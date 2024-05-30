import logging
from typing import cast

from app import config
from app._types import SearchResponse
from app.facets import build_facets
from app.postprocessing import BaseResultProcessor, load_result_processor
from app.query import (
    build_elasticsearch_query_builder,
    build_search_query,
    execute_query,
)

logger = logging.getLogger(__name__)

if config.CONFIG is None:
    # We want to be able to import api.py (for tests for example) without
    # failure, but we add a warning message as it's not expected in a
    # production settings
    logger.warning("Main configuration is not set, use CONFIG_PATH envvar")
    FILTER_QUERY_BUILDERS = {}
    RESULT_PROCESSORS = {}
else:
    # we cache query builder and result processor here for faster processing
    FILTER_QUERY_BUILDERS = {
        index_id: build_elasticsearch_query_builder(index_config)
        for index_id, index_config in config.CONFIG.indices.items()
    }
    RESULT_PROCESSORS = {
        index_id: load_result_processor(index_config)
        for index_id, index_config in config.CONFIG.indices.items()
    }


def search(
    index_id: str | None,
    q: str | None,
    sort_by: str | None,
    page: int,
    page_size: int,
    fields: list[str] | None,
    langs: list[str],
    facets: list[str] | None,
) -> SearchResponse:
    """Run a search"""
    global_config = cast(config.Config, config.CONFIG)
    index_id, index_config = global_config.get_index_config(index_id)
    result_processor = cast(BaseResultProcessor, RESULT_PROCESSORS[index_id])
    langs_set = set(langs)
    logger.debug(
        "Received search query: q='%s', langs='%s', page=%d, "
        "page_size=%d, fields='%s', sort_by='%s'",
        q,
        langs_set,
        page,
        page_size,
        fields,
        sort_by,
    )

    query = build_search_query(
        q=q,
        langs=langs_set,
        size=page_size,
        page=page,
        config=index_config,
        sort_by=sort_by,
        # filter query builder is generated from elasticsearch mapping and
        # takes ~40ms to generate, build-it before hand to avoid this delay
        filter_query_builder=FILTER_QUERY_BUILDERS[index_id],
        facets=facets,
    )
    logger.debug("Elasticsearch query: %s", query.to_dict())

    projection = set(fields) if fields else None
    search_result = execute_query(
        query,
        result_processor,
        page=page,
        page_size=page_size,
        projection=projection,
    )
    search_result.facets = build_facets(search_result, index_config, facets)
    # remove aggregations to avoid sending too much information
    search_result.aggregations = None
    return search_result
