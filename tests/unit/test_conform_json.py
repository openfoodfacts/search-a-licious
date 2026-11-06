from typing import Any

import pytest

from app.config import FieldConfig, FieldType, IndexConfig
from app.utils.conform_json import conform_json_to_config


def _field(
    name: str,
    type_: FieldType,
    fields: dict[str, FieldConfig] | None = None,
) -> FieldConfig:
    return FieldConfig(name=name, type=type_, fields=fields)


def _make_config(fields: dict[str, FieldConfig]) -> IndexConfig:
    """Build a minimal IndexConfig with only the given fields.

    IndexConfig requires ``index`` and ``taxonomy`` and a date
    last_modified_field_name; we set those up with a single date field.
    """
    from app.config import (
        ESIndexConfig,
        TaxonomyConfig,
        TaxonomyIndexConfig,
        TaxonomySourceConfig,
    )

    if "code" not in fields:
        fields["code"] = _field("code", FieldType.keyword)
    if "last_modified_t" not in fields:
        fields["last_modified_t"] = _field("last_modified_t", FieldType.date)

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
                    name="categories",
                    url="https://example.org/categories.json",  # type: ignore[arg-type]
                )
            ],
            index=TaxonomyIndexConfig(name="test_taxonomy"),
        ),
        # will be ignored but needs to be set for IndexConfig validation
        preprocessor="app.openfoodfacts.DocumentPreprocessor",
        document_fetcher="app.openfoodfacts.DocumentFetcher",
        result_processor="app.openfoodfacts.ResultProcessor",
    )


def assert_types_equal(result, expected):
    """when we test for equality of two objects in python,
    it does not necessarily mean they are of the same type
    With this method we also ensure this
    """
    assert type(result) is type(expected)
    if isinstance(result, dict):
        assert result.keys() == expected.keys()
        for key in result:
            assert_types_equal(result[key], expected[key])
    elif isinstance(result, list):
        assert len(result) == len(expected)
        for i in range(len(result)):
            assert_types_equal(result[i], expected[i])


# ---------------------------------------------------------------------------
# bool
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (1, True),
        (0, False),
        ("true", True),
        ("false", False),
        ("True", True),
        ("False", False),
        ("yes", True),
        ("no", False),
        ("on", True),
        ("off", False),
        ("anything", True),
        ("", False),
        ("0", False),
        ("null", False),
        ("none", False),
        (True, True),
        (False, False),
    ],
)
def test_bool_coercion(value, expected):
    config = _make_config({"obsolete": _field("obsolete", FieldType.bool)})
    doc = {"obsolete": value}
    conform_json_to_config(doc, config)
    expected = {"obsolete": expected}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_bool_none_dropped():
    config = _make_config({"obsolete": _field("obsolete", FieldType.bool)})
    doc = {"obsolete": None}
    conform_json_to_config(doc, config)
    assert "obsolete" not in doc


def test_bool_list_coercion():
    config = _make_config({"flags": _field("flags", FieldType.bool)})
    doc = {"flags": [1, 0, "true", "false", "yes"]}
    conform_json_to_config(doc, config)
    expected = {"flags": [True, False, True, False, True]}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_bool_list_all_dropped():
    config = _make_config({"flags": _field("flags", FieldType.bool)})
    doc = {"flags": [None, None]}
    conform_json_to_config(doc, config)
    assert "flags" not in doc


# ---------------------------------------------------------------------------
# numeric
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "type_,value,expected",
    [
        (FieldType.float, 1, 1.0),
        (FieldType.float, "1.5", 1.5),
        (FieldType.double, 3, 3.0),
        (FieldType.integer, 1.7, 1),
        (FieldType.integer, "42", 42),
        (FieldType.short, 2.9, 2),
        (FieldType.long, "100", 100),
        (FieldType.unsigned_long, 7, 7),
        (FieldType.half_float, "0.5", 0.5),
    ],
)
def test_numeric_coercion(type_, value, expected):
    config = _make_config({"v": _field("v", type_)})
    doc = {"v": value}
    conform_json_to_config(doc, config)
    assert doc["v"] == expected
    if type_ in (
        FieldType.integer,
        FieldType.short,
        FieldType.long,
        FieldType.unsigned_long,
    ):
        assert isinstance(doc["v"], int)
    else:
        assert isinstance(doc["v"], float)


def test_numeric_unparseable_dropped():
    config = _make_config({"v": _field("v", FieldType.float)})
    doc = {"v": "abc"}
    conform_json_to_config(doc, config)
    assert "v" not in doc


def test_numeric_bool_treated_as_int():
    # bool is a subclass of int; it should be treated as 1/0, not dropped.
    config = _make_config({"v": _field("v", FieldType.integer)})
    doc = {"v": True}
    conform_json_to_config(doc, config)
    expected = {"v": 1}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_numeric_list_coercion():
    config = _make_config({"v": _field("v", FieldType.float)})
    doc = {"v": [1, 2, "3.5", 4]}
    conform_json_to_config(doc, config)
    expected = {"v": [1.0, 2.0, 3.5, 4.0]}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_numeric_list_partial_failure():
    config = _make_config({"v": _field("v", FieldType.integer)})
    doc = {"v": ["1", "abc", 3, "4"]}
    conform_json_to_config(doc, config)
    expected = {"v": [1, 3, 4]}
    assert doc == expected
    assert_types_equal(doc, expected)


# ---------------------------------------------------------------------------
# date
# ---------------------------------------------------------------------------


def test_date_stringified_epoch_to_int():
    config = _make_config(
        {"last_modified_t": _field("last_modified_t", FieldType.date)}
    )
    doc = {"last_modified_t": "1700000000"}
    conform_json_to_config(doc, config)
    expected = {"last_modified_t": 1700000000}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_date_int_untouched():
    config = _make_config(
        {"last_modified_t": _field("last_modified_t", FieldType.date)}
    )
    doc = {"last_modified_t": 1700000000}
    conform_json_to_config(doc, config)
    expected = {"last_modified_t": 1700000000}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_date_iso_string_untouched():
    config = _make_config(
        {"last_modified_t": _field("last_modified_t", FieldType.date)}
    )
    doc = {"last_modified_t": "2023-11-14T12:00:00Z"}
    conform_json_to_config(doc, config)
    expected = {"last_modified_t": "2023-11-14T12:00:00Z"}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_date_float_epoch_untouched():
    config = _make_config(
        {"last_modified_t": _field("last_modified_t", FieldType.date)}
    )
    doc = {"last_modified_t": 1700000000.5}
    conform_json_to_config(doc, config)
    expected = {"last_modified_t": 1700000000.5}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_date_empty_string_dropped():
    config = _make_config(
        {"last_modified_t": _field("last_modified_t", FieldType.date)}
    )
    doc = {"last_modified_t": ""}
    conform_json_to_config(doc, config)
    assert "last_modified_t" not in doc


# ---------------------------------------------------------------------------
# untouched types
# ---------------------------------------------------------------------------


def test_keyword_untouched():
    config = _make_config({"code": _field("code", FieldType.keyword)})
    doc = {"code": "12345"}
    conform_json_to_config(doc, config)
    expected = {"code": "12345"}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_text_untouched():
    config = _make_config({"quantity": _field("quantity", FieldType.text)})
    doc = {"quantity": "500g"}
    conform_json_to_config(doc, config)
    expected = {"quantity": "500g"}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_disabled_untouched():
    config = _make_config(
        {"forest_footprint": _field("forest_footprint", FieldType.disabled)}
    )
    doc = {"forest_footprint": {"a": 1}}
    conform_json_to_config(doc, config)
    expected = {"forest_footprint": {"a": 1}}
    assert doc == expected
    assert_types_equal(doc, expected)


# ---------------------------------------------------------------------------
# object / nested recursion
# ---------------------------------------------------------------------------


def test_object_subfields_coerced():
    config = _make_config(
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
    doc = {"nutriments": {"fat_100g": "12", "salt_100g": 0.5, "untouched": "x"}}
    conform_json_to_config(doc, config)
    expected = {"nutriments": {"fat_100g": 12.0, "salt_100g": 0.5, "untouched": "x"}}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_nested_subfields_with_recursion():
    config = _make_config(
        {
            "ingredients": _field(
                "ingredients",
                FieldType.nested,
                fields={
                    "percent": _field("percent", FieldType.float),
                    "is_in_taxonomy": _field("is_in_taxonomy", FieldType.bool),
                },
            )
        }
    )
    doc = {
        "ingredients": [
            {
                "percent": "10",
                "is_in_taxonomy": 1,
                "ingredients": [
                    {"percent": 5, "is_in_taxonomy": 0},
                    {"percent": 2, "is_in_taxonomy": 1},
                ],
            },
        ]
    }
    conform_json_to_config(doc, config)
    expected = {
        "ingredients": [
            {
                "percent": 10.0,
                "is_in_taxonomy": True,
                "ingredients": [
                    {"percent": 5.0, "is_in_taxonomy": False},
                    {"percent": 2.0, "is_in_taxonomy": True},
                ],
            }
        ]
    }
    assert doc == expected
    assert_types_equal(doc, expected)


def test_nested_subfields_coerced_in_list():
    # the case of a nested field that has a subfield with the same name as itself
    config = _make_config(
        {
            "ingredients": _field(
                "ingredients",
                FieldType.nested,
                fields={
                    "percent": _field("percent", FieldType.float),
                    "is_in_taxonomy": _field("is_in_taxonomy", FieldType.bool),
                },
            )
        }
    )
    doc = {
        "ingredients": [
            {"percent": "10", "is_in_taxonomy": 1},
            {"percent": 5, "is_in_taxonomy": 0},
        ]
    }
    conform_json_to_config(doc, config)
    expected = {
        "ingredients": [
            {"percent": 10.0, "is_in_taxonomy": True},
            {"percent": 5.0, "is_in_taxonomy": False},
        ]
    }
    assert doc == expected
    assert_types_equal(doc, expected)


def test_nested_subfield_dropped_on_failure():
    config = _make_config(
        {
            "ingredients": _field(
                "ingredients",
                FieldType.nested,
                fields={
                    "percent": _field("percent", FieldType.float),
                },
            )
        }
    )
    doc = {"ingredients": [{"percent": "abc"}, {"percent": "2"}]}
    conform_json_to_config(doc, config)
    expected = {"ingredients": [{}, {"percent": 2.0}]}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_nested_present_as_dict_handled():
    # Defensive: a nested field arriving as a single dict is also handled.
    config = _make_config(
        {
            "ingredients": _field(
                "ingredients",
                FieldType.nested,
                fields={
                    "percent": _field("percent", FieldType.float),
                },
            )
        }
    )
    doc = {"ingredients": {"percent": "10"}}
    conform_json_to_config(doc, config)
    expected = {"ingredients": {"percent": 10.0}}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_deeply_nested_recursion():
    config = _make_config(
        {
            "packagings": _field(
                "packagings",
                FieldType.nested,
                fields={
                    "weight_measured": _field("weight_measured", FieldType.float),
                    "source": _field(
                        "source",
                        FieldType.object,
                        fields={
                            "uploaded_t": _field("uploaded_t", FieldType.date),
                        },
                    ),
                },
            )
        }
    )
    doc = {
        "packagings": [
            {"weight_measured": "12.5", "source": {"uploaded_t": "1700"}},
        ]
    }
    conform_json_to_config(doc, config)
    expected = {
        "packagings": [
            {"weight_measured": 12.5, "source": {"uploaded_t": 1700}},
        ]
    }
    assert doc == expected
    assert_types_equal(doc, expected)


# ---------------------------------------------------------------------------
# general behaviour
# ---------------------------------------------------------------------------


def test_unknown_keys_left_as_is():
    config = _make_config({"obsolete": _field("obsolete", FieldType.bool)})
    doc = {"obsolete": 1, "unknown_field": "value", "another": [1, 2]}
    conform_json_to_config(doc, config)
    expected = {
        "obsolete": True,
        "unknown_field": "value",
        "another": [1, 2],
    }
    assert doc == expected
    assert_types_equal(doc, expected)


def test_missing_field_skipped():
    config = _make_config({"obsolete": _field("obsolete", FieldType.bool)})
    doc = {"other": 1}
    conform_json_to_config(doc, config)
    expected = {"other": 1}
    assert doc == expected
    assert_types_equal(doc, expected)


def test_empty_document():
    config = _make_config({"obsolete": _field("obsolete", FieldType.bool)})
    doc: dict[str, Any] = {}
    conform_json_to_config(doc, config)
    assert doc == {}
