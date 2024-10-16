"""
A module to help building facets from aggregations
"""

from . import config
from ._types import (
    FacetInfo,
    FacetItem,
    FacetsFilters,
    FacetsInfos,
    QueryAnalysis,
    SuccessSearchResponse,
)
from .taxonomy_es import get_taxonomy_names


def _get_translations(
    lang: str, items: list[tuple[str, str]], index_config: config.IndexConfig
) -> dict[tuple[str, str], str]:
    """Get translations for a list of items

    :param lang: target language
    :param items: list of (entry id, field_name)
    :param index_config: the index configuration
    :return: a dict mapping (id, field_name) to the translation
    """
    # go from field_name to taxonomy
    field_names = set([field_name for _, field_name in items])
    field_taxonomy: dict[str, str] = {
        # note: the `or ""` is only to make typing understand it can't be None
        field_name: index_config.fields[field_name].taxonomy_name or ""
        for field_name in field_names
        if index_config.fields[field_name].taxonomy_name
    }
    # fetch items names within a single query
    items_to_fetch = [
        (id, field_taxonomy[field_name])
        for id, field_name in items
        if field_name in field_taxonomy
    ]
    items_names = get_taxonomy_names(items_to_fetch, index_config)
    # compute best translations
    translations: dict[tuple[str, str], str] = {}
    for id, field_name in items:
        item_translation = None
        names = (
            items_names.get((id, field_taxonomy[field_name]))
            if field_name in field_taxonomy
            else None
        )
        if names:
            item_translation = names.get(lang, None)
            # fold back to main language for item
            if not item_translation:
                main_lang = id.split(":", 1)[0]
                item_translation = names.get(main_lang, None)
            # fold back to english
            if not item_translation:
                item_translation = names.get("en", None)
        # eventually translate
        if item_translation:
            translations[(id, field_name)] = item_translation
    return translations


def translate_facets_values(
    lang: str, facets: FacetsInfos, index_config: config.IndexConfig
):
    """Translate values of facets"""
    # harvest items to translate
    items = [
        (item.key, field_name)
        for field_name, info in facets.items()
        for item in info.items
    ]
    translations = _get_translations(lang, items, index_config)
    # translate facets
    for field_name, info in facets.items():
        for item in info.items:
            item.name = translations.get((item.key, field_name), item.name)


def build_facets(
    search_result: SuccessSearchResponse,
    query_analysis: QueryAnalysis,
    lang: str,
    index_config: config.IndexConfig,
    facets_names: list[str] | None,
) -> FacetsInfos:
    """Given a search result with aggregations,
    build a list of facets for API response
    """
    aggregations = search_result.aggregations
    facets_filters: FacetsFilters = (
        dict(query_analysis.facets_filters) if query_analysis.facets_filters else {}
    )
    if facets_names is None or aggregations is None:
        return {}
    facets: FacetsInfos = {}
    for field_name in facets_names:
        facet_items: list[FacetItem] = []
        if field_name not in aggregations and field_name not in facets_filters:
            continue
        agg_data = aggregations.get(field_name, {})
        agg_buckets = agg_data.get("buckets", []) if agg_data else []
        selected_values = list(facets_filters.get(field_name, []))
        count_error_margin = agg_data.get("doc_count_error_upper_bound", 0)
        # best values
        facet_items.extend(
            FacetItem(
                key=bucket["key"],
                # TODO: compute value in target language if there is a taxonomy
                name=bucket["key"],
                count=bucket["doc_count"],
                selected=bucket["key"] in selected_values,
            )
            for bucket in agg_buckets
        )
        # selected values that are not in aggregations values
        facet_items.extend(
            FacetItem(
                key=value,
                # TODO: compute value in target language if there is a taxonomy
                name=value,
                count=None,  # undefined
                selected=True,
            )
            for value in set(selected_values) - set(item.key for item in facet_items)
        )
        # add other values
        if agg_data["sum_other_doc_count"]:
            facet_items.append(
                FacetItem(
                    key="--other--",
                    # TODO: translate in target language ?
                    name="Other",
                    count=agg_data["sum_other_doc_count"],
                    selected=False,
                )
            )
        # 2024-06-04: Alex: removed as we don't support it yet
        # at request construction time
        #
        # items_count = sum(item.count or 0 for item in facet_items)
        # and empty values if there are some (taking into account error margin)
        # if (not search_result.is_count_exact) and search_result.count > (
        #     items_count + count_error_margin
        # ):
        #     facet_items.append(
        #         FacetItem(
        #             key="--none--",
        #             # TODO: translate in target language ?
        #             name="None",
        #             # Note:translate_facets_values leave it to user to verify
        #             count=search_result.count - items_count,
        #             # FIXME: compute selected !
        #             selected=False,
        #         )
        #     )
        # re-order to have selected first
        facet_items = [
            item
            for i, item in sorted(
                enumerate(facet_items),
                key=lambda i_item: (not i_item[1].selected, i_item[0]),
            )
        ]
        # append our facet information
        facets[field_name] = FacetInfo(
            # FIXME translate field name in target language
            name=field_name,
            items=facet_items,
            count_error_margin=count_error_margin,
        )
    # translate
    translate_facets_values(lang, facets, index_config)
    return facets
