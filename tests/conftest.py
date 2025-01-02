import pytest
from fastapi.testclient import TestClient


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
