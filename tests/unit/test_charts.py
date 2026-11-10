import pytest
from pydantic import ValidationError

from app import facets
from app._types import (
    DistributionChart,
    GetChartSearchParameters,
    PostChartSearchParameters,
    QueryAnalysis,
    ScatterChart,
    SearchParameters,
    SuccessSearchResponse,
)
from app.charts import build_charts, has_scatter_values


def _search_result(aggregations) -> SuccessSearchResponse:
    return SuccessSearchResponse(
        hits=[],
        aggregations=aggregations,
        page=1,
        page_size=10,
        page_count=1,
        took=1,
        timed_out=False,
        count=10,
        is_count_exact=True,
    )


def _buckets(*pairs):
    return {"buckets": [{"key": k, "doc_count": n} for k, n in pairs]}


def _chart_values(chart):
    return chart["data"][0]["values"]


def test_distribution_chart_uses_translated_names(default_config, monkeypatch):
    lookups = []

    def fake_get_taxonomy_names(items, config):
        lookups.append(items)
        return {
            ("en:kellogg-s", "brands"): {"en": "Kellogg's"},
            ("post", "brands"): {"en": "Post"},
        }

    monkeypatch.setattr(facets, "get_taxonomy_names", fake_get_taxonomy_names)
    result = _search_result(
        {
            "brands": _buckets(
                ("en:kellogg-s", 5), ("post", 3), ("Post", 2), ("auchan", 1)
            ),
            "nutrition_grades": _buckets(("a", 4), ("b", 1)),
            "nova_groups": _buckets((1, 2), (3, 5), (4, 10)),
        }
    )

    charts = build_charts(
        result,
        default_config,
        [
            DistributionChart(field="brands"),
            DistributionChart(field="nutrition_grades"),
            DistributionChart(field="nova_groups"),
        ],
        "en",
    )

    # same name after translation: one bar; sorted ignoring case
    assert _chart_values(charts["brands"]) == [
        {"category": "auchan", "amount": 1},
        {"category": "Kellogg's", "amount": 5},
        {"category": "Post", "amount": 5},
    ]
    # not taxonomy-backed: keys kept
    assert _chart_values(charts["nutrition_grades"]) == [
        {"category": "a", "amount": 4},
        {"category": "b", "amount": 1},
    ]
    assert _chart_values(charts["nova_groups"]) == [
        {"category": 1, "amount": 2},
        {"category": 3, "amount": 5},
        {"category": 4, "amount": 10},
    ]
    # one lookup for all charts
    assert len(lookups) == 1


def test_no_taxonomy_lookup_without_taxonomy_fields(default_config, monkeypatch):
    def fail(items, config):
        raise AssertionError("unexpected taxonomy lookup")

    monkeypatch.setattr(facets, "get_taxonomy_names", fail)
    result = _search_result({"nutrition_grades": _buckets(("a", 4))})

    charts = build_charts(
        result, default_config, [DistributionChart(field="nutrition_grades")], "en"
    )

    assert _chart_values(charts["nutrition_grades"]) == [{"category": "a", "amount": 4}]


def test_numeric_keys(default_config, monkeypatch):
    monkeypatch.setattr(facets, "get_taxonomy_names", lambda items, config: {})
    result = _search_result({"nova_groups": _buckets((10, 6), (2, 2))})

    charts = build_charts(
        result, default_config, [DistributionChart(field="nova_groups")], "en"
    )

    assert _chart_values(charts["nova_groups"]) == [
        {"category": 2, "amount": 2},
        {"category": 10, "amount": 6},
    ]


SCANS_CHART = {"x": "scans_n", "y": "completeness"}


def test_chart_max_entries_bounds(default_config):
    charts = [SCANS_CHART]
    assert PostChartSearchParameters(q="milk", charts=charts).max_entries == 1000
    params = PostChartSearchParameters(q="milk", charts=charts, max_entries=10_000)
    assert params.max_entries == 10_000
    for bad in (0, 10_001):
        with pytest.raises(ValidationError):
            PostChartSearchParameters(q="milk", charts=charts, max_entries=bad)


def test_chart_needs_a_chart(default_config):
    with pytest.raises(ValidationError, match="too_short"):
        PostChartSearchParameters(q="milk", charts=[])


def test_chart_get_params_parse_charts_string(default_config):
    params = GetChartSearchParameters(
        q="milk", charts="nutriments.fat_100g:completeness,scans_n:completeness"
    )
    assert params.charts == [
        ScatterChart(x="nutriments.fat_100g", y="completeness"),
        ScatterChart(x="scans_n", y="completeness"),
    ]
    for bad in ("fat_100g", "a:b:c", "scans_n:completeness,fat_100g"):
        with pytest.raises(ValidationError):
            GetChartSearchParameters(q="milk", charts=bad)


def test_chart_params_non_numeric_field(default_config):
    with pytest.raises(ValidationError, match="Non numeric field name"):
        PostChartSearchParameters(
            q="milk", charts=[SCANS_CHART, {"x": "labels", "y": "completeness"}]
        )


def test_chart_params_forbid_page(default_config):
    with pytest.raises(ValidationError, match="extra_forbidden"):
        PostChartSearchParameters(q="milk", charts=[SCANS_CHART], page=2)


def test_chart_params_sort_script(default_config):
    charts = [SCANS_CHART]
    with pytest.raises(ValidationError, match="must not be a script"):
        GetChartSearchParameters(
            q="milk", charts="scans_n:completeness", sort_by="personal_score"
        )
    with pytest.raises(ValidationError, match="sort_params"):
        PostChartSearchParameters(charts=charts, sort_by="personal_score")
    sort_params = {"environmental_score": 1, "nutri_score": 1, "nova_group": 1}
    PostChartSearchParameters(
        charts=charts, sort_by="personal_score", sort_params=sort_params
    )


def test_has_scatter_values():
    chart = ScatterChart(x="nutriments.fat_100g", y="completeness")
    assert has_scatter_values({"nutriments": {"fat_100g": 0}, "completeness": 1}, chart)
    assert not has_scatter_values({"nutriments": {}, "completeness": 1}, chart)
    assert not has_scatter_values({"nutriments": {"fat_100g": 2}}, chart)


def test_search_max_results_still_checked(default_config):
    with pytest.raises(ValidationError, match="Maximum number of returned results"):
        SearchParameters(q="milk", page=1001, page_size=10)


def test_facets_numeric_keys(default_config, monkeypatch):
    monkeypatch.setattr(facets, "get_taxonomy_names", lambda items, config: {})
    nova_groups = _buckets((0, 3), (2, 1))
    nova_groups["sum_other_doc_count"] = 0
    result = _search_result({"nova_groups": nova_groups})

    infos = facets.build_facets(
        result,
        QueryAnalysis(facets_filters={"nova_groups": ["2"]}),
        "en",
        default_config,
        ["nova_groups"],
    )

    items = [item.model_dump() for item in infos["nova_groups"].items]
    assert items == [
        {"key": "2", "name": "2", "count": 1, "selected": True},
        {"key": "0", "name": "0", "count": 3, "selected": False},
    ]
