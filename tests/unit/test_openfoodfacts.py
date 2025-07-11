"""Test of Open Food Facts related code and config"""

import json
from pathlib import Path

import pytest

import app.config
import app.openfoodfacts


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
