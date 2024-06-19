import elastic_transport
import luqum.exceptions
from elasticsearch_dsl import A, Q, Search
from elasticsearch_dsl.aggs import Agg
from elasticsearch_dsl.query import Query
from luqum import tree
from luqum.elasticsearch import ElasticsearchQueryBuilder
from luqum.elasticsearch.schema import SchemaAnalyzer
from luqum.parser import parser

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
from .es_scripts import get_script_id
from .indexing import generate_index_object
from .postprocessing import BaseResultProcessor
from .utils import get_logger, str_utils

logger = get_logger(__name__)


def build_elasticsearch_query_builder(config: IndexConfig) -> ElasticsearchQueryBuilder:
    """Create the ElasticsearchQueryBuilder object
    according to our configuration"""
    index = generate_index_object(config.index.name, config)
    options = SchemaAnalyzer(index.to_dict()).query_builder_options()
    # we default to a AND between terms that are just space separated
    options["default_operator"] = ElasticsearchQueryBuilder.MUST
    return ElasticsearchQueryBuilder(**options)


def build_query_clause(query: str, langs: list[str], config: IndexConfig) -> Query:
    fields = []
    supported_langs = config.get_supported_langs()
    taxonomy_langs = config.get_taxonomy_langs()
    match_phrase_boost_queries = []

    for field in config.fields.values():
        # We don't include all fields in the multi-match clause, only a subset
        # of them
        if field.full_text_search:
            if field.type in (FieldType.taxonomy, FieldType.text_lang):
                # language subfields are not the same depending on whether the
                # field is a `taxonomy` or a `text_lang` field
                langs_subset = frozenset(
                    supported_langs
                    if field.type is FieldType.text_lang
                    else taxonomy_langs
                )
                field_match_phrase_boost_queries = []
                for lang in (_lang for _lang in langs if _lang in langs_subset):
                    subfield_name = f"{field.name}.{lang}"
                    fields.append(subfield_name)
                    field_match_phrase_boost_queries.append(
                        Q(
                            "match_phrase",
                            **{
                                subfield_name: {
                                    "query": query,
                                    "boost": config.match_phrase_boost,
                                }
                            },
                        )
                    )
                if len(field_match_phrase_boost_queries) == 1:
                    match_phrase_boost_queries.append(
                        field_match_phrase_boost_queries[0]
                    )
                elif len(field_match_phrase_boost_queries) > 1:
                    match_phrase_boost_queries.append(
                        Q("bool", should=field_match_phrase_boost_queries)
                    )

            else:
                fields.append(field.name)
                match_phrase_boost_queries.append(
                    Q(
                        "match_phrase",
                        **{
                            field.name: {
                                "query": query,
                                "boost": config.match_phrase_boost,
                            }
                        },
                    )
                )

    multi_match_query = Q("multi_match", query=query, fields=fields)

    if match_phrase_boost_queries:
        multi_match_query |= Q("bool", should=match_phrase_boost_queries)

    return multi_match_query


def parse_query(q: str | None) -> QueryAnalysis:
    """Begin query analysis by parsing the query."""
    analysis = QueryAnalysis(text_query=q)
    if q is None:
        return analysis
    try:
        analysis.luqum_tree = parser.parse(q)
    except (
        luqum.exceptions.ParseError,
        luqum.exceptions.InconsistentQueryException,
    ) as e:
        # if the lucene syntax is invalid, consider the query as plain text
        logger.warning("parsing error for query: '%s':\n%s", q, e)
        analysis.luqum_tree = None
    return analysis


def decompose_query(
    q: QueryAnalysis, filter_query_builder: ElasticsearchQueryBuilder
) -> QueryAnalysis:
    """Decompose the query into two parts:

    - a Lucene DSL query, which is used as a filter clause in the
      Elasticsearch query. Luqum library is used to transform the
      Lucene DSL into Elasticsearch DSL.
    - remaining terms, used for full text search.

    :param q: the user query
    :param filter_query_builder: Luqum query builder
    :return: a tuple containing the Elasticsearch filter clause and
      the remaining terms for full text search
    """
    if q.text_query is None:
        return q
    remaining_terms = ""
    if q.luqum_tree is not None:
        # Successful parsing
        logger.debug("parsed luqum tree: %s", repr(q.luqum_tree))
        word_children = []
        filter_children = []
        if isinstance(q.luqum_tree, (tree.UnknownOperation, tree.AndOperation)):
            for child in q.luqum_tree.children:
                if isinstance(child, tree.Word):
                    word_children.append(child)
                else:
                    filter_children.append(child)
        elif isinstance(q.luqum_tree, tree.Word):
            # the query single term
            word_children.append(q.luqum_tree)
        else:
            filter_children.append(q.luqum_tree)
        # We join with space every non word not recognized by the parser
        remaining_terms = " ".join(item.value for item in word_children)
        filter_tree = None
        if filter_children:
            # Note: we always wrap in AndOperation,
            # even if only one, to be consistent
            filter_tree = tree.AndOperation(*filter_children)

        # remove harvested words
        logger.debug("filter luqum tree: %s", repr(filter_tree))
        if filter_tree:
            filter_query = filter_query_builder(filter_tree)
        else:
            filter_query = None
        logger.debug("filter query from luqum: '%s'", filter_query)
    else:
        filter_query = None
        remaining_terms = q.text_query

    return q.clone(fulltext=remaining_terms, filter_query=filter_query)


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
        raise ValueError(f"Unknown script '{sort_by}'")
    script_id = get_script_id(index_id, sort_by)
    return {
        "_script": {
            "type": "number",
            "script": {
                "id": script_id,
                "params": params,
            },
            "order": "desc" if operator == "-" else "asc",
        }
    }


def create_aggregation_clauses(
    config: IndexConfig, facets: list[str] | None
) -> dict[str, Agg]:
    """Create term bucket aggregation clauses
    for all fields corresponding to facets,
    as defined in the config
    """
    clauses = {}
    if facets is not None:
        for field_name in facets:
            field = config.fields[field_name]
            if field.bucket_agg:
                # TODO - aggregation might depend on agg type or field type
                clauses[field.name] = A("terms", field=field.name)
    clauses['nutriscore_grade'] = A("terms", field='nutriscore_grade')
    clauses['nova_group'] = A("terms", field='nova_group')
    # TODO: add  A("terms", field=field.name) for field.name in charts
    return clauses


def build_search_query(
    params: SearchParameters,
    filter_query_builder: ElasticsearchQueryBuilder,
) -> QueryAnalysis:
    """Build an elasticsearch_dsl Query.

    :param q: the user raw query
    :param langs: the set of languages we want to support, it is used to
      select language subfields for some field types
    :param size: number of results to return
    :param page: requested page (starts at 1).
    :param config: the index configuration to use
    :param filter_query_builder: luqum elasticsearch query builder
    :param sort_by: sorting key, defaults to None (=relevance-based sorting)
    :return: the built Search query
    """
    analysis = parse_query(params.q)
    analysis = decompose_query(analysis, filter_query_builder)
    analysis = compute_facets_filters(analysis)

    logger.debug("filter query: %s", analysis.filter_query)
    logger.debug("remaining terms: '%s'", analysis.fulltext)

    return build_es_query(analysis, params)


def build_es_query(
    q: QueryAnalysis,
    params: SearchParameters,
) -> QueryAnalysis:
    config = params.index_config
    es_query = Search(index=config.index.name)

    if q.fulltext:
        base_multi_match_q = build_query_clause(q.fulltext, params.langs, config)
        es_query = es_query.query(base_multi_match_q)

    if q.filter_query:
        es_query = es_query.query("bool", filter=q.filter_query)

    for agg_name, agg in create_aggregation_clauses(config, params.facets).items():
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
    return q.clone(es_query=es_query)


def build_completion_query(
    q: str,
    taxonomy_names: list[str],
    lang: str,
    size: int,
    config: IndexConfig,
    fuzziness: int | None = 2,
):
    """Build an elasticsearch_dsl completion Query.

    :param q: the user autocomplete query
    :param taxonomy_names: a list of taxonomies we want to search in
    :param lang: the language we want search in
    :param size: number of results to return
    :param config: the index configuration to use
    :param fuzziness: fuzziness parameter for completion query
    :return: the built Query
    """

    completion_clause = {
        "field": f"names.{lang}",
        "size": size,
        "contexts": {"taxonomy_name": taxonomy_names},
    }

    if fuzziness is not None:
        completion_clause["fuzzy"] = {"fuzziness": fuzziness}

    query = Search(index=config.taxonomy.index.name)
    query = query.suggest(
        "taxonomy_suggest",
        q,
        completion=completion_clause,
    )
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
