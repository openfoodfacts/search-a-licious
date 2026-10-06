import pytest

from app.config import (
    ESIndexConfig,
    FieldConfig,
    FieldType,
    IndexConfig,
    TaxonomyConfig,
    TaxonomyIndexConfig,
    TaxonomySourceConfig,
)
from app.indexing import (
    DocumentProcessor,
    generate_mapping_object,
    process_taxonomy_field,
    process_text_lang_field,
)


@pytest.mark.parametrize(
    "data,input_field,split,expected",
    [
        (
            {
                "product_name": "MAIN",
                "product_name_fr": "FR",
                "product_name_it": "IT",
                "product_name_pt-BR": "pt-BR",
                "product_name_pt": "pt-PT",
                "product_name_vn": "VN",
                "product_name_id": "ID",
            },
            "product_name",
            False,
            {
                "fr": "FR",
                "it": "IT",
                "pt-BR": "pt-BR",
                "pt": "pt-PT",
                "main": "MAIN",
            },
        ),
        # Same, but without main language
        (
            {
                "product_name_fr": "FR",
            },
            "product_name",
            False,
            {"fr": "FR"},
        ),
    ],
)
def test_process_text_lang_field(data, input_field, split, expected):
    lang_separator = "_"
    split_separator = ","
    supported_langs = {"fr", "it", "pt-BR", "pt"}
    result = process_text_lang_field(
        data=data,
        input_field=input_field,
        split=split,
        lang_separator=lang_separator,
        split_separator=split_separator,
        supported_langs=supported_langs,
    )
    assert result == expected


taxonomy_config = TaxonomyConfig(
    sources=[
        TaxonomySourceConfig(
            name="category",
            url="https://static.openfoodfacts.org/data/taxonomies/categories.full.json",  # type: ignore
        )
    ],
    exported_langs=["en"],
    index=TaxonomyIndexConfig(name="off_taxonomy"),
)


@pytest.mark.parametrize(
    "data, field, taxonomy_config, expected",
    [
        (
            {
                "taxonomy_langs": ["fr", "it"],
                # en:edamame has a "xx" name in the taxonomy
                "categories_tags": "en:beverages,en:alcoholic-beverages,en:not-in-taxonomy,en:edamame",
                # the original name should be saved under an `original` key
                "categories": "Boissons,Boissons alcoolisées,Edamame",
            },
            FieldConfig(
                type=FieldType.taxonomy,
                name="categories",
                input_field="categories_tags",
                split=True,
                taxonomy_name="category",
            ),
            taxonomy_config,
            [
                "en:beverages",
                "en:alcoholic-beverages",
                "en:not-in-taxonomy",
                "en:edamame",
            ],
        ),
        # The field is missing here, we should return None
        (
            {"taxonomy_langs": ["fr", "it"]},
            FieldConfig(
                type=FieldType.taxonomy,
                name="categories",
                input_field="categories_tags",
                split=True,
                taxonomy_name="category",
            ),
            taxonomy_config,
            None,
        ),
    ],
)
def test_process_taxonomy_field(data, field, taxonomy_config, expected):
    split_separator = ","
    output = process_taxonomy_field(
        data=data,
        field=field,
        taxonomy_config=taxonomy_config,
        split_separator=split_separator,
    )

    if expected is None:
        assert output is None
    else:
        assert set(output) == set(expected)


def test_create_mapping(default_config, load_expected_result):
    mapping = generate_mapping_object(default_config)
    data = mapping.to_dict()
    expected_result = load_expected_result("test_mapping", data)
    assert data == expected_result


# ---------------------------------------------------------------------------
# DocumentProcessor.inputs_from_data: object / nested fields
# ---------------------------------------------------------------------------


def _field(name: str, type_: FieldType, **kwargs) -> FieldConfig:
    return FieldConfig(name=name, type=type_, **kwargs)


def _make_processor_config(fields: dict[str, FieldConfig]) -> IndexConfig:
    """Build a minimal IndexConfig with the given (top-level) fields."""
    fields.setdefault("code", _field("code", FieldType.keyword))
    fields.setdefault("last_modified_t", _field("last_modified_t", FieldType.date))
    return IndexConfig(
        index=ESIndexConfig(
            name="test",
            id_field_name="code",
            last_modified_field_name="last_modified_t",
        ),
        fields=fields,
        supported_langs=["en", "main"],
        taxonomy=TaxonomyConfig(
            sources=[
                TaxonomySourceConfig(
                    name="category",
                    url="https://example.org/categories.json",  # type: ignore[arg-type]
                )
            ],
            index=TaxonomyIndexConfig(name="test_taxonomy"),
        ),
        # required by IndexConfig but unused here; None avoids instantiating
        # the real Open Food Facts preprocessor in unit tests.
        preprocessor="app.openfoodfacts.DocumentPreprocessor",
        document_fetcher="app.openfoodfacts.DocumentFetcher",
        result_processor="app.openfoodfacts.ResultProcessor",
    )


def _make_processor(fields: dict[str, FieldConfig]) -> DocumentProcessor:
    return DocumentProcessor(_make_processor_config(fields))


def test_inputs_from_data_object_field():
    config = _make_processor_config(
        {
            "nutriments": _field(
                "nutriments",
                FieldType.object,
                fields={
                    "fat_100g": _field("fat_100g", FieldType.float),
                    "salt_100g": _field("salt_100g", FieldType.float),
                },
            )
        }
    )
    processor = DocumentProcessor(config)
    result = processor.inputs_from_data(
        "ID1", {"nutriments": {"fat_100g": 12.0, "salt_100g": 0.5, "unknonwn": 42}}
    )
    # top-level meta is always present
    assert result["_id"] == "ID1"
    assert "last_indexed_datetime" in result
    # the object field only contains its sub-fields (no meta leak)
    assert result["nutriments"] == {
        "fat_100g": 12.0,
        "salt_100g": 0.5,
    }
    assert "_id" not in result["nutriments"]
    assert "last_indexed_datetime" not in result["nutriments"]


def test_inputs_from_data_nested_field():
    config = _make_processor_config(
        {
            "ingredients": _field(
                "ingredients",
                FieldType.nested,
                fields={
                    "percent": _field("percent", FieldType.float),
                    "id": _field("id", FieldType.keyword, split=True),
                },
            )
        }
    )
    processor = DocumentProcessor(config)
    result = processor.inputs_from_data(
        "ID1",
        {
            "ingredients": [
                {"percent": 10.0, "id": "ing1,ing2"},
                {"percent": 2.0, "unknown": "should be dropped"},
            ]
        },
    )
    assert result["_id"] == "ID1"
    assert result["ingredients"] == [
        {"percent": 10.0, "id": ["ing1", "ing2"]},
        {"percent": 2.0},
    ]
    for item in result["ingredients"]:
        assert "_id" not in item
        assert "last_indexed_datetime" not in item


def test_inputs_from_data_nested_inside_object_recursion():
    config = _make_processor_config(
        {
            "packagings": _field(
                "packagings",
                FieldType.object,
                fields={
                    "materials": _field(
                        "materials",
                        FieldType.nested,
                        fields={
                            "id": _field("id", FieldType.keyword),
                            "recyclable": _field("recyclable", FieldType.bool),
                        },
                    ),
                    "weight": _field("weight", FieldType.float),
                },
            )
        }
    )
    processor = DocumentProcessor(config)
    result = processor.inputs_from_data(
        "ID1",
        {
            "packagings": {
                "weight": 12.5,
                "materials": [
                    {"unknown": "throw", "id": "plastic", "recyclable": False},
                    {"discard": True, "id": "cardboard", "recyclable": True},
                ],
            }
        },
    )
    assert result["packagings"] == {
        "weight": 12.5,
        "materials": [
            {"id": "plastic", "recyclable": False},
            {"id": "cardboard", "recyclable": True},
        ],
    }


def test_inputs_from_data_object_inside_nested_recursion():
    config = _make_processor_config(
        {
            "ingredients": _field(
                "ingredients",
                FieldType.nested,
                fields={
                    "percent": _field("percent", FieldType.float),
                    "source": _field(
                        "source",
                        FieldType.object,
                        fields={
                            "name": _field("name", FieldType.keyword),
                            "uploaded_t": _field("uploaded_t", FieldType.date),
                        },
                    ),
                },
            )
        }
    )
    processor = DocumentProcessor(config)
    result = processor.inputs_from_data(
        "ID1",
        {
            "ingredients": [
                {
                    "percent": 10.0,
                    "source": {"name": "db", "uploaded_t": "1700", "drop": "me"},
                    "toberemoved": True,
                },
                {"percent": 2.0, "source": {"name": "api", "extra": "drop"}},
            ]
        },
    )
    assert result["ingredients"] == [
        {
            "percent": 10.0,
            "source": {"name": "db", "uploaded_t": "1700"},
        },
        {"percent": 2.0, "source": {"name": "api"}},
    ]
