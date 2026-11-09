import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import app

ORIGIN = {"Origin": "https://example.org"}


@pytest.fixture(scope="module")
def client():
    @app.get("/test-unhandled-error")
    def unhandled_error():
        raise RuntimeError("boom")

    @app.get("/test-http-error")
    def http_error():
        raise HTTPException(status_code=418, detail="teapot")

    yield TestClient(app, raise_server_exceptions=False)
    app.router.routes = [
        r
        for r in app.router.routes
        if getattr(r, "path", "") not in ("/test-unhandled-error", "/test-http-error")
    ]


def test_unhandled_error_is_500_with_cors_headers(client):
    response = client.get("/test-unhandled-error", headers=ORIGIN)
    assert response.status_code == 500
    err = response.json()
    assert list(err.keys()) == ["detail"]
    assert response.json()["detail"].startswith("Internal Server Error")
    # without it, browsers report a CORS error instead of the real failure
    assert response.headers["access-control-allow-origin"] == ORIGIN["Origin"]


def test_http_error_keeps_its_status_and_cors_headers(client):
    response = client.get("/test-http-error", headers=ORIGIN)
    assert response.status_code == 418
    assert response.json() == {"detail": "teapot"}
    assert response.headers["access-control-allow-origin"] == ORIGIN["Origin"]
