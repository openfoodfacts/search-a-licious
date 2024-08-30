import pytest


def pytest_addoption(parser):
    """Add an option to update test result JSON files."""
    parser.addoption("--update-results", action="store_true", default=False)


@pytest.fixture
def update_results(request):
    """fixture to get the value of the --update-results flag

    It helps decide whether test should compare results to strode one
    or update them
    """
    return request.config.getoption("--update-results")
