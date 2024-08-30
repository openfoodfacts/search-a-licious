import logging
from typing import cast

from . import config
from ._types import (
    DebugInfo,
    QueryAnalysis,
    SearchParameters,
    SearchResponse,
    SearchResponseDebug,
    SuccessSearchResponse,
)
from .charts import build_charts
from .facets import build_facets
from .postprocessing import BaseResultProcessor, load_result_processor
from .query import build_elasticsearch_query_builder, build_search_query, execute_query

logger = logging.getLogger(__name__)

if config.CONFIG is None:
    # We want to be able to import api.py (for tests for example) without
    # failure, but we add a warning message as it's not expected in a
    # production settings
    logger.warning("Main configuration is not set, use CONFIG_PATH envvar")
    ES_QUERY_BUILDERS = {}
    RESULT_PROCESSORS = {}
else:
    # we cache query builder and result processor here for faster processing
    ES_QUERY_BUILDERS = {
        index_id: build_elasticsearch_query_builder(index_config)
        for index_id, index_config in config.CONFIG.indices.items()
    }
    RESULT_PROCESSORS = {
        index_id: load_result_processor(index_config)
        for index_id, index_config in config.CONFIG.indices.items()
    }


def add_debug_info(
    search_result: SuccessSearchResponse,
    analysis: QueryAnalysis,
    params: SearchParameters,
) -> SearchResponseDebug | None:
    if not params.debug_info:
        return None
    data = {}
    for debug_info in params.debug_info:
        match debug_info:
            case DebugInfo.es_query:
                data[debug_info.value] = (
                    analysis.es_query.to_dict() if analysis.es_query else None
                )
            case DebugInfo.lucene_query:
                data[debug_info.value] = (
                    str(analysis.luqum_tree) if analysis.luqum_tree else None
                )
            case DebugInfo.aggregations:
                data[debug_info.value] = search_result.aggregations
    return SearchResponseDebug(**data)


def search(
    params: SearchParameters,
) -> SearchResponse:
    """Run a search"""
    result_processor = cast(
        BaseResultProcessor, RESULT_PROCESSORS[params.valid_index_id]
    )
    logger.debug(
        "Received search query: q='%s', langs='%s', page=%d, "
        "page_size=%d, fields='%s', sort_by='%s', charts='%s'",
        params.q,
        params.langs_set,
        params.page,
        params.page_size,
        params.fields,
        params.sort_by,
        params.charts,
    )
    index_config = params.index_config
    query = build_search_query(
        params,
        # ES query builder is generated from elasticsearch mapping and
        # takes ~40ms to generate, build-it before hand to avoid this delay
        es_query_builder=ES_QUERY_BUILDERS[params.valid_index_id],
    )
    (
        logger.debug(
            "Luqum query: %s\nElasticsearch query: %s",
            str(query.luqum_tree),
            query.es_query.to_dict() if query.es_query else query.es_query,
        )
        if logger.isEnabledFor(logging.DEBUG)  # avoid processing if no debug
        else None
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
        search_result.charts = build_charts(search_result, index_config, params.charts)
        search_result.debug = add_debug_info(search_result, query, params)
        # remove aggregations
        search_result.aggregations = None
    return search_result
