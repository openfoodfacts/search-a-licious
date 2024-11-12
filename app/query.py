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
from .query_transformers import (
    LanguageSuffixTransformer,
    PhraseBoostTransformer,
    QueryCheck,
)
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


def parse_query(q: str | None) -> QueryAnalysis:
    """Begin query analysis by parsing the query."""
    analysis = QueryAnalysis(text_query=q)
    if q is None or not q.strip():
        return analysis
    try:
        analysis.luqum_tree = parser.parse(q)
        # FIXME: resolve UnknownFilter (to AND)
    except (
        luqum.exceptions.ParseError,
        luqum.exceptions.InconsistentQueryException,
    ) as e:
        raise InvalidLuceneQueryError("Request could not be analyzed by luqum") from e
    return analysis


def compute_facets_filters(q: QueryAnalysis) -> QueryAnalysis:
    """Extract facets filters from the query

    For now it only handles SearchField under a top AND operation,
    which expression is a bare term or a OR operation of bare terms.

    We do not verify if the field is an aggregation field or not,
    that can be done at a later stage

    :return: a new QueryAnalysis with facets_filters attribute
       as a dictionary of field names and list of values to filter on
    """
    if q.luqum_tree is None:
        return q

    filters = {}

    def _process_search_field(expr, field_name):
        facet_filter = None
        if isinstance(expr, tree.Term):
            # simple term
            facet_filter = [str(expr)]
        elif isinstance(expr, tree.FieldGroup):
            # use recursion
            _process_search_field(expr.expr, field_name)
        elif isinstance(expr, tree.OrOperation) and all(
            isinstance(item, tree.Term) for item in expr.children
        ):
            # OR operation of simple terms
            facet_filter = [str(item) for item in expr.children]
        if facet_filter:
            if field_name not in filters:
                filters[field_name] = facet_filter
            else:
                # avoid the case of double expression, we don't handle it
                filters.pop(field_name)

    if isinstance(q.luqum_tree, (tree.AndOperation, tree.UnknownOperation)):
        for child in q.luqum_tree.children:
            if isinstance(child, tree.SearchField):
                _process_search_field(child.expr, child.name)
    # case of a single search field
    elif isinstance(q.luqum_tree, tree.SearchField):
        _process_search_field(q.luqum_tree.expr, q.luqum_tree.name)
    # remove quotes around values
    filters = {
        field_name: [value.strip('"') for value in values]
        for field_name, values in filters.items()
    }
    return q.clone(facets_filters=filters)


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


def add_languages_suffix(
    analysis: QueryAnalysis, langs: list[str], config: IndexConfig
) -> QueryAnalysis:
    """Add correct languages suffixes to fields of type text_lang or taxonomy

    This match in a langage OR another
    """
    if analysis.luqum_tree is None:
        return analysis
    transformer = LanguageSuffixTransformer(
        lang_fields=set(config.lang_fields), langs=langs
    )
    analysis.luqum_tree = transformer.visit(analysis.luqum_tree)
    return analysis


def resolve_unknown_operation(analysis: QueryAnalysis) -> QueryAnalysis:
    """Resolve unknown operations in the query to a AND"""
    if analysis.luqum_tree is None:
        return analysis
    transformer = UnknownOperationResolver(resolve_to=tree.AndOperation)
    analysis.luqum_tree = transformer.visit(analysis.luqum_tree)
    return analysis


def boost_phrases(
    analysis: QueryAnalysis, boost: float, proximity: int | None
) -> QueryAnalysis:
    """Boost all phrases in the query"""
    if analysis.luqum_tree is None:
        return analysis
    transformer = PhraseBoostTransformer(boost=boost, proximity=proximity)
    analysis.luqum_tree = transformer.visit(analysis.luqum_tree)
    return analysis


def check_query(params: SearchParameters, analysis: QueryAnalysis) -> None:
    """Run some sanity checks on the luqum query"""
    if analysis.luqum_tree is None:
        return
    checker = QueryCheck(index_config=params.index_config, zeal=1)
    errors = checker.errors(analysis.luqum_tree)
    if errors:
        raise QueryCheckError("Found errors while checking query", errors=errors)


def resolve_open_ranges(analysis: QueryAnalysis) -> QueryAnalysis:
    """We need to resolve open ranges to closed ranges
    before using elasticsearch query builder"""
    if analysis.luqum_tree is None:
        return analysis
    transformer = OpenRangeTransformer()
    analysis.luqum_tree = transformer.visit(analysis.luqum_tree)
    return analysis


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
    if params.uses_sort_script and params.sort_by is not None:
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
    debug = SearchResponseDebug(query=query.to_dict())
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
