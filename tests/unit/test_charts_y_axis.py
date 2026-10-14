import pytest

from app._types import DistributionChart, GetSearchParameters, SuccessSearchResponse
from app.charts import build_charts


def _search_result() -> SuccessSearchResponse:
    return SuccessSearchResponse(
        hits=[],
        aggregations={"nutrition_grades": {"buckets": [{"key": "a", "doc_count": 4}]}},
        page=1,
        page_size=10,
        page_count=1,
        took=1,
        timed_out=False,
        count=4,
        is_count_exact=True,
    )


@pytest.mark.parametrize(
    "y_axis,expected", [(False, ["bottom"]), (True, ["bottom", "left"])]
)
def test_distribution_chart_y_axis(default_config, y_axis, expected):
    charts = build_charts(
        _search_result(),
        default_config,
        [DistributionChart(field="nutrition_grades")],
        y_axis=y_axis,
    )

    axes = charts["nutrition_grades"]["axes"]
    assert [axis["orient"] for axis in axes] == expected


@pytest.mark.parametrize("value,expected", [(None, False), ("true", True)])
def test_charts_y_axis_parameter(default_config, value, expected):
    extra = {} if value is None else {"charts_y_axis": value}
    params = GetSearchParameters(q="milk", charts="nutrition_grades", **extra)

    assert params.charts_y_axis is expected
