from types import SimpleNamespace
from unittest import mock

import pytest

from app._types import DistributionChart, GetSearchParameters, ScatterChart
from app.config import FieldConfig, Settings, settings
from app.validations import check_fields_are_numeric


def test_get_search_parameters_accepts_no_charts(default_global_config):
    params = GetSearchParameters(q="milk", charts=None)

    assert params.charts is None


def test_get_search_parameters_parses_distribution_chart(default_global_config):
    params = GetSearchParameters(q="milk", charts="categories")

    assert params.charts == [DistributionChart(field="categories")]


def test_get_search_parameters_parses_scatter_chart(default_global_config):
    params = GetSearchParameters(q="milk", charts="unique_scans_n:completeness")

    assert params.charts == [
        ScatterChart(x="unique_scans_n", y="completeness"),
    ]


def test_get_search_parameters_preserves_structured_charts(default_global_config):
    charts = [DistributionChart(field="categories")]

    params = GetSearchParameters(q="milk", charts=charts)

    assert params.charts == charts


def test_get_search_parameters_accepts_empty_string_charts(default_global_config):
    params = GetSearchParameters(q="milk", charts="")

    assert params.charts == []


def test_get_search_parameters_accepts_empty_list_charts(default_global_config):
    params = GetSearchParameters(q="milk", charts=[])

    assert params.charts == []


def test_get_search_parameters_accepts_omitted_charts(default_global_config):
    params = GetSearchParameters(q="milk")

    assert params.charts is None


@pytest.mark.parametrize(
    "field_type", ["half_float", "double", "short", "integer", "long", "bool"]
)
def test_scatter_chart_accepts_numeric_fields(field_type):
    """Any numeric type can be used in a scatter chart (it used to refuse `double`)"""
    index_config = SimpleNamespace(fields={"x": FieldConfig(type=field_type)})
    global_config = mock.MagicMock()
    global_config.get_index_config.return_value = ("off", index_config)
    with mock.patch("app.validations.get_config", return_value=global_config):
        assert check_fields_are_numeric("off", ["x"]) == []


@pytest.mark.parametrize("field_type", ["keyword", "text", "date"])
def test_scatter_chart_refuses_non_numeric_fields(field_type):
    index_config = SimpleNamespace(fields={"x": FieldConfig(type=field_type)})
    global_config = mock.MagicMock()
    global_config.get_index_config.return_value = ("off", index_config)
    with mock.patch("app.validations.get_config", return_value=global_config):
        assert check_fields_are_numeric("off", ["x"]) == ["Non numeric field name: x"]


def test_page_size_has_no_maximum_by_default(default_global_config):
    assert settings.max_page_size is None
    params = GetSearchParameters(q="milk", page_size=10_000)
    assert params.page_size == 10_000


@pytest.mark.parametrize(
    "page_size, ok", [(1, True), (999, True), (1000, True), (1001, False)]
)
def test_page_size_maximum_is_configurable(
    monkeypatch, default_global_config, page_size, ok
):
    monkeypatch.setattr(settings, "max_page_size", 1000)
    if ok:
        assert GetSearchParameters(q="milk", page_size=page_size).page_size == page_size
    else:
        with pytest.raises(ValueError, match="Maximum page_size is 1000"):
            GetSearchParameters(q="milk", page_size=page_size)


def test_max_page_size_setting(monkeypatch):
    monkeypatch.setenv("MAX_PAGE_SIZE", "500")
    assert Settings().max_page_size == 500
    monkeypatch.delenv("MAX_PAGE_SIZE")
    assert Settings().max_page_size is None
    monkeypatch.setenv("MAX_PAGE_SIZE", "0")
    with pytest.raises(ValueError):
        Settings()
