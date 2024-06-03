"""
A module to help building facets from aggregations
"""

from . import config
from ._types import FacetInfo, FacetItem, FacetsInfos, SearchResponse


def safe_get_index_config(
    index: str | None = None, configuration: config.Config | None = None
) -> config.IndexConfig | None:
    """Safely get config"""
    if configuration is None:
        configuration = config.CONFIG
    if configuration is None:
        return None
    _, index_config = configuration.get_index_config(index)
    return index_config


def check_all_facets_fields_are_agg(
    index_id: str | None, facets: list[str] | None
) -> list[str]:
    """Check all facets are valid,
    that is, correspond to a field with aggregation"""
    errors: list[str] = []
    if facets is None:
        return errors
    config = safe_get_index_config(index_id)
    if config is None:
        raise ValueError(f"Cannot get index config for index_id {index_id}")
    for field_name in facets:
        if field_name not in config.fields:
            errors.append(f"Unknown field name in facets: {field_name}")
        elif not config.fields[field_name].bucket_agg:
            errors.append(f"Non aggregation field name in facets: {field_name}")
    return errors


def build_facets(
    search_result: SearchResponse,
    index_config: config.IndexConfig,
    facets_names: list[str] | None,
) -> FacetsInfos:
    """Given a search result with aggregations,
    build a list of facets for API response
    """
    aggregations = search_result.aggregations
    if facets_names is None or aggregations is None:
        return {}
    facets: FacetsInfos = {}
    for field_name in facets_names:
        if field_name not in aggregations:
            pass
        agg_data = aggregations[field_name]
        agg_buckets = agg_data.get("buckets", [])
        # best values
        facet_items = [
            FacetItem(
                key=bucket["key"],
                # TODO: compute name in target language if there is a taxonomy
                name=bucket["key"],
                count=bucket["doc_count"],
                # TODO: add if selected
            )
            for bucket in agg_buckets
        ]
        # add other values
        if agg_data["sum_other_doc_count"]:
            facet_items.append(
                FacetItem(
                    key="--other--",
                    # TODO: translate in target language ?
                    name="Other",
                    count=agg_data["sum_other_doc_count"],
                )
            )
        items_count = sum(item.count for item in facet_items)
        # and no values
        if (not search_result.is_count_exact) and search_result.count > items_count:
            facet_items.append(
                FacetItem(
                    key="--none--",
                    # TODO: translate in target language ?
                    name="None",
                    # Note: this depends on search_result.is_count_exact,
                    # but we leave it to user to verify
                    count=search_result.count - items_count,
                )
            )
        # append our facet information
        facets[field_name] = FacetInfo(
            # FIXME translate
            name=field_name,
            items=facet_items,
            count_error_margin=agg_data["doc_count_error_upper_bound"],
        )

    return facets
