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
from .config import IndexConfig
from .exceptions import QueryAnalysisError
from .facets import build_facets
from .postprocessing import BaseResultProcessor, load_result_processor
from .query import build_elasticsearch_query_builder, build_search_query, execute_query

logger = logging.getLogger(__name__)


class _ConfigRef:
    """Hashable reference to an index config, compared by identity.

    Used as part of the cache key, so each config object has its own entries.
    As the entry keeps a reference to the config, its identity cannot be reused
    while the entry is cached. Outdated entries are flushed by the `maxsize` bound.
    """

    __slots__ = ("index_config",)

    def __init__(self, index_config: IndexConfig):
        self.index_config = index_config

    def __hash__(self):
        return id(self.index_config)

    def __eq__(self, other):
        return isinstance(other, _ConfigRef) and self.index_config is other.index_config


# cache query builder and result processor for faster processing
@functools.lru_cache(maxsize=32)
def _get_es_query_builder_cached(index_id: str, config_ref: _ConfigRef):
    return build_elasticsearch_query_builder(config_ref.index_config)


def get_es_query_builder(index_id: str, index_config: IndexConfig | None = None):
    """Get the (cached) query builder.

    Pass `index_config` to use the same config snapshot as the rest of a request.
    """
    if index_config is None:
        index_config = config.get_config().indices[index_id]
    return _get_es_query_builder_cached(index_id, _ConfigRef(index_config))


@functools.lru_cache(maxsize=32)
def _get_result_processor_cached(index_id: str, config_ref: _ConfigRef):
    return load_result_processor(config_ref.index_config)


def get_result_processor(index_id: str, index_config: IndexConfig | None = None):
    """Get the (cached) result processor.

    Pass `index_config` to use the same config snapshot as the rest of a request.
    """
    if index_config is None:
        index_config = config.get_config().indices[index_id]
    return _get_result_processor_cached(index_id, _ConfigRef(index_config))


def log_cache_metrics():
    logger.info(
        "ES Query Builder Cache Stats: %s", _get_es_query_builder_cached.cache_info()
    )
    logger.info(
        "Result Processor Cache Stats: %s", _get_result_processor_cached.cache_info()
    )


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
    # use a single config snapshot for the whole request
    index_config = params.index_config
    result_processor = cast(
        BaseResultProcessor,
        get_result_processor(params.valid_index_id, index_config),
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
    try:
        query = build_search_query(
            params,
            # ES query builder is generated from elasticsearch mapping and
            # takes ~40ms to generate, build-it before hand to avoid this delay
            es_query_builder=get_es_query_builder(params.valid_index_id, index_config),
        )
    except (QueryAnalysisError, ValueError) as e:
        return ErrorSearchResponse(
            debug=SearchResponseDebug(),
            errors=[
                SearchResponseError(
                    title=e.__class__.__name__,
                    description=str(e),
                    status=400,
                )
            ],
        )
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Luqum query: %s\nElasticsearch query: %s",
            str(query.luqum_tree),
            query.es_query.to_dict() if query.es_query else query.es_query,
        )
        logger.debug(
            "ES Builder Cache Info: %s", _get_es_query_builder_cached.cache_info()
        )
        logger.debug(
            "Result processor Cache Info: %s", _get_result_processor_cached.cache_info()
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
        search_result.charts = build_charts(
            search_result,
            index_config,
            params.charts,
            params.main_lang,
            y_axis=params.charts_y_axis,
        )
        search_result.debug = add_debug_info(search_result, query, params)
        # remove aggregations
        search_result.aggregations = None
    return search_result
