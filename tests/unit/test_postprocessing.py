import copy
from pathlib import Path

import pytest
from elasticsearch_dsl import Search
from elasticsearch_dsl.response import Response

from app.config import Config
from app.openfoodfacts import ResultProcessor, generate_image_url
from app.postprocessing import BaseResultProcessor, _prepare_projection


@pytest.mark.parametrize(
    "fields, expected",
    [
        (
            {"code", "nutriments.energy-kcal_100g", "nutriments.sugars_100g"},
            {"code": "123", "nutriments": {"energy-kcal_100g": 80, "sugars_100g": 0}},
        ),
        (
            {"nutriments.salt_100g", "nutriments.missing"},
            {"nutriments": {"salt_100g": None}},
        ),
        (
            {"nutriments.details.unit", "nutriments.details.source"},
            {"nutriments": {"details": {"unit": "g", "source": "label"}}},
        ),
        ({"product_name_en"}, {"product_name_en": "Cola"}),
        ({"code.missing", "missing.child"}, {}),
        ({"nutriments.missing"}, {}),
    ],
)
def test_result_nested_fields(default_config, fields, expected):
    processor = BaseResultProcessor(default_config)
    document = {
        "code": "123",
        "product_name": {"main": "Cola", "en": "Cola"},
        "nutriments": {
            "energy-kcal_100g": 80,
            "sugars_100g": 0,
            "salt_100g": None,
            "details": {"unit": "g", "source": "label", "extra": "omit"},
        },
    }

    assert processor.process_result(document, fields) == expected


@pytest.mark.parametrize(
    "fields",
    [{"nutriments"}, {"nutriments", "nutriments.sugars_100g"}],
)
def test_result_whole_object_fields(default_config, fields):
    document = {"code": "123", "nutriments": {"sugars_100g": 0, "fat_100g": 5}}
    processor = BaseResultProcessor(default_config)

    assert processor.process_result(copy.deepcopy(document), fields) == {
        "nutriments": document["nutriments"]
    }


@pytest.mark.parametrize("fields", [None, set()])
def test_result_without_field_selection(default_config, fields):
    document = {"code": "123", "nutriments": {"sugars_100g": 0}, "labels": []}
    processor = BaseResultProcessor(default_config)

    assert processor.process_result(copy.deepcopy(document), fields) == document


@pytest.mark.parametrize("method", ["get", "post"])
def test_search_nested_nutriment_fields(
    default_config, query_builder_cache_is_empty, test_client, monkeypatch, method
):
    def execute(query):
        return Response(
            query,
            {
                "took": 1,
                "timed_out": False,
                "hits": {
                    "total": {"value": 1, "relation": "eq"},
                    "hits": [
                        {
                            "_id": "123",
                            "_score": 1,
                            "_source": {
                                "code": "123",
                                "nutriments": {
                                    "energy-kcal_100g": 80,
                                    "sugars_100g": 0,
                                    "fat_100g": 5,
                                },
                            },
                        }
                    ],
                },
                "aggregations": {},
            },
        )

    monkeypatch.setattr(Search, "execute", execute)
    fields = ["code", "nutriments.energy-kcal_100g", "nutriments.sugars_100g"]
    if method == "get":
        response = test_client.get(
            "/search", params={"q": "cola", "fields": ",".join(fields)}
        )
    else:
        response = test_client.post("/search", json={"q": "cola", "fields": fields})

    assert response.status_code == 200
    assert response.json()["hits"] == [
        {
            "code": "123",
            "nutriments": {"energy-kcal_100g": 80, "sugars_100g": 0},
            "_score": 1,
        }
    ]


@pytest.mark.parametrize("batch", [False, True])
def test_nested_fields_apply_after_image_postprocessing(batch):
    config = Config.from_yaml(Path("data/config/openfoodfacts.yml")).indices["off"]
    processor = ResultProcessor(config)
    document = {
        "code": "1234567890123",
        "lang": "en",
        "languages_codes": ["en"],
        "selected_images": {
            "front": [{"lc": "en", "rev": 1, "full_size": {"h": 100, "w": 100}}]
        },
    }
    url = generate_image_url(document["code"], "front_en.1.400")

    fields = {"selected_images.front.display.en"}
    if batch:
        actual = processor.process(make_search_response([document]), fields)["hits"][0]
        assert actual.pop("_score") == 1
    else:
        actual = processor.process_result(document, fields)
    assert actual == {"selected_images": {"front": {"display": {"en": url}}}}


def make_search_response(documents):
    return Response(
        Search(),
        {
            "took": 1,
            "timed_out": False,
            "hits": {
                "total": {"value": len(documents), "relation": "eq"},
                "hits": [{"_score": 1, "_source": doc} for doc in documents],
            },
            "aggregations": {},
        },
    )


def test_response_reuses_cached_projection(default_config):
    _prepare_projection.cache_clear()
    fields = {f"missing{i}.value" for i in range(500)} | {"nested.value"}
    processor = BaseResultProcessor(default_config)
    response = make_search_response([{"nested": {"value": 0, "omit": 1}}] * 100)

    assert (
        processor.process(response, fields)["hits"]
        == [{"nested": {"value": 0}, "_score": 1}] * 100
    )
    # One root projection and one nested projection are shared across all hits.
    assert _prepare_projection.cache_info().misses == 2
    assert (
        processor.process(response, {"nested.omit"})["hits"]
        == [{"nested": {"omit": 1}, "_score": 1}] * 100
    )
    assert _prepare_projection.cache_info().maxsize == 128


def test_response_preserves_custom_result_override(default_config):
    class CustomProcessor(BaseResultProcessor):
        def process_result(self, result, projection):
            assert projection == {"code"}
            return {"custom": result["code"]}

    processor = CustomProcessor(default_config)
    response = make_search_response([{"code": "123"}])

    assert processor.process(response, {"code"})["hits"] == [
        {"custom": "123", "_score": 1}
    ]


def test_response_isolates_custom_postprocessor_fields(default_config):
    class CustomProcessor(BaseResultProcessor):
        def process_after(self, result, projection=None):
            assert projection == {"nested"}
            projection.clear()
            return result

    processor = CustomProcessor(default_config)
    response = make_search_response([{"nested": {"value": 0, "omit": 1}}] * 2)

    assert (
        processor.process(response, {"nested.value"})["hits"]
        == [{"nested": {"value": 0}, "_score": 1}] * 2
    )
