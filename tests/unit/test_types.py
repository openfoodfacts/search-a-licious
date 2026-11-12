from types import SimpleNamespace
from unittest import mock

import pytest

from app._types import DistributionChart, GetSearchParameters, ScatterChart
from app.config import FieldConfig
from app.query import parse_sort_by_field
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


@pytest.mark.parametrize(
    "sort_by",
    [
        "unique_scans_n",
        "-unique_scans_n",
        "nutriments.fat_100g",
        "-nutriments.fat_100g",
        "nutriments.energy-kcal_100g",
    ],
)
def test_sort_by_accepts_fields_and_numeric_subfields(default_global_config, sort_by):
    params = GetSearchParameters(q="milk", sort_by=sort_by)

    assert params.sort_by == sort_by


@pytest.mark.parametrize(
    "sort_by",
    [
        # an object field has no value of its own
        "nutriments",
        "-nutriments",
        # nested: needs a nested sort clause
        "packagings",
        "packagings.weight_measured",
        # not in the config
        "nutriments.unknown",
        "nutriments.fat_100g.x",
        "unique_scans_n.fat_100g",
        "unknown.fat_100g",
        "nutriments.",
        ".fat_100g",
    ],
)
def test_sort_by_refuses_other_paths(default_global_config, sort_by):
    with pytest.raises(ValueError, match="`sort_by` must be a valid field name"):
        GetSearchParameters(q="milk", sort_by=sort_by)


def test_sort_by_subfield_reaches_elasticsearch_unchanged(default_global_config):
    """No rewriting of the path: `nutriments.fat_100g` is the mapped field"""
    params = GetSearchParameters(q="milk", sort_by="-nutriments.fat_100g")

    assert parse_sort_by_field(params.sort_by, params.index_config) == (
        "-nutriments.fat_100g"
    )
