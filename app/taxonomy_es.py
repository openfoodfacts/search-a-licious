"""Operations on taxonomies in ElasticSearch

See also :py:mod:`app.taxonomy`
"""

from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Q

from app.config import IndexConfig


def get_taxonomy_names(
    items: list[tuple[str, str]],
    config: IndexConfig,
) -> dict[tuple[str, str], dict[str, list[str]]]:
    """Given a set of terms in different taxonomies, return their names"""
    filters = []
    for id, taxonomy_name in items:
        # match one term
        filters.append(Q("term", id=id) & Q("term", taxonomy_name=taxonomy_name))
    query = (
        Search(index=config.taxonomy.index.name)
        .filter("bool", should=filters, minimum_should_match=1)
        .params(size=len(filters))
    )
    return {
        (result.id, result.taxonomy_name): result.names.to_dict()
        for result in query.execute().hits
    }
