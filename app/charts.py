from ._types import ChartsInfos, SuccessSearchResponse


def build_charts(
    search_result: SuccessSearchResponse,
    charts_names: list[str] | None,
) -> ChartsInfos:
    charts: ChartsInfos = {}
    aggregations = search_result.aggregations

    if charts_names is None or aggregations is None:
        return charts

    for chart_name in charts_names:
        agg_data = aggregations.get(chart_name, {})

        buckets = agg_data.get("buckets", []) if agg_data else []

        # Filter unknown values
        values = [
            {"category": bucket["key"], "amount": bucket["doc_count"]}
            for bucket in buckets
            if bucket["key"] != "unknown"
        ]
        values.sort(key=lambda x: x["category"])

        charts[chart_name] = {
            "$schema": "https://vega.github.io/schema/vega/v5.json",
            "title": chart_name,
            "autosize": {"type": "fit", "contains": "padding"},
            "signals": [
                {
                    "name": "width",
                    "init": "containerSize()[0]",
                    "on": [{"events": "window:resize", "update": "containerSize()[0]"}],
                },
                {
                    "name": "tooltip",
                    "value": {},
                    "on": [
                        {"events": "rect:pointerover", "update": "datum"},
                        {"events": "rect:pointerout", "update": "{}"},
                    ],
                },
            ],
            "height": 140,
            "padding": 5,
            "data": [
                {
                    "name": "table",
                    "values": values,
                },
            ],
            "scales": [
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
            ],
            "axes": [
                {"orient": "bottom", "scale": "xscale", "domain": False, "ticks": False}
            ],
            "marks": [
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
            ],
        }

    return charts
