from unittest.mock import MagicMock, patch
import yaml

from app._types import FacetInfo, FacetItem, QueryAnalysis, SuccessSearchResponse
from app.config import Config
from app.facets import build_facets, translate_facets_values

BASE_CONFIG_YAML = """
indices:
    test:
        index:
            number_of_replicas: 1
            number_of_shards: 1
            name: test_index
            id_field_name: mykey
            last_modified_field_name: last_modified
        fields:
            mykey:
                required: true
                type: keyword
            last_modified:
                required: true
                type: date
            categories:
                type: keyword
                bucket_agg: true
                display_name:
                    en: Categories
                    fr: Catégories
            labels:
                type: keyword
                bucket_agg: true
                display_name: Product Labels
            simple_field:
                type: keyword
                bucket_agg: true
        supported_langs: ["en", "fr"]
        taxonomy:
            sources: []
            exported_langs: []
            index:
                number_of_replicas: 1
                number_of_shards: 1
                name: test_taxonomy
        document_fetcher: app._import.BaseDocumentFetcher
default_index: test
"""


def get_test_config():
    data = yaml.safe_load(BASE_CONFIG_YAML)
    return Config(**data)


def test_translate_pseudo_facet_labels():
    config = get_test_config()
    index_config = config.indices["test"]

    facets = {
        "categories": FacetInfo(
            name="categories",
            items=[
                FacetItem(key="cat1", name="cat1", count=10, selected=False),
                FacetItem(key="--other--", name="Other", count=5, selected=False),
                FacetItem(key="--none--", name="None", count=2, selected=False),
            ],
        )
    }

    # Test French translation
    with patch("app.facets._get_translations", return_value={}):
        translate_facets_values("fr", facets, index_config)

    items_by_key = {item.key: item.name for item in facets["categories"].items}
    assert items_by_key["--other--"] == "Autres"
    assert items_by_key["--none--"] == "Aucun"

    # Test Spanish translation
    with patch("app.facets._get_translations", return_value={}):
        translate_facets_values("es", facets, index_config)

    items_by_key = {item.key: item.name for item in facets["categories"].items}
    assert items_by_key["--other--"] == "Otros"
    assert items_by_key["--none--"] == "Ninguno"


def test_build_facets_display_name():
    config = get_test_config()
    index_config = config.indices["test"]

    mock_search_result = MagicMock(spec=SuccessSearchResponse)
    mock_search_result.aggregations = {
        "categories": {
            "buckets": [{"key": "en:beverages", "doc_count": 12}],
            "sum_other_doc_count": 0,
        },
        "labels": {
            "buckets": [{"key": "en:organic", "doc_count": 5}],
            "sum_other_doc_count": 0,
        },
        "simple_field": {
            "buckets": [{"key": "val1", "doc_count": 3}],
            "sum_other_doc_count": 0,
        },
    }

    query_analysis = QueryAnalysis(facets_filters={})

    with patch("app.facets._get_translations", return_value={}):
        # Test French display name resolution
        facets_fr = build_facets(
            mock_search_result,
            query_analysis,
            "fr",
            index_config,
            ["categories", "labels", "simple_field"],
        )
        assert facets_fr["categories"].name == "Catégories"
        assert facets_fr["labels"].name == "Product Labels"
        assert facets_fr["simple_field"].name == "simple_field"

        # Test English display name resolution
        facets_en = build_facets(
            mock_search_result,
            query_analysis,
            "en",
            index_config,
            ["categories", "labels", "simple_field"],
        )
        assert facets_en["categories"].name == "Categories"
