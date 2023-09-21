from elasticsearch_dsl import Q, Search
from elasticsearch_dsl.query import Query
from luqum import visitor
from luqum.elasticsearch import ElasticsearchQueryBuilder
from luqum.exceptions import ParseSyntaxError
from luqum.parser import parser
from luqum.tree import Word

from app.config import Config, FieldType
from app.types import JSONType


def build_elasticsearch_query_builder(config: Config):
    not_analyzed_fields = []
    for field in config.fields:
        if field.type == FieldType.keyword:
            not_analyzed_fields.append(field.name)

    return ElasticsearchQueryBuilder(not_analyzed_fields=not_analyzed_fields)


class UnknownOperationRemover(visitor.TreeTransformer):
    def __init__(self):
        super().__init__(track_parents=True)

    def visit_unknown_operation(self, node, context):
        for item in node.children:
            if not isinstance(item, Word):
                new_item = item.clone_item()
                new_item.children = self.clone_children(item, new_item, context)
                yield new_item

    def __call__(self, tree):
        return self.visit(tree)


def build_query_clause(query: str, langs: set[str], config: Config) -> Query:
    fields = []
    supported_langs = config.get_supported_langs()
    match_phrase_boost_queries = []

    for field in config.fields:
        # We don't include all fields in the multi-match clause, only a subset of them
        if field.include_multi_match:
            if field.has_lang_subfield():
                field_match_phrase_boost_queries = []
                for lang in (l for l in langs if l in supported_langs):
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


def parse_lucene_dsl_query(q: str, config: Config) -> tuple[list[JSONType], str]:
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
        filter_query_builder = build_elasticsearch_query_builder(config)
        filter_clauses = (
            filter_query_builder(processed_tree).get("bool", {}).get("must", [])
        )
    else:
        filter_clauses = []
        remaining_terms = q

    return filter_clauses, remaining_terms


def build_search_query(
    q: str, langs: set[str], num_results: int, config: Config
) -> Query:
    filter_clauses, remaining_terms = parse_lucene_dsl_query(q, config)

    query = Search(index=config.index.name)

    if remaining_terms:
        base_multi_match_q = build_query_clause(remaining_terms, langs, config)
        query = query.query(base_multi_match_q)

    if filter_clauses:
        query = query.query("bool", filter=filter_clauses)

    query = query.extra(
        size=num_results,
    )
    return query
