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


def _es_api_error(status_code: int) -> elasticsearch.ApiError:
    return elasticsearch.ApiError(
        "secret details", mock.MagicMock(status=status_code), {"error": "secret"}
    )


ES_ERRORS = [
    (elastic_transport.ConnectionError("cannot connect to es01"), 503),
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
