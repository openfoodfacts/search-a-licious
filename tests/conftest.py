import pytest


def pytest_addoption(parser):
    """Add an option to update test result JSON files."""
    parser.addoption("--update-results", action="store_true", default=False)


@pytest.fixture
def update_results(request):
    return request.config.getoption("--update-results")
