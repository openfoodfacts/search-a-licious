from unittest import mock

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
