"""Operations on taxonomies in ElasticSearch

See also :py:mod:`app.taxonomy`
"""

import os
import shutil
from pathlib import Path

from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Q

from app.config import IndexConfig, TaxonomyConfig
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


def create_synonyms_files(taxonomy: Taxonomy, target_dir: Path):
    """Create a set of files that can be used to define a Synonym Graph Token Filter

    see:
    https://www.elastic.co/guide/en/elasticsearch/reference/current/search-with-synonyms.html#synonyms-store-synonyms-file
    """

    # auto-generate synonyms files for each language, ready to write to
    synonyms_files = {}

    def file_for_lang(lang):
        if lang not in synonyms_files:
            fname = target_dir / f"{lang}.txt"
            synonyms_files[lang] = open(fname, "w")
        return synonyms_files[lang]

    for node in taxonomy.iter_nodes():
        for lang, synonyms in node.synonyms.items():
            if not synonyms:
                continue
            # avoid commas in synonyms…
            synonyms = [s.replace(",", " ") for s in synonyms]
            file_for_lang(lang).write(f"{','.join(synonyms)} => {node.id}\n")

    # close files
    for f in synonyms_files.values():
        f.close()


def create_synonyms(taxonomy_config: TaxonomyConfig, target_dir: Path):
    for name, taxonomy in iter_taxonomies(taxonomy_config):
        target = target_dir / name
        # a temporary directory, we move at the end
        target_tmp = target_dir / f"{name}.tmp"
        # ensure directory
        os.makedirs(target_tmp, mode=0o775, exist_ok=True)
        # generate synonyms files
        create_synonyms_files(taxonomy, target_tmp)
        # move to final location, overriding previous files
        shutil.move(target_tmp, target)
        # Note: in current deployment, file are shared between ES instance,
        # so we don't need to replicate the files


def refresh_synonyms(
    index_name: str, taxonomy_config: TaxonomyConfig, target_dir: Path
):
    create_synonyms(taxonomy_config, target_dir)
    es = connection.current_es_client()
    if es.indices.exists(index=index_name):
        # trigger update of synonyms in token filters by reloading search analyzers
        # and clearing relevant cache
        es.reload_search_analyzers(index_name)
        es.clear_cache(index_name, request=True)
