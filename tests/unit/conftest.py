from pathlib import Path

import pytest

from app.config import Config
from app.query import build_elasticsearch_query_builder

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_CONFIG_PATH = DATA_DIR / "openfoodfacts_config.yml"


@pytest.fixture
def default_config():
    """Fixture that returns default Open Food Facts configuration for tests."""
    yield Config.from_yaml(DEFAULT_CONFIG_PATH)


@pytest.fixture
def default_filter_query_builder(default_config):
    """Fixture that returns Luqum elasticsearch query builder based on default
    config."""
    yield build_elasticsearch_query_builder(default_config)
