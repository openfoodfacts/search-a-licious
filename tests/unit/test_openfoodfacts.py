"""Test of Open Food Facts related code and config"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

import app.config
import app.indexing
import app.openfoodfacts
from app._types import FetcherStatus
from app.openfoodfacts import TaxonomyPreprocessor
from app.taxonomy import Taxonomy, TaxonomyNodeResult


@pytest.mark.parametrize("fname", ["openfoodfacts"])
def test_prod_config(fname, load_expected_result):
    # this test is more there to test the configuration itself
    # than the config parser
    conf = app.config.Config.from_yaml(Path(f"data/config/{fname}.yml"))
    expected_conf = load_expected_result(
        f"test_prod_config_{fname}", json.loads(conf.json())
    )
    assert expected_conf == json.loads(conf.json())


def test_openfoodfacts_document_processor(load_expected_result):
    conf = app.config.Config.from_yaml(Path("data/config/openfoodfacts.yml"))
    processor = app.openfoodfacts.DocumentPreprocessor(
        config=conf.indices["off"],
    )
    document = {
        "code": "1234567890123",
        "product_name": "Test Product main",
        "product_name_en": "Test Product EN",
        "product_name_fr": "Test Product FR",
        "ingredients_text": "this should be in main",
        "ingredients_text_en": "this should be in en",
        "nutriments": {
            "energy-kcal_100g": 80.8,
            "fat_100g": 22,
            # should be dismissed
            "iron_100g": 0.001,
            "fat_value": 22,
            "fat_unit": "g",
        },
        # nova groups markers
        "nova_groups_markers": {
            3: [["en:ingredient", "en:chocolate powder"]],
            4: [["en:ingredient", "en:vanillin"], ["en:additive", "en:e424"]],
        },
        # images
        "images": {
            "uploaded": {
                "1": {
                    "sizes": {
                        "100": {"h": 88, "w": 100},
                        "full": {"h": 1856, "w": 2104},
                    },
                    "uploaded_t": 1750445179,
                    "uploader": "test1",
                },
                "2": {
                    "sizes": {
                        "100": {"h": 100, "w": 100},
                        "full": {"h": 300, "w": 300},
                    },
                    "uploaded_t": 1750480000,
                    "uploader": "test2",
                },
            },
            "selected": {
                "front": {
                    "en": {
                        "generation": {},
                        "imgid": "1",
                        "rev": "3",
                        "sizes": {
                            "100": {"h": 88, "w": 100},
                            "full": {"h": 928, "w": 1052},
                        },
                    },
                    "fr": {
                        "generation": {
                            "coordinates_image_size": "full",
                            "x1": 10,
                            "x2": 110,
                            "y1": 33,
                            "y2": 53,
                        },
                        "imgid": "2",
                        "rev": "4",
                        "sizes": {
                            "100": {"h": 20, "w": 100},
                            "full": {"h": 60, "w": 300},
                        },
                    },
                },
            },
        },
    }
    result = processor.preprocess(document)
    expected_document = load_expected_result(
        "test_openfoodfacts_document_preprocessor", result.document
    )
    assert result.document == expected_document


def test_openfoodfacts_document_processor_no_images():
    """We must not fail just because we lack some fields"""
    conf = app.config.Config.from_yaml(Path("data/config/openfoodfacts.yml"))
    processor = app.openfoodfacts.DocumentPreprocessor(
        config=conf.indices["off"],
    )
    result = processor.preprocess({})
    assert result.document == {"nutriments": {}, "obsolete": False}
    result = processor.preprocess({"images": {}})
    assert result.document == {
        "nutriments": {},
        "obsolete": False,
        "uploaded_images": [],
        "selected_images": {},
    }


class TestTaxonomyPreprocessor:
    def test_preprocess_brands(self):
        # TaxonomyPreprocessor does not user the IndexConfig, so we can
        # provide a mock
        preprocessor = TaxonomyPreprocessor(MagicMock())
        brand_taxonomy = Taxonomy.from_dict(
            "brands",
            {
                "xx:flora": {
                    "name": {"xx": "Flora"},
                    "synonyms": {"xx": ["Flora"]},
                },
                "xx:nat-vie": {
                    "name": {"xx": "NAT&vie"},
                    "synonyms": {"xx": ["NAT&vie", "NAT&vie veggie"]},
                },
            },
        )
        node = brand_taxonomy["xx:nat-vie"]
        assert node is not None
        result = preprocessor.preprocess(brand_taxonomy, node)
        assert isinstance(result, TaxonomyNodeResult)
        assert result.status is FetcherStatus.FOUND
        # Check that we renamed "xx" to "main"
        assert result.node.names["main"] == "NAT&vie"
        assert result.node.synonyms["main"] == ["NAT&vie", "NAT&vie veggie"]


@pytest.mark.parametrize(
    "language", [pytest.param({}, id="missing"), {"lc": ""}, {"lc": None}]
)
def test_result_processor_skips_selected_images_without_language(language):
    conf = app.config.Config.from_yaml(Path("data/config/openfoodfacts.yml"))
    processor = app.openfoodfacts.ResultProcessor(config=conf.indices["off"])
    product = {
        "code": "3168930010265",
        "lang": "en",
        "languages_codes": ["en"],
        "selected_images": {
            "front": [
                {**language, "rev": 298, "full_size": {"h": 400, "w": 400}},
                {"lc": "en", "rev": 299, "full_size": {"h": 400, "w": 400}},
            ],
        },
    }

    result = processor.process_result(product, projection=None)

    assert result["images"]["selected"]["front"] == {
        "en": {"rev": 299, "sizes": {"full": {"h": 400, "w": 400}}},
    }
    assert result["image_url"] == (
        "https://images.openfoodfacts.org/images/products/316/893/001/0265/front_en.299.400.jpg"
    )
    assert result["selected_images"]["front"]["display"]["en"] == result["image_url"]


def _fetch(monkeypatch, response=None, exc=None, item=None):
    """Run DocumentFetcher.fetch_document with a mocked HTTP session"""
    get = MagicMock(return_value=response, side_effect=exc)
    monkeypatch.setattr(app.openfoodfacts.http_session, "get", get)
    config = MagicMock()
    config.index.id_field_name = "code"
    result = app.openfoodfacts.DocumentFetcher(config).fetch_document(
        "stream", item or {"code": "123"}
    )
    return result, get


def _response(status_code, json_data=None, json_error=False):
    response = MagicMock(status_code=status_code, ok=status_code < 400)
    if json_error:
        response.json.side_effect = requests.exceptions.JSONDecodeError("bad", "", 0)
    else:
        response.json.return_value = json_data
    return response


def test_fetcher_found(monkeypatch):
    result, get = _fetch(
        monkeypatch, _response(200, {"status": 1, "product": {"a": 1}})
    )
    assert result.status == FetcherStatus.FOUND
    assert result.document == {"a": 1}
    # a timeout is always set
    assert get.call_args.kwargs["timeout"] == app.openfoodfacts.OFF_API_TIMEOUT


@pytest.mark.parametrize(
    "response",
    [
        _response(200, {"status": 0, "status_verbose": "product not found"}),
        _response(404, {"status": 0}),
    ],
)
def test_fetcher_removed(monkeypatch, response):
    result, _ = _fetch(monkeypatch, response)
    assert result.status == FetcherStatus.REMOVED
    # the id is needed to delete the document
    assert result.document == {"code": "123"}


def test_fetcher_deleted_action_is_removed_with_id(monkeypatch):
    result, get = _fetch(monkeypatch, item={"code": "123", "action": "deleted"})
    assert result.status == FetcherStatus.REMOVED
    assert result.document == {"code": "123"}
    # no need to fetch a deleted product
    get.assert_not_called()


def test_removed_product_is_processed_as_a_deletion(monkeypatch):
    result, _ = _fetch(monkeypatch, _response(404, {"status": 0}))
    conf = app.config.Config.from_yaml(Path("data/config/openfoodfacts.yml"))
    processed = app.indexing.DocumentProcessor(conf.indices["off"]).from_result(result)
    assert processed.status == FetcherStatus.REMOVED
    assert processed.document == {"_id": "123"}


@pytest.mark.parametrize("status_code", [429, 500, 502, 503])
def test_fetcher_retries_on_server_error(monkeypatch, status_code):
    # the body has no product, but this must not be taken as a removal
    result, _ = _fetch(monkeypatch, _response(status_code, {}))
    assert result.status == FetcherStatus.RETRY


def test_fetcher_retries_on_timeout(monkeypatch):
    result, _ = _fetch(monkeypatch, exc=requests.exceptions.Timeout())
    assert result.status == FetcherStatus.RETRY


def test_fetcher_invalid_json(monkeypatch):
    result, _ = _fetch(monkeypatch, _response(200, json_error=True))
    assert result.status == FetcherStatus.OTHER


@pytest.mark.parametrize("projection", [None, {"code", "selected_images"}])
def test_selected_images_keep_each_language(projection):
    """Every language retains its own revision and all three image sizes."""
    conf = app.config.Config.from_yaml(Path("data/config/openfoodfacts.yml"))
    processor = app.openfoodfacts.ResultProcessor(config=conf.indices["off"])
    product = {
        "code": "3168930010265",
        "lang": "en",
        "languages_codes": ["en", "fr", "de"],
        "selected_images": {
            "front": [
                {"lc": "en", "rev": 299, "full_size": {"h": 400, "w": 400}},
                {"lc": "fr", "rev": 300, "full_size": {"h": 400, "w": 400}},
            ],
        },
    }
    result = processor.process_result(product, projection=projection)
    assert result["selected_images"] == {
        "front": {
            size_name: {
                lc: f"https://images.openfoodfacts.org/images/products/316/893/001/0265/front_{lc}.{rev}.{size}.jpg"
                for lc, rev in [("en", 299), ("fr", 300)]
            }
            for size_name, size in [("display", 400), ("small", 200), ("thumb", 100)]
        }
    }


def test_no_generated_selected_images_without_languages():
    """An empty language list must not generate image URL entries."""
    conf = app.config.Config.from_yaml(Path("data/config/openfoodfacts.yml"))
    processor = app.openfoodfacts.ResultProcessor(config=conf.indices["off"])
    fields = processor.build_image_fields(
        {"code": "3168930010265", "languages_codes": []}, projection=None
    )
    assert "selected_images" not in fields


@pytest.mark.parametrize("languages", [{"en": 1, "fr": 2}, ["en", "fr"], {}])
def test_preprocess_language_codes(languages):
    """Production preprocessing accepts source dictionaries and existing lists."""
    conf = app.config.Config.from_yaml(Path("data/config/openfoodfacts.yml"))
    processor = app.openfoodfacts.DocumentPreprocessor(config=conf.indices["off"])
    result = processor.preprocess(
        {"code": "1234567890123", "languages_codes": languages}
    )
    assert result.document is not None
    assert result.document["languages_codes"] == list(languages)
