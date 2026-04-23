import functools
import logging
from typing import cast

from . import config
from ._types import (
    DebugInfo,
    ErrorSearchResponse,
    QueryAnalysis,
    SearchParameters,
    SearchResponse,
    SearchResponseDebug,
    SearchResponseError,
    SuccessSearchResponse,
)
from .charts import build_charts
from .exceptions import QueryCheckError
from .facets import build_facets
from .postprocessing import BaseResultProcessor, load_result_processor
from .query import build_elasticsearch_query_builder, build_search_query, execute_query

logger = logging.getLogger(__name__)


# cache query builder and result processor for faster processing
# Using lru_cache with config id as part of the key acts as a versioned cache,
# so on config update old cached items are flushed automatically due to the maxsize bound.
@functools.lru_cache(maxsize=32)
def _get_es_query_builder_cached(index_id: str, config_version: int):
    logger.info("Initializing ES query builder cache for index %s (config %s)", index_id, config_version)
    index_config = config.get_config().indices[index_id]
    return build_elasticsearch_query_builder(index_config)


def get_es_query_builder(index_id: str):
    return _get_es_query_builder_cached(index_id, id(config.get_config()))


@functools.lru_cache(maxsize=32)
def _get_result_processor_cached(index_id: str, config_version: int):
    logger.info("Initializing result processor cache for index %s (config %s)", index_id, config_version)
    index_config = config.get_config().indices[index_id]
    return load_result_processor(index_config)


def get_result_processor(index_id: str):
    return _get_result_processor_cached(index_id, id(config.get_config()))


def log_cache_metrics():
    logger.info("ES Query Builder Cache Stats: %s", _get_es_query_builder_cached.cache_info())
    logger.info("Result Processor Cache Stats: %s", _get_result_processor_cached.cache_info())


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
        BaseResultProcessor, get_result_processor(params.valid_index_id)
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
    try:
        query = build_search_query(
            params,
            # ES query builder is generated from elasticsearch mapping and
            # takes ~40ms to generate, build-it before hand to avoid this delay
            es_query_builder=get_es_query_builder(params.valid_index_id),
        )
    except QueryCheckError as e:
        return ErrorSearchResponse(
            debug=SearchResponseDebug(),
            errors=[SearchResponseError(title="QueryCheckError", description=str(e))],
        )
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Luqum query: %s\nElasticsearch query: %s",
            str(query.luqum_tree),
            query.es_query.to_dict() if query.es_query else query.es_query,
        )
        logger.debug("ES Builder Cache Info: %s", _get_es_query_builder_cached.cache_info())
        logger.debug("Result processor Cache Info: %s", _get_result_processor_cached.cache_info())

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
