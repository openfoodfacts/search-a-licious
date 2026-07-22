from app._types import DistributionChart, GetSearchParameters, ScatterChart


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
