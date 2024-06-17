import logging
from typing import cast

from . import config
from ._types import SearchParameters, SearchResponse, SuccessSearchResponse
from .facets import build_facets
from .postprocessing import BaseResultProcessor, load_result_processor
from .query import build_elasticsearch_query_builder, build_search_query, execute_query

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
    params: SearchParameters,
) -> SearchResponse:
    """Run a search"""
    result_processor = cast(
        BaseResultProcessor, RESULT_PROCESSORS[params.valid_index_id]
    )
    logger.debug(
        "Received search query: q='%s', langs='%s', page=%d, "
        "page_size=%d, fields='%s', sort_by='%s'",
        params.q,
        params.langs_set,
        params.page,
        params.page_size,
        params.fields,
        params.sort_by,
    )
    index_config = params.index_config
    query = build_search_query(
        params,
        # filter query builder is generated from elasticsearch mapping and
        # takes ~40ms to generate, build-it before hand to avoid this delay
        filter_query_builder=FILTER_QUERY_BUILDERS[params.valid_index_id],
    )
    logger.debug(
        "Elasticsearch query: %s",
        query.es_query.to_dict() if query.es_query else query.es_query,
    )

    projection = set(params.fields) if params.fields else None
    search_result = execute_query(
        query.es_query,
        result_processor,
        page=params.page,
        page_size=params.page_size,
        projection=projection,
    )
    if isinstance(search_result, SuccessSearchResponse):
        search_result.facets = build_facets(
            search_result, query, params.main_lang, index_config, params.facets
        )
        # remove aggregations to avoid sending too much information
        search_result.aggregations = None
    return search_result
