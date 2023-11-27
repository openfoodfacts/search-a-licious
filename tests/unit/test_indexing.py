import pytest

from app.config import (
    FieldConfig,
    FieldType,
    TaxonomyConfig,
    TaxonomyIndexConfig,
    TaxonomySourceConfig,
)
from app.indexing import process_taxonomy_field, process_text_lang_field


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
                "other": ["VN", "ID"],
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
    assert (
        process_text_lang_field(
            data=data,
            input_field=input_field,
            split=split,
            lang_separator=lang_separator,
            split_separator=split_separator,
            supported_langs=supported_langs,
        )
        == expected
    )


taxonomy_config = TaxonomyConfig(
    sources=[
        TaxonomySourceConfig(
            name="category",
            url="https://static.openfoodfacts.org/data/taxonomies/categories.full.json",  # type: ignore
        )
    ],
    exported_langs=["en"],
    index=TaxonomyIndexConfig(),
)


@pytest.mark.parametrize(
    "data, field, taxonomy_config, taxonomy_langs, expected",
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
                add_taxonomy_synonyms=True,
                taxonomy_name="category",
            ),
            taxonomy_config,
            {"en"},
            {
                "fr": [
                    "Boissons",
                    "alcool",
                    "alcools",
                    "boisson alcoolisée",
                    "Boissons alcoolisées",
                    "Edamame",
                ],
                "it": ["Bevande", "Bevande alcoliche", "Edamame"],
                "en": [
                    "Drinks",
                    "Beverages",
                    "Alcoholic beverages",
                    "drinks with alcohol",
                    "alcohols",
                    "Alcoholic drinks",
                    "Edamame",
                ],
                "original": "Boissons,Boissons alcoolisées,Edamame",
            },
        ),
        # Same, but without synonyms
        (
            {
                "taxonomy_langs": ["fr", "it"],
                "categories_tags": "en:beverages,en:alcoholic-beverages",
            },
            FieldConfig(
                type=FieldType.taxonomy,
                name="categories",
                input_field="categories_tags",
                split=True,
                add_taxonomy_synonyms=False,
                taxonomy_name="category",
            ),
            taxonomy_config,
            {"en"},
            {
                "fr": [
                    "Boissons",
                    "Boissons alcoolisées",
                ],
                "it": ["Bevande", "Bevande alcoliche"],
                "en": [
                    "Beverages",
                    "Alcoholic beverages",
                ],
            },
        ),
        # The field is missing here, we should return None
        (
            {"taxonomy_langs": ["fr", "it"]},
            FieldConfig(
                type=FieldType.taxonomy,
                name="categories",
                input_field="categories_tags",
                split=True,
                add_taxonomy_synonyms=False,
                taxonomy_name="category",
            ),
            taxonomy_config,
            {"en"},
            None,
        ),
    ],
)
def test_process_taxonomy_field(data, field, taxonomy_config, taxonomy_langs, expected):
    split_separator = ","
    output = process_taxonomy_field(
        data=data,
        field=field,
        taxonomy_config=taxonomy_config,
        split_separator=split_separator,
        taxonomy_langs=taxonomy_langs,
    )

    if expected is None:
        assert output is None
    else:
        assert set(output.keys()) == set(expected.keys())
        for key in expected.keys():
            assert set(output[key]) == set(expected[key])
