from elasticsearch_dsl import Q, Search
from elasticsearch_dsl.query import Query
from luqum import visitor
from luqum.elasticsearch import ElasticsearchQueryBuilder
from luqum.exceptions import ParseSyntaxError
from luqum.parser import parser
from luqum.tree import Word

from app.config import Config, FieldType
from app.types import JSONType


def build_elasticsearch_query_builder(config: Config) -> ElasticsearchQueryBuilder:
    not_analyzed_fields = []
    for field in config.fields:
        if field.type in (FieldType.keyword, FieldType.disabled):
            not_analyzed_fields.append(field.name)

    return ElasticsearchQueryBuilder(
        default_operator=ElasticsearchQueryBuilder.MUST,
        not_analyzed_fields=not_analyzed_fields,
    )


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
    match_phrase_boost_queries = []

    for field in config.fields:
        # We don't include all fields in the multi-match clause, only a subset
        # of them
        if field.include_multi_match:
            if field.has_lang_subfield():
                field_match_phrase_boost_queries = []
                for lang in (_lang for _lang in langs if _lang in supported_langs):
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
    luqum_tree = None
    try:
        luqum_tree = parser.parse(q)
    except ParseSyntaxError:
        # if the lucene syntax is invalid, consider the query as plain text
        remaining_terms = q

    if luqum_tree is not None:
        # We join with space every non word not recognized by the parser
        remaining_terms = " ".join(
            item.value for item in luqum_tree.children if isinstance(item, Word)
        )
        processed_tree = UnknownOperationRemover().visit(luqum_tree)
        filter_query = filter_query_builder(processed_tree)
        filter_clauses = filter_query.get("bool", {}).get("must", [])
    else:
        filter_clauses = []
        remaining_terms = q

    return filter_clauses, remaining_terms


def parse_sort_by_parameter(sort_by: str | None, config: Config) -> str | None:
    if sort_by is None:
        return None

    if negative_operator := sort_by.startswith("-"):
        sort_by = sort_by[1:]

    for field in config.fields:
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
    num_results: int,
    config: Config,
    sort_by: str | None = None,
) -> Query:
    filter_query_builder = build_elasticsearch_query_builder(config)
    filter_clauses, remaining_terms = parse_lucene_dsl_query(q, filter_query_builder)

    query = Search(index=config.index.name)

    if remaining_terms:
        base_multi_match_q = build_query_clause(remaining_terms, langs, config)
        query = query.query(base_multi_match_q)

    if filter_clauses:
        query = query.query("bool", filter=filter_clauses)

    sort_by = parse_sort_by_parameter(sort_by, config)
    if sort_by is not None:
        query = query.sort(sort_by)

    query = query.extra(
        size=num_results,
    )
    return query
