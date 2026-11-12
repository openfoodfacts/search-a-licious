import socket
import threading
import time

import elastic_transport
import pytest
from elasticsearch_dsl.connections import connections
from fastapi.testclient import TestClient

from app.api import app
from app.config import Settings, settings
from app.utils import connection


def test_elasticsearch_request_timeout_setting(monkeypatch):
    # the default is the one of the Elasticsearch client
    assert Settings().elasticsearch_request_timeout == 10.0
    monkeypatch.setenv("ELASTICSEARCH_REQUEST_TIMEOUT", "2.5")
    assert Settings().elasticsearch_request_timeout == 2.5
    monkeypatch.setenv("ELASTICSEARCH_REQUEST_TIMEOUT", "0")
    with pytest.raises(ValueError):
        Settings()


@pytest.fixture
def silent_elasticsearch(monkeypatch):
    """A server that accepts connections and never answers,
    registered as the default connection with a 1 second timeout"""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    clients = []

    def accept():
        while True:
            try:
                clients.append(server.accept()[0])
            except OSError:
                return

    threading.Thread(target=accept, daemon=True).start()
    monkeypatch.setattr(
        settings, "elasticsearch_url", f"http://127.0.0.1:{server.getsockname()[1]}"
    )
    monkeypatch.setattr(settings, "elasticsearch_request_timeout", 1.0)
    previous = connections._conns.get("default")
    connection.get_api_es_client()
    yield
    if previous is None:
        connections._conns.pop("default", None)
    else:
        connections._conns["default"] = previous
    server.close()
    for client in clients:
        client.close()


def test_api_client_gives_up_after_the_configured_timeout(silent_elasticsearch):
    es = connection.current_es_client()
    start = time.monotonic()
    with pytest.raises(elastic_transport.ConnectionTimeout):
        es.search(index="some-index")
    # not the 10 seconds of the client default
    assert 0.9 <= time.monotonic() - start < 4


def test_search_answers_503_after_the_configured_timeout(
    silent_elasticsearch, default_global_config
):
    client = TestClient(app, raise_server_exceptions=True)
    start = time.monotonic()
    response = client.get("/search", params={"q": "milk"})
    assert response.status_code == 503
    assert time.monotonic() - start < 4
