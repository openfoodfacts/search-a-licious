import pathlib
import time

import elasticsearch
import pytest

import app.config
import app.utils.connection

DATA_DIR = pathlib.Path(__file__).parent / "data"
DEFAULT_CONFIG_PATH = DATA_DIR / "test_off.yml"


@pytest.fixture(scope="module")
def test_off_config():
    """Fixture that sets default config to DEFAULT_CONFIG_PATH"""
    return app.config.set_global_config(DEFAULT_CONFIG_PATH)


@pytest.fixture
def es_connection(test_off_config):
    """Fixture that get's an Elasticsearch connection"""
    es = None
    waited = 0
    while es is None:
        try:
            es = app.utils.connection.get_es_client()
            health = es.cluster.health()
            if health.get("status") != "green":
                raise elasticsearch.exceptions.ConnectionError(
                    "Elasticsearch not ready"
                )
            return es
        except elasticsearch.exceptions.ConnectionError:
            waited += 1
            if waited > 10:
                raise
            time.sleep(1)
