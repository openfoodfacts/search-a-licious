import pytest

from app._types import SearchParameters
from app.query import build_search_query


@pytest.mark.parametrize("q", ["mil*", "milk?", "*ilk"])
def test_wildcard_free_text_query_has_no_default_field(
    q, default_config, default_filter_query_builder
):
    """Elasticsearch rejects a query_string with both `default_field` and `fields`"""
    analysis = build_search_query(
        SearchParameters(q=q, langs=["en"], page_size=5, page=1, boost_phrase=False),
        es_query_builder=default_filter_query_builder,
    )
    query_string = analysis.es_query.to_dict()["query"]["query_string"]

    assert "default_field" not in query_string
    assert "product_name.en" in query_string["fields"]
