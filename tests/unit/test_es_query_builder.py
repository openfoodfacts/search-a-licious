from unittest import mock

import pytest

from app._types import SearchParameters
from app.es_query_builder import FullTextMixin
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


def test_wildcard_free_text_query_without_fields_matches_nothing(
    default_config, default_filter_query_builder
):
    """An empty `fields` would make ES fall back to every field"""
    with mock.patch.object(
        FullTextMixin, "full_text_query_fields", new_callable=mock.PropertyMock
    ) as fields:
        fields.return_value = []
        analysis = build_search_query(
            SearchParameters(q="mil*", langs=["en"], page_size=5, page=1),
            es_query_builder=default_filter_query_builder,
        )
    assert analysis.es_query.to_dict()["query"] == {"match_none": {}}
