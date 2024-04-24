"""
A module to help building facets from aggregations
"""

from typing import Any

from . import config
from ._types import SearchResponse


def build_facets(
    search_result: SearchResponse,
    index: str | None = None,
    facet_name: str = config.DEFAULT_FACET_NAME,
):
    """Given a search result with aggregations,
    build a list of facets for API response"""
    facets: list[dict[str, Any]] = []
    if config.CONFIG is None:
        return facets
    _, index_config = config.CONFIG.get_index_config(index)
    aggregations = search_result.aggregations
    facet_fields = index_config.get_facets_order()
    for field_name in facet_fields:
        if field_name not in aggregations:
            pass
        agg_data = aggregations[field_name]
        agg_buckets = agg_data.get("buckets", [])
        # best values
        facet_items = [
            {
                "key": bucket["key"],
                # TODO: compute name in target language if there is a taxonomy
                "name": bucket["name"],
                "count": bucket["doc_count"],
                # TODO: add if selected
            }
            for bucket in agg_buckets
        ]
        # add other values
        if agg_data["sum_other_doc_count"]:
            facet_items.append(
                {
                    "key": "--other--",
                    # TODO: translate in target language ?
                    "name": "other",
                    "count": agg_data["sum_other_doc_count"],
                }
            )
        items_count = sum(item["count"] for item in facet_items)
        # and no values
        if (not search_result.is_count_exact) and search_result.count > items_count:
            facet_items.append(
                {
                    "key": "--none--",
                    # Note: this depends on search_result.is_count_exact,
                    # but we leave it to user to verify
                    "count": search_result.count - items_count,
                }
            )
        # append our facet information
        facets.append(
            {
                "key": field_name,
                # FIXME translate
                "name": field_name,
                "items": facet_items,
                "count_error_margin": aggregations["doc_count_error_upper_bound"],
            }
        )

    return facets
