from pathlib import Path

import orjson
import pytest

from app._types import JSONType
from app.config import Config
from app.query import build_elasticsearch_query_builder
from app.utils.io import dump_json, load_json

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_CONFIG_PATH = DATA_DIR / "openfoodfacts_config.yml"


@pytest.fixture
def default_config():
    """Fixture that returns default Open Food Facts index configuration for
    tests."""
    yield Config.from_yaml(DEFAULT_CONFIG_PATH).indices["off"]


@pytest.fixture
def default_global_config():
    """Fixture that returns default global configuration for tests."""
    yield Config.from_yaml(DEFAULT_CONFIG_PATH)


@pytest.fixture
def default_filter_query_builder(default_config):
    """Fixture that returns Luqum elasticsearch query builder based on default
    config."""
    yield build_elasticsearch_query_builder(default_config)


@pytest.fixture
def load_expected_result(update_results):
    """Return a helper function to load expected results of a test
    or eventually save them."""

    def load_expected_result_fn(test_id: str, data: JSONType):
        if update_results:
            dump_json(DATA_DIR / f"{test_id}.json", data, option=orjson.OPT_INDENT_2)
        elif not (DATA_DIR / f"{test_id}.json").exists():
            raise RuntimeError(
                f"No result file for {test_id}, "
                "maybe you need to first run with --update-results."
            )
        return load_json(DATA_DIR / f"{test_id}.json")

    return load_expected_result_fn
