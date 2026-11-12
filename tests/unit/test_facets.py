from unittest import mock

import elastic_transport
import elasticsearch
import pytest
from fastapi.testclient import TestClient

from app import facets
from app._types import DistributionChart, QueryAnalysis, SuccessSearchResponse
from app.api import app
from app.charts import build_charts

BRAND_BUCKETS = {
    "buckets": [
        {"key": "en:kellogg-s", "doc_count": 5},
        {"key": "xx:post", "doc_count": 3},
    ],
    "sum_other_doc_count": 0,
}


def _api_error(cls, status: int) -> elasticsearch.ApiError:
    return cls("secret details", mock.MagicMock(status=status), {"error": "secret"})


# the failures of the second Elasticsearch query (the one for names)
LOOKUP_ERRORS = [
    pytest.param(
        elasticsearch.NotFoundError(
            "no such index [off_taxonomy]", mock.MagicMock(status=404), {}
        ),
        id="missing-taxonomy-index",
    ),
    pytest.param(_api_error(elasticsearch.ApiError, 500), id="api-error"),
    pytest.param(_api_error(elasticsearch.BadRequestError, 400), id="bad-request"),
    pytest.param(elastic_transport.ConnectionError("cannot reach es01"), id="down"),
    pytest.param(elastic_transport.ConnectionTimeout("timeout on es01"), id="timeout"),
]


def _failing_lookup(error):
    def get_taxonomy_names(items, config):
        raise error

    return get_taxonomy_names


def _search_result(aggregations) -> SuccessSearchResponse:
    return SuccessSearchResponse(
        hits=[],
        aggregations=aggregations,
        page=1,
        page_size=10,
        page_count=1,
        took=1,
        timed_out=False,
        count=10,
        is_count_exact=True,
    )


@pytest.mark.parametrize("error", LOOKUP_ERRORS)
def test_get_translations_without_names_when_lookup_fails(
    default_config, monkeypatch, caplog, error
):
    monkeypatch.setattr(facets, "get_taxonomy_names", _failing_lookup(error))
    with caplog.at_level("WARNING"):
        translations = facets.get_translations(
            "en", [("en:kellogg-s", "brands")], default_config
        )
    assert translations == {}
    assert "Could not get the names of facet values" in caplog.text
    # only the type of the failure is logged, not its details
    assert "secret" not in caplog.text
    assert "es01" not in caplog.text


def test_get_translations_does_not_hide_other_errors(default_config, monkeypatch):
    """Only Elasticsearch failures are tolerated: a bug must still show"""
    monkeypatch.setattr(
        facets, "get_taxonomy_names", _failing_lookup(KeyError("a bug"))
    )
    with pytest.raises(KeyError):
        facets.get_translations("en", [("en:kellogg-s", "brands")], default_config)


@pytest.mark.parametrize("error", LOOKUP_ERRORS)
def test_build_facets_keeps_ids_when_lookup_fails(default_config, monkeypatch, error):
    monkeypatch.setattr(facets, "get_taxonomy_names", _failing_lookup(error))
    result = _search_result({"brands": BRAND_BUCKETS})

    infos = facets.build_facets(
        result, QueryAnalysis(), "en", default_config, ["brands"]
    )

    assert [(i.key, i.name, i.count) for i in infos["brands"].items] == [
        ("en:kellogg-s", "en:kellogg-s", 5),
        ("xx:post", "xx:post", 3),
    ]


def test_build_charts_keeps_ids_when_lookup_fails(default_config, monkeypatch):
    monkeypatch.setattr(
        facets,
        "get_taxonomy_names",
        _failing_lookup(elastic_transport.ConnectionTimeout("timeout")),
    )
    result = _search_result({"brands": BRAND_BUCKETS})

    charts = build_charts(
        result, default_config, [DistributionChart(field="brands")], "en"
    )

    values = charts["brands"]["data"][0]["values"]
    assert sorted(v["category"] for v in values) == ["en:kellogg-s", "xx:post"]


def test_facets_use_names_when_lookup_works(default_config, monkeypatch):
    """Control: the translation still happens when nothing fails"""
    monkeypatch.setattr(
        facets,
        "get_taxonomy_names",
        lambda items, config: {("en:kellogg-s", "brands"): {"en": "Kellogg's"}},
    )
    result = _search_result({"brands": BRAND_BUCKETS})

    infos = facets.build_facets(
        result, QueryAnalysis(), "en", default_config, ["brands"]
    )

    assert infos["brands"].items[0].name == "Kellogg's"
    assert infos["brands"].items[1].name == "xx:post"


@pytest.mark.parametrize("error", LOOKUP_ERRORS)
@pytest.mark.parametrize("method", ["get", "post"])
def test_search_with_facets_is_200_when_name_lookup_fails(
    default_global_config, monkeypatch, method, error
):
    """The products were found: the search must not turn into a 500"""
    monkeypatch.setattr(facets, "get_taxonomy_names", _failing_lookup(error))
    result = _search_result({"brands": BRAND_BUCKETS})
    client = TestClient(app, raise_server_exceptions=False)
    with mock.patch("app.search.execute_query", return_value=result):
        if method == "get":
            response = client.get("/search", params={"q": "choc", "facets": "brands"})
        else:
            response = client.post("/search", json={"q": "choc", "facets": ["brands"]})

    assert response.status_code == 200
    items = response.json()["facets"]["brands"]["items"]
    assert [i["name"] for i in items] == ["en:kellogg-s", "xx:post"]
