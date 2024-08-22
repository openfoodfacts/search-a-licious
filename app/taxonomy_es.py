"""Operations on taxonomies in ElasticSearch

See also :py:mod:`app.taxonomy`
"""

import os
import shutil
from pathlib import Path

from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Q

from app.config import IndexConfig
from app.taxonomy import Taxonomy, iter_taxonomies
from app.utils import connection


def get_taxonomy_names(
    items: list[tuple[str, str]],
    config: IndexConfig,
) -> dict[tuple[str, str], dict[str, list[str]]]:
    """Given a set of terms in different taxonomies, return their names"""
    filters = []
    for id, taxonomy_name in items:
        # match one term
        filters.append(Q("term", id=id) & Q("term", taxonomy_name=taxonomy_name))
    query = (
        Search(index=config.taxonomy.index.name)
        .filter("bool", should=filters, minimum_should_match=1)
        .params(size=len(filters))
    )
    return {
        (result.id, result.taxonomy_name): result.names.to_dict()
        for result in query.execute().hits
    }


def _normalize_synonym(token: str) -> str:
    """Normalize a synonym,

    It applies the same filter as ES will apply before the synonym filter
    to ensure matching tokens
    """
    # also avoid commas in synonyms…
    # TODO: should we also run asciifolding or so ? Or depends on language ?
    return token.lower().replace(" ", "_")


def create_synonyms_files(taxonomy: Taxonomy, langs: list[str], target_dir: Path):
    """Create a set of files that can be used to define a Synonym Graph Token Filter

    We will match every known synonym in a language
    to the identifier of the entry.
    We do this because we are not sure which is the main language for an entry.

    Also the special xx language is added to every languages if it exists.

    see:
    https://www.elastic.co/guide/en/elasticsearch/reference/current/search-with-synonyms.html#synonyms-store-synonyms-file
    """

    # auto-generate synonyms files for each language, ready to write to
    synonyms_paths = {lang: (target_dir / f"{lang}.txt") for lang in langs}
    synonyms_files = {lang: fpath.open("w") for lang, fpath in synonyms_paths.items()}

    for node in taxonomy.iter_nodes():
        multi_lang_synonyms = node.synonyms.get("xx", [])
        multi_lang_synonyms = [_normalize_synonym(s) for s in multi_lang_synonyms]
        for lang, synonyms in node.synonyms.items():
            if (not synonyms and not multi_lang_synonyms) or lang not in langs:
                continue
            # avoid commas in synonyms…
            synonyms = [_normalize_synonym(s) for s in synonyms] + multi_lang_synonyms
            synonyms_files[lang].write(f"{','.join(synonyms)} => {node.id}\n")

    # close files
    for f in synonyms_files.values():
        f.close()


def create_synonyms(index_config: IndexConfig, target_dir: Path):
    for name, taxonomy in iter_taxonomies(index_config.taxonomy):
        target = target_dir / name
        # a temporary directory, we move at the end
        target_tmp = target_dir / f"{name}.tmp"
        # ensure directory
        os.makedirs(target_tmp, mode=0o775, exist_ok=True)
        # generate synonyms files
        create_synonyms_files(taxonomy, index_config.supported_langs, target_tmp)
        # move to final location, overriding previous files
        shutil.move(target, str(target) + ".old")
        shutil.move(target_tmp, target)
        shutil.rmtree(str(target) + ".old")
        # Note: in current deployment, file are shared between ES instance,
        # so we don't need to replicate the files


def refresh_synonyms(index_name: str, index_config: IndexConfig, target_dir: Path):
    create_synonyms(index_config, target_dir)
    es = connection.current_es_client()
    if es.indices.exists(index=index_name):
        # trigger update of synonyms in token filters by reloading search analyzers
        # and clearing relevant cache
        es.reload_search_analyzers(index_name)
        es.clear_cache(index_name, request=True)
