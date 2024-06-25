from ._types import ChartsInfos, SuccessSearchResponse
from functools import reduce

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


def build_distribution_chart(chart_name, values):
    chart = empty_chart(chart_name)
    chart['data'] = [
        {
            "name": "table",
            "values": values,
            "transform": [
                {
                    "type": "filter",
                    "expr": "datum['category'] != 'unknown'"
                }
            ]
        },
    ]
    chart['signals'].append({
        "name": "tooltip",
        "value": {},
        "on": [
            {"events": "rect:pointerover", "update": "datum"},
            {"events": "rect:pointerout", "update": "{}"},
        ],
    })
    chart['scales'] = [
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
    chart['axes'] = [
        {"orient": "bottom", "scale": "xscale", "domain": False, "ticks": False}
    ]
    chart['marks'] = [
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
                    "fill": {"value": "steelblue"},
                },
                "hover": {
                    "fill": {"value": "red"},
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
                        {"test": "datum === tooltip", "value": 0},
                        {"value": 1},
                    ],
                },
            },
        },
    ]
    return chart


def build_scatter_chart(chart_name, search_result):
    def _get(v, path):
        return reduce(lambda c, k: c.get(k, {}), path.split('.'), v)

    chart = empty_chart(chart_name)
    x, y = chart_name.split(':')
    # nutriments.xxx is broken in vega.
    # I think it searches for nutriments[xxx]
    # might be expected ^^
    vega_x = x.replace('.', '__')
    vega_y = y.replace('.', '__')
    values = [{vega_x: _get(v, x), vega_y: _get(v, y)} for v in search_result.hits]

    chart['data'] = [{
        "name": 'source',
        "values": values
    }]
    chart['scales'] = [{
      "name": "x",
      "type": "linear",
      "round": True,
      "nice": True,
      "zero": True,
      "domain": {"data": "source", "field": vega_x},
      "range": "width"
    },
    {
      "name": "y",
      "type": "linear",
      "round": True,
      "nice": True,
      "zero": True,
      "domain": {"data": "source", "field": vega_y},
      "range": "height"
    }]
    chart["axes"] = [
        {
            "scale": "x",
            "grid": True,
            "domain": False,
            "orient": "bottom",
            "tickCount": 5,
            "title": x
        },
        {
            "scale": "y",
            "grid": True,
            "domain": False,
            "orient": "left",
            "titlePadding": 5,
            "title": y
        }
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
                    "stroke": {"value": "#4682b4"},
                    "fill": {"value": "transparent"}
                }
            }
        }
    ]

    return chart


def build_charts(
    search_result: SuccessSearchResponse,
    charts_names: list[str] | None,
) -> ChartsInfos:
    charts: ChartsInfos = {}
    aggregations = search_result.aggregations

    if charts_names is None or aggregations is None:
        return charts

    for chart_name in charts_names:
        if ':' in chart_name:
            charts[chart_name] = build_scatter_chart(chart_name, search_result)
        else:
            agg_data = aggregations.get(chart_name, {})

            buckets = agg_data.get("buckets", []) if agg_data else []

            # Filter unknown values
            values = [
                {"category": bucket["key"], "amount": bucket["doc_count"]}
                for bucket in buckets
            ]
            values.sort(key=lambda x: x["category"])

            charts[chart_name] = build_distribution_chart(chart_name, values)

    return charts
