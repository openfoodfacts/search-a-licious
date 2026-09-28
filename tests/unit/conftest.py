import json
from pathlib import Path

import pytest

from app import config as app_config
from app._types import JSONType
from app.config import Config
from app.query import build_elasticsearch_query_builder
from app.utils.io import load_json

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_CONFIG_PATH = DATA_DIR / "openfoodfacts_config.yml"


@pytest.fixture
def default_config():
    """Fixture that returns default Open Food Facts index configuration for
    tests."""
    conf = Config.from_yaml(DEFAULT_CONFIG_PATH)
    previous_conf = app_config._CONFIG
    app_config._CONFIG = conf
    yield conf.indices["off"]
    app_config._CONFIG = previous_conf


@pytest.fixture
def default_global_config():
    """Fixture that returns default global configuration for tests."""
    conf = Config.from_yaml(DEFAULT_CONFIG_PATH)
    previous_conf = app_config._CONFIG
    app_config._CONFIG = conf
    yield conf
    app_config._CONFIG = previous_conf


@pytest.fixture
def default_filter_query_builder(default_config):
    """Fixture that returns Luqum elasticsearch query builder based on default
    config."""
    yield build_elasticsearch_query_builder(default_config)


@pytest.fixture
def query_builder_cache_is_empty():
    """Fixture that ensures the query builder cache is empty
    before and after a test, so we don't get one from a previous test
    """
    from app.search import _ES_QUERY_BUILDERS

    _ES_QUERY_BUILDERS.clear()
    yield
    _ES_QUERY_BUILDERS.clear()


@pytest.fixture
def load_expected_result(update_results):
    """Return a helper function to load expected results of a test
    or eventually save them."""

    def load_expected_result_fn(test_id: str, data: JSONType):
        if update_results:
            with open(DATA_DIR / f"{test_id}.json", "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)
        elif not (DATA_DIR / f"{test_id}.json").exists():
            raise RuntimeError(
                f"No result file for {test_id}, "
                "maybe you need to first run with --update-results."
            )
        return load_json(DATA_DIR / f"{test_id}.json")

    return load_expected_result_fn
