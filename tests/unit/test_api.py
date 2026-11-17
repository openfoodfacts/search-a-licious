from unittest import mock

import elastic_transport
import elasticsearch
import pytest
import starlette.status as status
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app._types import (
    ErrorSearchResponse,
    GetSearchParameters,
    PostSearchParameters,
    SearchResponseDebug,
    SearchResponseError,
    SuccessSearchResponse,
)
from app.api import app, status_for_response


def _error_response(title: str) -> ErrorSearchResponse:
    return ErrorSearchResponse(
        debug=SearchResponseDebug(),
        errors=[SearchResponseError(title=title, description="test")],
    )


def test_status_for_response_client_query_error_is_400():
    result = _error_response("InvalidLuceneQueryError")
    assert status_for_response(result) == status.HTTP_400_BAD_REQUEST


def test_status_for_response_value_error_is_400():
    result = _error_response("ValueError")
    assert status_for_response(result) == status.HTTP_400_BAD_REQUEST


def test_status_for_response_explicit_status_code():
    result = ErrorSearchResponse(
        debug=SearchResponseDebug(),
        errors=[
            SearchResponseError(
                title="es_api_error", description="bad range", status=400
            )
        ],
    )
    assert status_for_response(result) == status.HTTP_400_BAD_REQUEST


def test_status_for_response_es_error_is_503():
    result = _error_response("es_connection_error")
    assert status_for_response(result) == status.HTTP_503_SERVICE_UNAVAILABLE


def test_status_for_response_unknown_error_is_500():
    result = _error_response("SomeUnknownError")
    assert status_for_response(result) == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.parametrize("params_cls", [GetSearchParameters, PostSearchParameters])
@pytest.mark.parametrize(
    "pagination",
    [{"page_size": 0}, {"page_size": -5}, {"page": 0}, {"page": -1}],
)
def test_search_parameters_reject_invalid_pagination(
    default_config, params_cls, pagination
):
    with pytest.raises(ValidationError) as exc_info:
        params_cls(q="milk", **pagination)
    assert exc_info.value.errors()[0]["type"] == "greater_than_equal"


def test_search_parameters_accept_minimal_pagination(default_config):
    params = GetSearchParameters(q="milk", page=1, page_size=1)
    assert (params.page, params.page_size) == (1, 1)


def _success_response(hits: list[dict]) -> SuccessSearchResponse:
    return SuccessSearchResponse(
        hits=hits,
        page=1,
        page_size=24,
        page_count=1,
        took=3,
        timed_out=False,
        count=len(hits),
        is_count_exact=True,
        debug=SearchResponseDebug(es_query={"match_all": {}}),
    )


def test_off_test_page_without_query_is_the_search_form():
    response = TestClient(app).get("/off-test")
    assert response.status_code == 200


def test_off_test_page_displays_results(default_config):
    """The demo page used to fail with a TypeError as soon as `q` was given"""
    result = _success_response([{"code": "123", "product_name": "Whole milk"}])
    with mock.patch("app.api.app_search.search", return_value=result) as search:
        response = TestClient(app).get("/off-test?q=milk&langs=fr,en&page_size=5")

    assert response.status_code == 200
    assert "Whole milk" in response.text
    parameters = search.call_args.args[0]
    assert isinstance(parameters, GetSearchParameters)
    assert (parameters.q, parameters.langs, parameters.page_size) == (
        "milk",
        ["fr", "en"],
        5,
    )


def test_off_test_page_displays_search_errors(default_config):
    result = _error_response("InvalidLuceneQueryError")
    with mock.patch("app.api.app_search.search", return_value=result):
        response = TestClient(app).get("/off-test?q=milk")
    assert response.status_code == 200
    assert "InvalidLuceneQueryError" in response.text


def _es_api_error(status_code: int) -> elasticsearch.ApiError:
    return elasticsearch.ApiError(
        "secret details", mock.MagicMock(status=status_code), {"error": "secret"}
    )


ES_ERRORS = [
    (elastic_transport.ConnectionError("cannot connect to es01"), 503),
    (elastic_transport.ConnectionTimeout("timeout on es01"), 503),
    (_es_api_error(500), 503),
    (_es_api_error(400), 400),
]


@pytest.mark.parametrize("error,expected_status", ES_ERRORS)
def test_document_elasticsearch_failure(default_config, error, expected_status):
    with mock.patch("app.api.Search") as search:
        search.return_value.query.return_value.extra.return_value.execute.side_effect = (
            error
        )
        response = TestClient(app).get("/document/123")
    assert response.status_code == expected_status
    # no detail of the failure is given to the client
    assert "secret" not in response.text
    assert "es01" not in response.text


@pytest.mark.parametrize("error,expected_status", ES_ERRORS)
def test_autocomplete_elasticsearch_failure(default_config, error, expected_status):
    with mock.patch("app.api.build_completion_query") as build:
        build.return_value.execute.side_effect = error
        response = TestClient(app).get("/autocomplete?q=mil&taxonomy_names=categories")
    assert response.status_code == expected_status
    assert "secret" not in response.text
    assert "es01" not in response.text


def test_autocomplete_missing_taxonomy_index_message_is_kept(default_config):
    error = elasticsearch.NotFoundError("no index", mock.MagicMock(status=404), {})
    with mock.patch("app.api.build_completion_query") as build:
        build.return_value.execute.side_effect = error
        response = TestClient(app).get("/autocomplete?q=mil&taxonomy_names=categories")
    assert response.status_code == 500
    assert "taxonomies need to be imported" in response.text


@pytest.mark.parametrize(
    "error",
    [
        elastic_transport.ConnectionError("cannot connect to es01"),
        elastic_transport.ConnectionTimeout("timeout on es01"),
    ],
)
def test_search_unreachable_backend_is_503(default_global_config, error):
    """A search timeout used to be an unhandled error (HTTP 500)"""
    client = TestClient(app, raise_server_exceptions=True)
    with mock.patch("elasticsearch_dsl.Search.execute", side_effect=error):
        response = client.get("/search?q=milk")
    assert response.status_code == 503
    assert response.json()["errors"][0]["title"] == "es_connection_error"


@pytest.mark.parametrize(
    "extra_get, extra_post",
    [
        ({}, {}),
        ({"facets": "brands_tags"}, {"facets": ["brands_tags"]}),
        (
            {"charts": "brands_tags"},
            {"charts": [{"chart_type": "DistributionChart", "field": "brands_tags"}]},
        ),
        (
            {"charts": "nova_group:unique_scans_n"},
            {
                "charts": [
                    {
                        "chart_type": "ScatterChart",
                        "x": "nova_group",
                        "y": "unique_scans_n",
                    }
                ]
            },
        ),
        ({"sort_by": "-unique_scans_n"}, {"sort_by": "-unique_scans_n"}),
    ],
)
@pytest.mark.parametrize("method", ["get", "post"])
def test_search_unknown_index_id_is_422(
    default_global_config, method, extra_get, extra_post
):
    """An unknown index_id is a client error, not an unhandled KeyError (500)"""
    client = TestClient(app, raise_server_exceptions=True)
    if method == "get":
        response = client.get(
            "/search", params={"q": "milk", "index_id": "unknown", **extra_get}
        )
    else:
        response = client.post(
            "/search", json={"q": "milk", "index_id": "unknown", **extra_post}
        )
    assert response.status_code == 422
    assert "Index ID 'unknown' not found" in response.text


def test_autocomplete_empty_query_is_422(default_global_config):
    """An empty query used to crash in elasticsearch_dsl (KeyError, 500)"""
    client = TestClient(app, raise_server_exceptions=True)
    response = client.get("/autocomplete?q=&taxonomy_names=categories")
    assert response.status_code == 422
