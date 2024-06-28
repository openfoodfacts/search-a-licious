from functools import reduce

from ._types import (
    ChartsInfos,
    ChartType,
    DistributionChartType,
    ScatterChartType,
    SuccessSearchResponse,
)

PRIMARY_COLOR = "#341100"
ACCENT_COLOR = "#ff8714"


def empty_chart(chart_name):
    return {
        "$schema": "https://vega.github.io/schema/vega/v5.json",
        "title": chart_name,
        "autosize": {"type": "fit", "contains": "padding"},
        "signals": [
            {
                "name": "width",
                "init": "containerSize()[0]",
                "on": [{"events": "window:resize", "update": "containerSize()[0]"}],
            },
        ],
        "height": 140,
        "padding": 5,
        "data": [],
        "scales": [],
        "axes": [],
        "marks": [],
    }


def build_distribution_chart(chart: DistributionChartType, values):
    chart = empty_chart(chart.field)
    chart["data"] = [
        {
            "name": "table",
            "values": values,
            "transform": [{"type": "filter", "expr": "datum['category'] != 'unknown'"}],
        },
    ]
    chart["signals"].append(
        {
            "name": "tooltip",
            "value": {},
            "on": [
                {"events": "rect:pointerover", "update": "datum"},
                {"events": "rect:pointerout", "update": "{}"},
            ],
        }
    )
    chart["scales"] = [
        {
            "name": "xscale",
            "type": "band",
            "domain": {"data": "table", "field": "category"},
            "range": "width",
            "padding": 0.05,
            "round": True,
        },
        {
            "name": "yscale",
            "domain": {"data": "table", "field": "amount"},
            "nice": True,
            "range": "height",
        },
    ]
    chart["axes"] = [
        {"orient": "bottom", "scale": "xscale", "domain": False, "ticks": False}
    ]
    chart["marks"] = [
        {
            "type": "rect",
            "from": {"data": "table"},
            "encode": {
                "enter": {
                    "x": {"scale": "xscale", "field": "category"},
                    "width": {"scale": "xscale", "band": 1},
                    "y": {"scale": "yscale", "field": "amount"},
                    "y2": {"scale": "yscale", "value": 0},
                },
                "update": {
                    "fill": {"value": PRIMARY_COLOR},
                },
                "hover": {
                    "fill": {"value": ACCENT_COLOR},
                },
            },
        },
        {
            "type": "text",
            "encode": {
                "enter": {
                    "align": {"value": "center"},
                    "baseline": {"value": "bottom"},
                    "fill": {"value": "#333"},
                },
                "update": {
                    "x": {
                        "scale": "xscale",
                        "signal": "tooltip.category",
                        "band": 0.5,
                    },
                    "y": {
                        "scale": "yscale",
                        "signal": "tooltip.amount",
                        "offset": -2,
                    },
                    "text": {"signal": "tooltip.amount"},
                    "fillOpacity": [
                        {"value": 1},
                    ],
                },
            },
        },
    ]
    return chart


def build_scatter_chart(chart_option: ScatterChartType, search_result):
    """
    Build a scatter plot only for values from search_results
    (only values in the current page)
    TODO: use values from the whole search?
    """

    def _get(v, path):
        return reduce(lambda c, k: c.get(k, {}), path.split("."), v)

    chart = empty_chart(f"{chart_option.x} x { chart_option.y }")

    # nutriments.xxx is broken in vega.
    # I think it searches for nutriments[xxx]
    # might be expected ^^
    vega_x = chart_option.x.replace(".", "__")
    vega_y = chart_option.y.replace(".", "__")
    values = [
        {vega_x: _get(v, chart_option.x), vega_y: _get(v, chart_option.y)}
        for v in search_result.hits
    ]

    chart["data"] = [{"name": "source", "values": values}]
    chart["scales"] = [
        {
            "name": "x",
            "type": "linear",
            "round": True,
            "nice": True,
            "zero": True,
            "domain": {"data": "source", "field": vega_x},
            "range": "width",
        },
        {
            "name": "y",
            "type": "linear",
            "round": True,
            "nice": True,
            "zero": True,
            "domain": {"data": "source", "field": vega_y},
            "range": "height",
        },
    ]
    chart["axes"] = [
        {
            "scale": "x",
            "grid": True,
            "domain": False,
            "orient": "bottom",
            "tickCount": 5,
            "title": chart_option.x,
        },
        {
            "scale": "y",
            "grid": True,
            "domain": False,
            "orient": "left",
            "titlePadding": 5,
            "title": chart_option.y,
        },
    ]

    chart["marks"] = [
        {
            "name": "marks",
            "type": "symbol",
            "from": {"data": "source"},
            "encode": {
                "update": {
                    "x": {"scale": "x", "field": vega_x},
                    "y": {"scale": "y", "field": vega_y},
                    "shape": {"value": "circle"},
                    "strokeWidth": {"value": 2},
                    "opacity": {"value": 0.5},
                    "stroke": {"value": PRIMARY_COLOR},
                    "fill": {"value": PRIMARY_COLOR},
                }
            },
        }
    ]

    return chart


def build_charts(
    search_result: SuccessSearchResponse,
    requested_charts: list[ChartType] | None,
) -> ChartsInfos:
    charts: ChartsInfos = {}

    if requested_charts is None:
        return charts

    aggregations = search_result.aggregations

    for requested_chart in requested_charts:
        if requested_chart.chart_type == "ScatterChartType":
            charts[f"{requested_chart.x}:{requested_chart.y}"] = build_scatter_chart(
                requested_chart, search_result
            )
        else:
            # distribution charts are created from aggregations
            if aggregations is not None:
                agg_data = aggregations.get(requested_chart.field, {})

                buckets = agg_data.get("buckets", []) if agg_data else []

                values = [
                    {"category": bucket["key"], "amount": bucket["doc_count"]}
                    for bucket in buckets
                ]
                values.sort(key=lambda x: x["category"])

                charts[requested_chart.field] = build_distribution_chart(
                    requested_chart, values
                )

    return charts
