from app import facets
from app._types import DistributionChart, SuccessSearchResponse
from app.charts import build_charts


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
