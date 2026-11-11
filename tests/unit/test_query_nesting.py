from unittest import mock

import pytest
from fastapi.testclient import TestClient

from app._types import SuccessSearchResponse
from app.api import app

# from about 330 levels (Python recursion limit of 1000) the transformation of
# the query raises a RecursionError
TOO_DEEP = 400


def _nested(depth: int) -> str:
    return "(" * depth + "milk" + ")" * depth


def _not_chain(count: int) -> str:
    return " ".join(["NOT"] * count) + " milk"


def _success() -> SuccessSearchResponse:
    return SuccessSearchResponse(
        hits=[],
        aggregations={},
        page=1,
        page_size=10,
        page_count=1,
        took=1,
        timed_out=False,
        count=0,
        is_count_exact=True,
    )


@pytest.mark.parametrize("q", [_nested(TOO_DEEP), _not_chain(TOO_DEEP)])
@pytest.mark.parametrize("method", ["get", "post"])
def test_a_query_nested_too_deeply_is_a_client_error(default_global_config, method, q):
    """It used to be an unhandled RecursionError, answered with a 500"""
    client = TestClient(app, raise_server_exceptions=False)
    with mock.patch("app.search.execute_query") as execute:
        if method == "get":
            response = client.get("/search", params={"q": q})
        else:
            response = client.post("/search", json={"q": q})
    assert response.status_code == 400
    error = response.json()["errors"][0]
    assert error["title"] == "QueryTooComplexError"
    assert error["status"] == 400
    assert "nested too deeply" in error["description"]
    # no search is sent to Elasticsearch
    execute.assert_not_called()


@pytest.mark.parametrize("q", [_nested(100), _not_chain(100), "milk"])
def test_a_query_with_reasonable_nesting_is_searched(default_global_config, q):
    """Control: nothing changes for the queries that worked"""
    client = TestClient(app, raise_server_exceptions=False)
    with mock.patch("app.search.execute_query", return_value=_success()) as execute:
        response = client.get("/search", params={"q": q})
    assert response.status_code == 200
    execute.assert_called_once()


def test_the_error_does_not_break_the_next_requests(default_global_config):
    client = TestClient(app, raise_server_exceptions=False)
    with mock.patch("app.search.execute_query", return_value=_success()):
        assert client.get("/search", params={"q": _nested(TOO_DEEP)}).status_code == 400
        assert client.get("/search", params={"q": "milk"}).status_code == 200
