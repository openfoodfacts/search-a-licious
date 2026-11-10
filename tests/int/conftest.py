import pathlib
import time

import pytest
import yaml

import app.config
import app.utils.connection
from app.config import settings
from app.search_client import ConnectionError_

from .data_generation import (
    delete_es_indices,
    delete_es_synonyms,
    ingest_data,
    ingest_taxonomies,
    load_state,
    save_state,
)

DATA_DIR = pathlib.Path(__file__).parent / "data"
DEFAULT_CONFIG_PATH = DATA_DIR / "test_off.yml"


@pytest.fixture(scope="session")
def test_off_config(tmp_path_factory):
    """Fixture that sets default config to DEFAULT_CONFIG_PATH

    With OpenSearch (no synonyms sets API), synonyms are disabled.
    """
    config_path = DEFAULT_CONFIG_PATH
    if settings.search_engine == "opensearch":
        data = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text())
        for index in data["indices"].values():
            index["synonyms_strategy"] = "none"
        config_path = tmp_path_factory.mktemp("config") / "test_off.yml"
        config_path.write_text(yaml.safe_dump(data))
    return app.config.set_global_config(config_path)


@pytest.fixture(scope="session")
def index_config(test_off_config):
    """Fixture that returns the IndexConfig corresponding to test_off."""
    return test_off_config.get_index_config("test_off")[1]


ES_MAX_WAIT = 60  # 1 minute


class _NotReady(Exception):
    """The search engine is up but not ready yet"""


@pytest.fixture(scope="session")
def es_connection(test_off_config):
    """Fixture that get's a connection to the search engine"""
    es = None
    waited = 0
    while es is None:
        try:
            es = app.utils.connection.get_es_client()
            health = es.cluster.health()
            if health.get("status") != "green":
                raise _NotReady("Search engine not ready")
            return es
        except (ConnectionError_, _NotReady):
            waited += 1
            if waited > ES_MAX_WAIT:
                raise
            time.sleep(1)
            es = None


@pytest.fixture
def synonyms_created(index_config, es_connection):
    """A feature to ensure synonyms file are created"""
    ingest_taxonomies("test_off", index_config, es_connection)


@pytest.fixture(scope="session")
def data_ingester(index_config, es_connection, clean_es):
    """Return a feature to ingest data

    It will cleanup ES if requested by --clean-es option.

    It will ingest taxonomies and data, if needed, or use previous created indexes.
    """
    if clean_es:
        delete_es_indices(es_connection)
        if settings.search_engine != "opensearch":
            delete_es_synonyms(es_connection)
    else:
        load_state("test_off", index_config, es_connection)

    def _ingester(data, read_only=True):
        """The implementation of data ingestion

        if you test modifies the index, you should set read_only=False
        """
        ingest_taxonomies("test_off", index_config, es_connection)
        ingest_data(data, "test_off", index_config, es_connection, read_only=read_only)
        save_state("test_off", index_config, es_connection)

    return _ingester
