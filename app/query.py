import elastic_transport
import elasticsearch
import luqum.exceptions
from elasticsearch_dsl import A, Search
from elasticsearch_dsl.aggs import Agg
from luqum import tree
from luqum.elasticsearch.schema import SchemaAnalyzer
from luqum.elasticsearch.visitor import ElasticsearchQueryBuilder
from luqum.parser import parser
from luqum.utils import OpenRangeTransformer, UnknownOperationResolver

from ._types import (
    ErrorSearchResponse,
    JSONType,
    PostSearchParameters,
    QueryAnalysis,
    SearchParameters,
    SearchResponse,
    SearchResponseDebug,
    SearchResponseError,
    SuccessSearchResponse,
)
from .config import FieldType, IndexConfig
from .es_query_builder import FullTextQueryBuilder
from .es_scripts import get_script_id
from .exceptions import InvalidLuceneQueryError, QueryCheckError, UnknownScriptError
from .indexing import generate_index_object
from .postprocessing import BaseResultProcessor
from .query_pipeline import (
    add_languages_suffix,
    boost_phrases,
    check_query,
    compute_facets_filters,
    parse_query,
    resolve_open_ranges,
    resolve_unknown_operation,
)
from .query_transformers import QueryCheck
from .utils import get_logger, str_utils

logger = get_logger(__name__)


def build_elasticsearch_query_builder(config: IndexConfig) -> ElasticsearchQueryBuilder:
    """Create the ElasticsearchQueryBuilder object
    according to our configuration"""
    index = generate_index_object(config.index.name, config)
    options = SchemaAnalyzer(index.to_dict()).query_builder_options()
    # we default to a AND between terms that are just space separated
    options["default_operator"] = ElasticsearchQueryBuilder.MUST
    # remove default_field
    options.pop("default_field", None)
    return FullTextQueryBuilder(**options)


def parse_sort_by_field(sort_by: str | None, config: IndexConfig) -> str | None:
    """Parse `sort_by` parameter, special handling is performed for `text_lang`
    subfield.

    :param sort_by: the raw `sort_by` value
    :param config: the index configuration to use
    :return: None if `sort_by` is not provided or the final value otherwise
    """
    if sort_by is None:
        return None

    operator, sort_by = str_utils.split_sort_by_sign(sort_by)

    for field in config.fields.values():
        if field.name == sort_by:
            if field.type is FieldType.text_lang:
                # use 'main' language subfield for sorting
                sort_by = f"{field.name}.main"
                break

    if operator == "-":
        sort_by = f"-{sort_by}"

    return sort_by


def parse_sort_by_script(
    sort_by: str,
    params: JSONType | None,
    config: IndexConfig,
    index_id: str,
) -> JSONType:
    """Create the ES sort expression to sort by a script"""
    # remove negation mark while retaining we want negative sorting
    operator, sort_by = str_utils.split_sort_by_sign(sort_by)
    script = (config.scripts or {}).get(sort_by)
    if script is None:
        raise UnknownScriptError(f"Unknown script '{sort_by}'")
    script_id = get_script_id(index_id, sort_by)
    # join params and static params
    script_params = dict((params or {}), **(script.static_params or {}))
    return {
        "_script": {
            "type": "number",
            "script": {
                "id": script_id,
                "params": script_params,
            },
            "order": "desc" if operator == "-" else "asc",
        }
    }


def create_aggregation_clauses(
    config: IndexConfig, fields: set[str] | list[str] | None
) -> dict[str, Agg]:
    """Create term bucket aggregation clauses
    for all fields corresponding to facets,
    as defined in the config
    """
    clauses = {}
    if fields is not None:
        for field_name in fields:
            field = config.fields[field_name]
            if field.bucket_agg:
                # TODO - aggregation might depend on agg type or field type
                clauses[field.name] = A("terms", field=field.name)
    return clauses


def build_search_query(
    params: SearchParameters,
    es_query_builder: ElasticsearchQueryBuilder,
) -> QueryAnalysis:
    """Build an elasticsearch_dsl Query.

    :param params: SearchParameters containing all search parameters
    :param es_query_builder: the builder to transform
      the luqum tree to an elasticsearch query
    :return: the built Search query
    """
    analysis = parse_query(params.q)
    analysis = compute_facets_filters(analysis)
    analysis = resolve_unknown_operation(analysis)
    analysis = resolve_open_ranges(analysis)
    if params.boost_phrase and params.sort_by is None:
        analysis = boost_phrases(
            analysis,
            params.index_config.match_phrase_boost,
            params.index_config.match_phrase_boost_proximity,
        )
    # add languages for localized fields
    analysis = add_languages_suffix(analysis, params.langs, params.index_config)
    # we are at a goop point to check the query
    check_query(params, analysis)

    logger.debug("luqum query: %s", analysis.luqum_tree)

    return build_es_query(analysis, params, es_query_builder)


def build_es_query(
    analysis: QueryAnalysis,
    params: SearchParameters,
    es_query_builder: ElasticsearchQueryBuilder,
) -> QueryAnalysis:
    config = params.index_config
    es_query = Search(index=config.index.name)
    # main query
    if analysis.luqum_tree is not None:
        try:
            es_query = es_query.query(
                es_query_builder(analysis.luqum_tree, params.index_config, params.langs)
            )
        except luqum.exceptions.InconsistentQueryException as e:
            raise InvalidLuceneQueryError(
                "Request could not be transformed by luqum"
            ) from e

    agg_fields = set(params.facets) if params.facets is not None else set()
    if params.charts is not None:
        agg_fields.update(
            [
                chart.field
                for chart in params.charts
                if chart.chart_type == "DistributionChart"
            ]
        )
    for agg_name, agg in create_aggregation_clauses(config, agg_fields).items():
        es_query.aggs.bucket(agg_name, agg)

    sort_by: JSONType | str | None = None
    if (
        isinstance(params, PostSearchParameters)
        and params.uses_sort_script
        and params.sort_by is not None
    ):
        sort_by = parse_sort_by_script(
            params.sort_by, params.sort_params, config, params.valid_index_id
        )
    else:
        sort_by = parse_sort_by_field(params.sort_by, config)
    if sort_by is not None:
        es_query = es_query.sort(sort_by)

    es_query = es_query.extra(
        size=params.page_size,
        from_=params.page_size * (params.page - 1),
    )
    return analysis.clone(es_query=es_query)


def build_completion_query(
    q: str,
    taxonomy_names: list[str],
    langs: list[str],
    size: int,
    config: IndexConfig,
    fuzziness: int | None = 2,
):
    """Build an elasticsearch_dsl completion Query.

    :param q: the user autocomplete query
    :param taxonomy_names: a list of taxonomies we want to search in
    :param langs: the languages we want search in
    :param size: number of results to return
    :param config: the index configuration to use
    :param fuzziness: fuzziness parameter for completion query
    :return: the built Query
    """
    query = Search(index=config.taxonomy.index.name)
    # import pdb;pdb.set_trace();
    for lang in langs:
        completion_clause = {
            "field": f"synonyms.{lang}",
            "size": size,
            "contexts": {"taxonomy_name": taxonomy_names},
            "skip_duplicates": True,
        }
        if fuzziness is not None:
            completion_clause["fuzzy"] = {"fuzziness": fuzziness}

        query = query.suggest(
            f"taxonomy_suggest_{lang}",
            q,
            completion=completion_clause,
        )
    # limit returned fields
    query.source(fields=["id", "taxonomy_name", "name"])
    return query


def execute_query(
    query: Search,
    result_processor: BaseResultProcessor,
    page: int,
    page_size: int,
    projection: set[str] | None = None,
) -> SearchResponse:
    errors = []
    debug = SearchResponseDebug(es_query=query.to_dict())
    try:
        results = query.execute()
    except elasticsearch.ApiError as e:
        logger.error("Error while running query: %s %s", str(e), str(e.body))
        errors.append(SearchResponseError(title="es_api_error", description=str(e)))
        return ErrorSearchResponse(debug=debug, errors=errors)
    except elastic_transport.ConnectionError as e:
        errors.append(
            SearchResponseError(title="es_connection_error", description=str(e))
        )
        return ErrorSearchResponse(debug=debug, errors=errors)

    response = result_processor.process(results, projection)
    count = response["count"]
    return SuccessSearchResponse(
        page=page,
        page_size=page_size,
        page_count=count // page_size + int(bool(count % page_size)),
        debug=debug,
        **response,
    )
