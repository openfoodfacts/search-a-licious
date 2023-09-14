"""
This script was used as a one-off to generate the JSON schema, and the Product model.

It works by iterating through the products.bson file and generating a large product by combining them. This is then
used to create a JSON schema.

Finally, the JSON schema is converted to a series of elasticsearch_dsl fields.

However, there are so many undocumented and rare fields, that the Product model had to be manually edited after this
process (otherwise the import would throw errors due to documents having different field types as they were imported).
So, we can't easily reconstruct the model from this script.

However, if you do wish to run again, follow these instructions:
Run this script for generate_json_schema() only
Use schema converter from https://www.liquid-technologies.com/online-json-to-schema-converter
- Array rules: List validation
- Make required: False
- Infer enums: False

Then run this script with generate_es_schema only
"""
from __future__ import annotations

import argparse
import json

import bson


def dict_merge(dct, merge_dct):
    """Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.
    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None
    """
    for k, v in merge_dct.items():
        if (
            k in dct and isinstance(dct[k], dict) and isinstance(merge_dct[k], dict)
        ):  # noqa
            if len(merge_dct[k]) > len(dct[k]):
                dict_merge(dct[k], merge_dct[k])
        if (
            k in dct and isinstance(dct[k], list) and isinstance(merge_dct[k], list)
        ):  # noqa
            if len(merge_dct[k]) > len(dct[k]):
                dct[k] = merge_dct[k]
        else:
            dct[k] = merge_dct[k]

    return dct


def generate_json_schema(filename):
    extensive_dict = {}
    with open(filename, "rb") as f:
        for i, row in enumerate(bson.decode_file_iter(f)):
            extensive_dict = dict_merge(extensive_dict, row)
            if i == 1000:
                break

    # Remove ocr tags
    dupe_dict = {}
    for k, v in extensive_dict.items():
        if "_ocr_" not in k:
            dupe_dict[k] = v

    extensive_dict = dupe_dict
    json_data = json.dumps(extensive_dict, indent=4)
    # We need to do this hack since this is not a valid variable name in Python:
    json_data = json_data.replace(
        "fruits-vegetables-nuts_100g_estimate",
        "fruits_vegetables_nuts_100g_estimate",
    )
    print(json_data)


VALUE_TYPE_TO_ELASTICSEARCH = {
    "string": "Keyword({})",
    "null": "Keyword({})",
    "integer": "Double({})",
    "number": "Double({})",
}
exclude = set({"categories", "brands", "product_name", "code", "_id"})


def print_indent(nesting_level):
    print("    " * nesting_level, end="")


def print_es_schema_node(key, value, nesting_level, skip_comma=False):
    print_indent(nesting_level)
    if not nesting_level:
        print("{} = {}".format(key, value))
    else:
        if skip_comma:
            print("'{}': {}".format(key, value))
        else:
            print("'{}': {},".format(key, value))


def generate_es_schema_node(key, value, nesting_level=0):
    # for k, v in node.items():
    if key in exclude:
        return
    value_type = value["type"]
    # Occasionally value_type is a list, if so, just pick the first element
    if type(value_type) == list:
        value_type = value_type[0]
    if value_type in VALUE_TYPE_TO_ELASTICSEARCH and "items" not in value:
        elasticsearch_value_type = VALUE_TYPE_TO_ELASTICSEARCH[value_type].format(
            "",
        )
        print_es_schema_node(key, elasticsearch_value_type, nesting_level)
        return

    # Will either be array or object now
    assert value_type in ["array", "object"], value_type
    if value_type == "array" and len(value["items"]) == 1:
        # In this case, we're just an array - that value should be type, but if not set just use string
        elasticsearch_value_type = VALUE_TYPE_TO_ELASTICSEARCH[
            value["items"].get(
                "type",
                "string",
            )
        ]
        elasticsearch_value_type = elasticsearch_value_type.format(
            "multi=True",
        )
        print_es_schema_node(key, elasticsearch_value_type, nesting_level)
        return

    # Finally, array of objects (like ingredients)
    multi = False
    if value_type == "array":
        multi = True
        sub_type = value["items"]["type"]
        if sub_type != "object":
            # nova_groups_markers has an array of arrays, skip this
            return
        assert value["items"]["type"] == "object"
        value_type = "object"
        value = value["items"]

    if value_type == "object":
        print_es_schema_node(key, "Nested(", nesting_level, skip_comma=True)
        print_indent(nesting_level + 1)
        print("properties={")

        for k, v in value.get("properties", {}).items():
            generate_es_schema_node(k, v, nesting_level + 2)
        print_indent(nesting_level + 1)
        print("},")
        if multi:
            print_indent(nesting_level + 1)
            print("multi=True,")
        print_indent(nesting_level)
        if nesting_level:
            print("),")
        else:
            print(")")


def generate_es_schema():
    with open("app/product.schema.json") as f:
        product_json_schema = json.load(f)
    product_json_schema = product_json_schema["properties"]
    print(product_json_schema)

    for k, v in product_json_schema.items():
        generate_es_schema_node(k, v)


if __name__ == "__main__":
    parser = argparse.ArgumentParser("perform_import")
    parser.add_argument(
        "--filename",
        help="Filename where Mongo products.bson file is located",
        type=str,
        defaut="",
    )
    args = parser.parse_args()
    generate_json_schema(args.filename)
    generate_es_schema()
