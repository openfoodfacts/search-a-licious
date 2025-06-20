import gzip
import shutil
from pathlib import Path
from typing import Callable, Iterable

import orjson


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


def safe_replace_dir(target: Path, new_target: Path):
    """Replace a directory atomically"""
    # a temporary place for the target dir
    old_target = target.with_suffix(target.suffix + ".old")
    # move target to old_target
    if old_target.exists():
        shutil.rmtree(old_target)
    if target.exists():
        shutil.move(target, old_target)
    # move our file
    try:
        shutil.move(new_target, target)
    except Exception:
        # if something went wrong, we restore the old target
        if old_target.exists():
            shutil.move(old_target, target)
        # reraise
        raise
    else:
        # cleanup
        if old_target.exists():
            shutil.rmtree(old_target)
