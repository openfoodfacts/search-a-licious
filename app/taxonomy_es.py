"""Operations on taxonomies in ElasticSearch

See also :py:mod:`app.taxonomy`
"""

import re

import elasticsearch
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Q

from app.config import MAX_SYNONYMS_SETS_RULES, IndexConfig
from app.exceptions import TooManySynonymsSetsException
from app.taxonomy import Taxonomy, iter_taxonomies
from app.utils import connection
from app.utils.lists import batch


def get_taxonomy_names(
    items: list[tuple[str, str]],
    config: IndexConfig,
) -> dict[tuple[str, str], dict[str, str]]:
    """Given a set of terms in different taxonomies, return their names"""
    filters = []
    no_lang_prefix_ids = {id_ for id_, _ in items if ":" not in id_}
    for id, taxonomy_name in items:
        # we may not have lang prefix, in this case blind match them
        id_term = (
            Q("term", id=id)
            if id not in no_lang_prefix_ids
            else Q("wildcard", id={"value": f"*:{id}"})
        )
        # match one term
        filters.append(id_term & Q("term", taxonomy_name=taxonomy_name))
    query = (
        Search(index=config.taxonomy.index.name)
        .filter("bool", should=filters, minimum_should_match=1)
        .params(size=len(filters))
    )
    results = query.execute().hits
    # some id needs to be replaced by a value
    no_lang_prefix = {result.id: result.id.split(":", 1)[-1] for result in results}
    translations = {
        (result.id, result.taxonomy_name): result.name.to_dict() for result in results
    }
    # add values without prefix, because we may have some
    translations.update(
        {
            (no_lang_prefix[result.id], result.taxonomy_name): result.name.to_dict()
            for result in results
            if no_lang_prefix[result.id] in no_lang_prefix_ids
        }
    )
    return translations


def _normalize_synonym(token: str) -> str:
    """Normalize a synonym,

    It applies the same filter as ES will apply before the synonym filter
    to ensure matching tokens
    """
    # make lower case
    token = token.lower()
    # changes anything that is neither a word char nor a space for space
    token = re.sub(r"[^\w\s]+", " ", token)
    # normalize spaces
    token = re.sub(r"\s+", " ", token)
    # TODO: should we also run asciifolding or so ? Or depends on language ?
    return token


def compute_synonyms_sets(
    taxonomy: Taxonomy, langs: list[str]
) -> dict[str, dict[str, list[str]]]:
    """Compute synonyms rules to put in synonym sets corresponding to a taxonomy

    We will match every known synonym in a language
    to the identifier of the entry.
    We do this because we are not sure which is the main language for an entry.

    Also the special xx language is added to every languages if it exists.
    """

    # create the sets
    synonyms_sets: dict[str, dict[str, list[str]]] = {lang: {} for lang in langs}

    for node in taxonomy.iter_nodes():
        # we add multi lang synonyms to every language
        multi_lang_synonyms = node.synonyms.get("xx", [])
        multi_lang_synonyms = [_normalize_synonym(s) for s in multi_lang_synonyms]
        # also node id without prefix
        multi_lang_synonyms.append(_normalize_synonym(node.id.split(":", 1)[-1]))
        multi_lang_synonyms = [s for s in multi_lang_synonyms if s.strip()]
        for lang, synonyms in node.synonyms.items():
            if (not synonyms and not multi_lang_synonyms) or lang not in langs:
                continue
            # avoid commas in synonyms… add multilang syns and identifier without prefix
            synonyms_ = (_normalize_synonym(s) for s in synonyms)
            synonyms = [s for s in synonyms_ if s.strip()]
            synonyms = sorted(set(synonyms + multi_lang_synonyms))
            synonyms = [s for s in synonyms if s.strip()]
            if synonyms:
                # add rule
                synonyms_sets[lang][node.id] = synonyms
    return synonyms_sets


def ingest_synonyms_sets(
    index_config: IndexConfig,
    taxonomy: Taxonomy,
    computed_sets: dict[str, dict[str, list[str]]],
    es: elasticsearch.Elasticsearch,
):
    """Create synonyms sets corresponding to a taxonomy in Elasticsearch
    that can be used to define a Synonym Graph Token Filter

    see:
    https://www.elastic.co/guide/en/elasticsearch/reference/current/search-with-synonyms.html#synonyms-store-synonyms-file
    and
    https://www.elastic.co/docs/api/doc/elasticsearch/v8/operation/operation-synonyms-put-synonym
    """
    created_sets = set()
    for lang, lang_synonyms_sets in computed_sets.items():
        set_name = index_config.get_synonym_set_name(taxonomy.name, lang)
        # there is a limit to 10000 synonyms rules per set so use batching
        for set_num, batched_synonyms_sets_items in enumerate(
            batch(lang_synonyms_sets.items(), MAX_SYNONYMS_SETS_RULES)
        ):
            # see
            # https://www.elastic.co/docs/reference/text-analysis/analysis-synonym-graph-tokenfilter#_solr_synonyms_2
            # for rule definition
            set_id = f"{set_name}-{set_num}"
            es.synonyms.put_synonym(
                id=set_id,
                synonyms_set=[
                    {"id": id, "synonyms": f"{','.join(synonyms)} => {id}"}
                    for id, synonyms in batched_synonyms_sets_items
                ],
            )
            created_sets.add(set_id)
    # eventually created some more needed sets as empty sets
    # because analyzers will cite them
    expected_sets_ids = set(
        expected_synonyms_sets_ids(index_config, taxonomy.name, None)
    )
    for set_id in expected_sets_ids - created_sets:
        es.synonyms.put_synonym(
            id=set_id,
            synonyms_set=[],
        )
    created_sets |= expected_sets_ids
    return created_sets


def iter_synonyms_sets(index_config: IndexConfig, es: elasticsearch.Elasticsearch):
    """Iterate synonyms sets names that correspond to this index_config"""
    seen = 0
    count = 100  # we will get real count in first response
    while seen < count:
        infos = es.synonyms.get_synonyms_sets(from_=seen, size=1000)
        count = infos["count"]
        for info in infos["results"]:
            # our synonyms set starts with our index name
            if info["synonyms_set"].startswith(index_config.index.name):
                yield info["synonyms_set"]
        seen += len(infos["results"])


def create_synonyms(
    index_name: str, index_config: IndexConfig, es: elasticsearch.Elasticsearch
):
    created_sets = set()
    for taxonomy in iter_taxonomies(index_config.taxonomy):
        # generate synonyms files
        computed_sets = compute_synonyms_sets(taxonomy, index_config.supported_langs)
        taxonomy_created_sets = ingest_synonyms_sets(
            index_config, taxonomy, computed_sets, es
        )
        created_sets.update(taxonomy_created_sets)
    return created_sets


def remove_synonyms_sets(sets_ids: set, es: elasticsearch.Elasticsearch):
    for set_id in sets_ids:
        es.synonyms.delete_synonym(id=set_id)


def check_synonyms_sets_size(index_config: IndexConfig):
    es = connection.current_es_client()
    existing_sets = set(iter_synonyms_sets(index_config, es))
    expected_sets = set()
    for source in index_config.taxonomy.sources:
        expected_sets.update(
            expected_synonyms_sets_ids(index_config, source.name, None)
        )
    if existing_sets - expected_sets:
        extra = ", ".join(existing_sets - expected_sets)
        raise TooManySynonymsSetsException(
            f"Synonyms sets that won't be taken into account: {extra}"
        )


def expected_synonyms_sets_ids(
    index_config: IndexConfig, taxonomy_name: str, lang: str | None
):
    """Get the name of synonyms_sets to take into account for a taxonomy
    and eventually a language
    """
    langs = [lang] if lang else index_config.supported_langs
    taxonomy_config = index_config.taxonomy.sources_by_name.get(taxonomy_name)
    if not taxonomy_config:
        return
    chunks_num = (
        int((taxonomy_config.max_synonyms_entries - 1) / MAX_SYNONYMS_SETS_RULES) + 1
    )
    for lang in langs:
        set_prefix = index_config.get_synonym_set_name(taxonomy_name, lang)
        yield from (f"{set_prefix}-{i}" for i in range(chunks_num))


def refresh_synonyms(index_name: str, index_config: IndexConfig):
    es = connection.current_es_client()
    # get currently existing sets
    existing_sets = set(iter_synonyms_sets(index_config, es))
    created_sets = create_synonyms(index_name, index_config, es)
    # remove sets that are not there any more
    remove_synonyms_sets(existing_sets - created_sets, es)
    if es.indices.exists(index=index_name):
        # trigger update of synonyms in token filters by reloading search analyzers
        # and clearing relevant cache
        es.indices.reload_search_analyzers(index=index_name)
        es.indices.clear_cache(index=index_name, request=True)
