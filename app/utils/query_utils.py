from __future__ import annotations

from elasticsearch_dsl import Q

from app.config import Config
from app.models.product import Product


def get_nesting_segments(path):
    # For A.B.C, we need to create a nested query A { B { C [where C is in the input query]. We do this by walking
    # backwards through the list
    segments = path.split(".")
    # Remove the last element
    segments.pop()
    return segments


def add_nesting(path, query):
    if "." not in path:
        return query

    for segment in list(reversed(get_nesting_segments(path))):
        query = Q("nested", path=segment, query=query)
    return query


def create_query(query_type, field, value):
    return add_nesting(field, Q(query_type, **{field: value}))


def create_range_query(query):
    assert len(query.keys()) == 1
    path = list(query.keys())[0]
    return add_nesting(path, {"range": query})


def build_multi_match_query(query: str, langs: set[str], config: Config):
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


def build_search_query(q: str, langs: set[str], num_results: int, config: Config):
    base_multi_match_q = build_multi_match_query(q, langs, config)
    query = (
        Product.search()
        .query(base_multi_match_q)
        .extra(
            size=num_results,
        )
    )
    return query
