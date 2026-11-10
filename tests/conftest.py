import pytest
from fastapi.testclient import TestClient

from app.config import settings


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requires_synonyms_sets: needs the Elasticsearch synonyms sets API, "
        "skipped with OpenSearch",
    )


def pytest_collection_modifyitems(config, items):
    """Skip the tests that need the Elasticsearch synonyms sets API on OpenSearch"""
    if settings.search_engine != "opensearch":
        return
    skip = pytest.mark.skip(reason="synonyms sets API is not available on OpenSearch")
    for item in items:
        if "requires_synonyms_sets" in item.keywords:
            item.add_marker(skip)


def pytest_addoption(parser):
    """Add an option to update test result JSON files,
    and another to clean Elasticsearch indexes
    """
    parser.addoption("--update-results", action="store_true", default=False)
    parser.addoption("--clean-es", action="store_true", default=False)


@pytest.fixture(scope="session")
def update_results(request):
    """fixture to get the value of the --update-results flag

    It helps decide whether test should compare results to strode one
    or update them
    """
    return request.config.getoption("--update-results")


@pytest.fixture(scope="session")
def clean_es(request):
    """fixture to get the value of the --clean-es flag"""
    return request.config.getoption("--clean-es")


@pytest.fixture
def test_client():
    """Provide a test client on the API"""
    from app.api import app

    return TestClient(app)
