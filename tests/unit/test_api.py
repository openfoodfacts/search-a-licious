import pytest
import starlette.status as status
from pydantic import ValidationError

from app._types import (
    ErrorSearchResponse,
    GetSearchParameters,
    PostSearchParameters,
    SearchResponseDebug,
    SearchResponseError,
)
from app.api import status_for_response


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
