from unittest import mock

import pytest

from app._types import SearchParameters
from app.es_query_builder import FullTextMixin
from app.exceptions import FreeRangeError
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


def _build(q, builder, **kwargs):
    return build_search_query(
        SearchParameters(q=q, langs=["en"], page_size=5, page=1, **kwargs),
        es_query_builder=builder,
    )


@pytest.mark.parametrize("q,fuzziness", [("milk~1", 1), ("milk~", "AUTO")])
def test_fuzzy_free_text_query_searches_all_fields(
    q, fuzziness, default_config, default_filter_query_builder
):
    """A fuzzy word must be a full text search, as a plain word is"""
    query = _build(q, default_filter_query_builder).es_query.to_dict()["query"]

    multi_match = query["multi_match"]
    assert multi_match["query"] == "milk"
    assert multi_match["type"] == "best_fields"
    assert multi_match["fuzziness"] == fuzziness
    assert "product_name.en" in multi_match["fields"]
    assert "fuzzy" not in query


def test_fuzzy_free_text_query_combines_with_other_terms(
    default_config, default_filter_query_builder
):
    query = _build("milk~2 sugar", default_filter_query_builder).es_query.to_dict()[
        "query"
    ]
    clauses = query["bool"]["must"]
    assert clauses[0]["multi_match"]["fuzziness"] == 2
    assert clauses[1]["multi_match"]["query"] == "sugar"


def test_fuzzy_free_text_query_without_fields_matches_nothing(
    default_config, default_filter_query_builder
):
    with mock.patch.object(
        FullTextMixin, "full_text_query_fields", new_callable=mock.PropertyMock
    ) as fields:
        fields.return_value = []
        query = _build("milk~1", default_filter_query_builder).es_query.to_dict()
    assert query["query"] == {"match_none": {}}


def test_fuzzy_on_a_field_is_unchanged(default_config, default_filter_query_builder):
    query = _build("product_name:milk~1", default_filter_query_builder).es_query
    assert query.to_dict()["query"] == {
        "fuzzy": {"product_name.en": {"fuzziness": 1.0, "value": "milk"}}
    }


@pytest.mark.parametrize("q", ["[1 TO 2]", "{1 TO 5}", ">3", "milk NOT [1 TO 2]"])
def test_free_text_range_is_refused(q, default_config, default_filter_query_builder):
    """A range on the placeholder field would silently match nothing"""
    with pytest.raises(FreeRangeError, match="specify a field"):
        _build(q, default_filter_query_builder)


def test_range_on_a_field_still_works(default_config, default_filter_query_builder):
    query = _build("nutriments.fat_100g:[1 TO 2]", default_filter_query_builder)
    assert query.es_query.to_dict()["query"] == {
        "range": {"nutriments.fat_100g": {"gte": "1", "lte": "2"}}
    }
