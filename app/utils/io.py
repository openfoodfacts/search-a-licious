import gzip
import json
from pathlib import Path
from typing import Callable, Iterable, Union

_orjson_available = True
try:
    import orjson
except ImportError:
    _orjson_available = False


def jsonl_iter(jsonl_path: Union[str, Path]) -> Iterable[dict]:
    """Iterate over elements of a JSONL file.

    :param jsonl_path: the path of the JSONL file. Both plain (.jsonl) and
        gzipped (jsonl.gz) files are supported.
    :yield: dict contained in the JSONL file
    """
    open_fn = get_open_fn(jsonl_path)

    with open_fn(str(jsonl_path), "rt", encoding="utf-8") as f:
        yield from jsonl_iter_fp(f)


def get_open_fn(filepath: Union[str, Path]) -> Callable:
    filepath = str(filepath)
    if filepath.endswith(".gz"):
        return gzip.open
    else:
        return open


def jsonl_iter_fp(fp) -> Iterable[dict]:
    for line in fp:
        line = line.strip("\n")
        if line:
            if _orjson_available:
                yield orjson.loads(line)
            else:
                yield json.loads(line)
