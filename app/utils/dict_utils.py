from __future__ import annotations


def get_nested_value(key, d):
    """
    Get a key in the form a.b.c in the nested dict d
    """
    for part in key.split("."):
        # Handle nested with properties too
        if "properties" in d:
            d = d["properties"]
        d = d[part]
    return d
