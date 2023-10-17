import elastic_transport
from elasticsearch_dsl import Q, Search
from elasticsearch_dsl.query import Query
from luqum import visitor
from luqum.elasticsearch import ElasticsearchQueryBuilder
from luqum.elasticsearch.schema import SchemaAnalyzer
from luqum.exceptions import ParseSyntaxError
from luqum.parser import parser
from luqum.tree import UnknownOperation, Word

from app.config import Config, FieldType
from app.indexing import generate_index_object
from app.postprocessing import BaseResultProcessor
from app.types import (
    ErrorSearchResponse,
    JSONType,
    SearchResponse,
    SearchResponseDebug,
    SearchResponseError,
    SuccessSearchResponse,
)
from app.utils import get_logger

logger = get_logger(__name__)


def build_elasticsearch_query_builder(config: Config) -> ElasticsearchQueryBuilder:
    index = generate_index_object(config.index.name, config)
    options = SchemaAnalyzer(index.to_dict()).query_builder_options()
    options["default_operator"] = ElasticsearchQueryBuilder.MUST
    return ElasticsearchQueryBuilder(**options)


class UnknownOperationRemover(visitor.TreeTransformer):
    def __init__(self):
        super().__init__(track_parents=True)

    def visit_unknown_operation(self, node, context):
        new_node = node.clone_item()
        children = [
            child
            for child in self.clone_children(node, new_node, context)
            if not isinstance(child, Word)
        ]
        new_node.children = children
        yield new_node

    def __call__(self, tree):
        return self.visit(tree)


def build_query_clause(query: str, langs: set[str], config: Config) -> Query:
    fields = []
    supported_langs = config.get_supported_langs()
    taxonomy_langs = config.get_taxonomy_langs()
    match_phrase_boost_queries = []

    for field in config.fields.values():
        # We don't include all fields in the multi-match clause, only a subset
        # of them
        if field.include_multi_match:
            if field.type in (FieldType.taxonomy, FieldType.text_lang):
                # language subfields are not the same depending on whether the
                # field is a `taxonomy` or a `text_lang` field
                langs_subset = (
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


def parse_lucene_dsl_query(
    q: str, filter_query_builder: ElasticsearchQueryBuilder
) -> tuple[list[JSONType], str]:
    """Parse query using Lucene DSL.

    We decompose the query into two parts:

    - a Lucene DSL query, which is used as a filter clause in the
      Elasticsearch query. Luqum library is used to transform the
      Lucene DSL into Elasticsearch DSL.
    - remaining terms, used for full text search.

    :param q: the user query
    :param filter_query_builder: Luqum query builder
    :return: a tuple containing the Elasticsearch filter clause and
      the remaining terms for full text search
    """
    luqum_tree = None
    remaining_terms = ""
    try:
        luqum_tree = parser.parse(q)
    except ParseSyntaxError as e:
        # if the lucene syntax is invalid, consider the query as plain text
        logger.warning("parsing error for query: '%s':\n%s", q, e)
        remaining_terms = q

    if luqum_tree is not None:
        # Successful parsing
        logger.debug("parsed luqum tree: %s", repr(luqum_tree))
        if isinstance(luqum_tree, UnknownOperation):
            # We join with space every non word not recognized by the parser
            remaining_terms = " ".join(
                item.value for item in luqum_tree.children if isinstance(item, Word)
            )
        elif isinstance(luqum_tree, Word):
            # single term
            remaining_terms = luqum_tree.value

        processed_tree = UnknownOperationRemover().visit(luqum_tree)
        logger.debug("processed luqum tree: %s", repr(processed_tree))
        if processed_tree.children:
            filter_query = filter_query_builder(processed_tree)
        else:
            filter_query = None
        logger.debug("filter query from luqum: '%s'", filter_query)
    else:
        filter_query = None
        remaining_terms = q

    return filter_query, remaining_terms


def parse_sort_by_parameter(sort_by: str | None, config: Config) -> str | None:
    """Parse `sort_by` parameter, special handling is performed for `text_lang`
    subfield.

    :param sort_by: the raw `sort_by` value
    :param config: the Config to use
    :return: None if `sort_by` is not provided or the final value otherwise
    """
    if sort_by is None:
        return None

    if negative_operator := sort_by.startswith("-"):
        sort_by = sort_by[1:]

    for field in config.fields.values():
        if field.name == sort_by:
            if field.type is FieldType.text_lang:
                # use 'main' language subfield for sorting
                sort_by = f"{field.name}.main"
                break

    if negative_operator:
        sort_by = f"-{sort_by}"

    return sort_by


def build_search_query(
    q: str,
    langs: set[str],
    size: int,
    page: int,
    config: Config,
    filter_query_builder: ElasticsearchQueryBuilder,
    sort_by: str | None = None,
) -> Query:
    """Build an elasticsearch_dsl Query.

    :param q: the user raw query
    :param langs: the set of languages we want to support, it is used to
      select language subfields for some field types
    :param size: number of results to return
    :param page: requested page (starts at 1).
    :param config: configuration to use
    :param filter_query_builder: luqum elasticsearch query builder
    :param sort_by: sorting key, defaults to None (=relevance-based sorting)
    :return: the built Query
    """
    filter_query, remaining_terms = parse_lucene_dsl_query(q, filter_query_builder)
    logger.debug("filter query: %s", filter_query)
    logger.debug("remaining terms: '%s'", remaining_terms)

    query = Search(index=config.index.name)

    if remaining_terms:
        base_multi_match_q = build_query_clause(remaining_terms, langs, config)
        query = query.query(base_multi_match_q)

    if filter_query:
        query = query.query("bool", filter=filter_query)

    sort_by = parse_sort_by_parameter(sort_by, config)
    if sort_by is not None:
        query = query.sort(sort_by)

    query = query.extra(
        size=size,
        from_=size * (page - 1),
    )
    return query


def execute_query(
    query: Query,
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
