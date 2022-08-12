from __future__ import annotations

from elasticsearch_dsl import Q


def get_nesting_segments(path):
    # For A.B.C, we need to create a nested query A { B { C [where C is in the input query]. We do this by walking
    # backwards through the list
    segments = path.split('.')
    # Remove the last element
    segments.pop()
    return segments


def add_nesting(path, query):
    if '.' not in path:
        return query

    for segment in list(reversed(get_nesting_segments(path))):
        query = Q('nested', path=segment, query=query)
    return query


def create_query(query_type, field, value):
    return add_nesting(field, Q(query_type, **{field: value}))


def create_range_query(query):
    assert len(query.keys()) == 1
    path = list(query.keys())[0]
    return add_nesting(path, {'range': query})
