import logging
import threading
import weakref
from typing import cast

from luqum.elasticsearch.visitor import ElasticsearchQueryBuilder

from . import config
from ._types import (
    BaseSearchParameters,
    ChartSearchParameters,
    ChartsInfos,
    DebugInfo,
    ErrorSearchResponse,
    QueryAnalysis,
    SearchParameters,
    SearchResponse,
    SearchResponseDebug,
    SearchResponseError,
    SuccessSearchResponse,
)
from .charts import build_charts, has_scatter_values
from .exceptions import QueryAnalysisError
from .facets import build_facets
from .postprocessing import BaseResultProcessor, load_result_processor
from .query import build_elasticsearch_query_builder, build_search_query, execute_query

logger = logging.getLogger(__name__)


# we cache query builder and result processor here for faster processing
_ES_QUERY_BUILDERS: dict[str, ElasticsearchQueryBuilder] = {}
_RESULT_PROCESSORS: dict[str, BaseResultProcessor] = {}
_CACHED_CONFIG_REF: weakref.ReferenceType[config.Config] | None = None
# protects the caches above (invalidation, check, build and lookup)
_CACHE_LOCK = threading.RLock()


def invalidate_runtime_caches():
    """Clear in-process caches used by search runtime."""
    global _CACHED_CONFIG_REF
    with _CACHE_LOCK:
        _ES_QUERY_BUILDERS.clear()
        _RESULT_PROCESSORS.clear()
        _CACHED_CONFIG_REF = None


def _ensure_runtime_caches_match_config():
    """Invalidate caches when global config object changed.

    Must be called with `_CACHE_LOCK` held.

    :return: the config object the caches are now consistent with
    """
    global _CACHED_CONFIG_REF
    current_config = config.get_config()
    if _CACHED_CONFIG_REF is None:
        _CACHED_CONFIG_REF = weakref.ref(current_config)
        return current_config

    if _CACHED_CONFIG_REF() is not current_config:
        logger.info("Global config changed, invalidating search runtime caches")
        _ES_QUERY_BUILDERS.clear()
        _RESULT_PROCESSORS.clear()
        _CACHED_CONFIG_REF = weakref.ref(current_config)
    return current_config


def get_es_query_builder(index_id):
    with _CACHE_LOCK:
        current_config = _ensure_runtime_caches_match_config()
        if index_id not in _ES_QUERY_BUILDERS:
            index_config = current_config.indices[index_id]
            _ES_QUERY_BUILDERS[index_id] = build_elasticsearch_query_builder(
                index_config
            )
        return _ES_QUERY_BUILDERS[index_id]


def get_result_processor(index_id):
    with _CACHE_LOCK:
        current_config = _ensure_runtime_caches_match_config()
        if index_id not in _RESULT_PROCESSORS:
            index_config = current_config.indices[index_id]
            _RESULT_PROCESSORS[index_id] = load_result_processor(index_config)
        return _RESULT_PROCESSORS[index_id]


def add_debug_info(
    search_result: SuccessSearchResponse,
    analysis: QueryAnalysis,
    params: BaseSearchParameters,
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


def _build_query(params: BaseSearchParameters) -> QueryAnalysis | ErrorSearchResponse:
    try:
        return build_search_query(
            params,
            # ES query builder is generated from elasticsearch mapping and
            # takes ~40ms to generate, build-it before hand to avoid this delay
            es_query_builder=get_es_query_builder(params.valid_index_id),
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
    query = _build_query(params)
    if isinstance(query, ErrorSearchResponse):
        return query
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


def chart(params: ChartSearchParameters) -> SearchResponse:
    """Build scatter charts from the first `max_entries` results"""
    query = _build_query(params)
    if isinstance(query, ErrorSearchResponse):
        return query
    result_processor = cast(
        BaseResultProcessor, get_result_processor(params.valid_index_id)
    )
    search_result = execute_query(
        query.es_query,
        result_processor,
        page=1,
        page_size=params.max_entries,
        projection={f.split(".")[0] for c in params.charts for f in (c.x, c.y)},
    )
    if isinstance(search_result, SuccessSearchResponse):
        all_hits = search_result.hits
        charts: ChartsInfos = {}
        for chart_option in params.charts:
            search_result.hits = [
                h for h in all_hits if has_scatter_values(h, chart_option)
            ]
            charts.update(
                build_charts(
                    search_result, params.index_config, [chart_option], params.main_lang
                )
            )
        search_result.charts = charts
        search_result.debug = add_debug_info(search_result, query, params)
        search_result.hits = []
        search_result.aggregations = None
    return search_result
