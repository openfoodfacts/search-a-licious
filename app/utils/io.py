import gzip
import json
from pathlib import Path
from typing import Callable, Iterable

import orjson

from app.types import JSONType


def load_json(filepath: str | Path) -> dict | list:
    """Load a JSON file, support gzipped JSON files.

    :param path: the path of the file
    """
    open = get_open_fn(filepath)
    with open(filepath, "rb") as f:
        return orjson.loads(f.read())


def jsonl_iter(jsonl_path: str | Path) -> Iterable[dict]:
    """Iterate over elements of a JSONL file.

    :param jsonl_path: the path of the JSONL file. Both plain (.jsonl) and
        gzipped (jsonl.gz) files are supported.
    :yield: dict contained in the JSONL file
    """
    open_fn = get_open_fn(jsonl_path)

    with open_fn(str(jsonl_path), "rt", encoding="utf-8") as f:
        yield from jsonl_iter_fp(f)


def get_open_fn(filepath: str | Path) -> Callable:
    filepath = str(filepath)
    if filepath.endswith(".gz"):
        return gzip.open
    else:
        return open


def jsonl_iter_fp(fp) -> Iterable[dict]:
    for line in fp:
        line = line.strip("\n")
        if line:
            yield orjson.loads(line)


def dump_json(path: str | Path, item: JSONType, **kwargs):
    """Dump an object in a JSON file.

    :param path: the path of the file
    :param item: the item to serialize
    """
    open_fn = get_open_fn(path)
    with open_fn(str(path), "wb") as f:
        f.write(orjson.dumps(item, **kwargs))
