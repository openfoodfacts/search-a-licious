from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app._import import MAX_LOGGED_ERRORS, _error_kind, run_items_import


def _bulk_error(i: int, kind: str = "document_parsing_exception") -> dict:
    return {
        "index": {
            "_id": f"{i:05}",
            "status": 400,
            "error": {"type": kind, "reason": "x" * 300},
        }
    }


def _run_import(results, default_config):
    """Run an import where the processes give `results`
    (a list of `(process number, indexed documents, errors)`)"""
    pool = MagicMock()
    pool.return_value.__enter__.return_value = pool.return_value
    # several processes are run by the pool, a single one directly
    pool.return_value.starmap.return_value = results
    with (
        patch("app._import.connection"),
        patch("app._import.generate_index_object"),
        patch("app._import.wait_index_health"),
        patch("app._import.Pool", pool),
        patch("app._import.import_parallel", side_effect=results),
        patch("app._import.update_alias"),
    ):
        return run_items_import(
            Path("items.jsonl"),
            len(results),
            default_config,
            skip_updates=True,
        )


@pytest.mark.parametrize(
    "error, kind",
    [
        (_bulk_error(1), "index/document_parsing_exception"),
        (_bulk_error(1, "mapper_parsing_exception"), "index/mapper_parsing_exception"),
        (
            {"delete": {"status": 500, "error": {"type": "boom", "reason": "x"}}},
            "delete/boom",
        ),
        # the documents that could not be prepared
        (
            {"document_preparation_error": {"id": "1", "error": "ValueError: boom"}},
            "document_preparation_error/ValueError",
        ),
        ({"index": {"status": 400, "error": "mapping"}}, "index/mapping"),
        ({"delete": {"status": 404}}, "delete"),
        ({}, "unknown"),
        ("not a dict", "unknown"),
    ],
)
def test_error_kind(error, kind):
    assert _error_kind(error) == kind


def test_many_errors_are_counted_in_full_and_logged_in_part(default_config, caplog):
    errors = [_bulk_error(i) for i in range(25)]
    with caplog.at_level("INFO"):
        num_errors = _run_import([(0, 100, errors)], default_config)
    assert num_errors == 25
    assert "Encountered 25 errors (the first 10 are shown)" in caplog.text
    assert "'_id': '00009'" in caplog.text
    assert "'_id': '00010'" not in caplog.text
    # the line stays small whatever the number of errors
    line = next(r.getMessage() for r in caplog.records if "Encountered" in r.message)
    assert len(line) < 10 * 700


def test_few_errors_are_all_logged(default_config, caplog):
    errors = [_bulk_error(i) for i in range(3)]
    with caplog.at_level("INFO"):
        assert _run_import([(0, 100, errors)], default_config) == 3
    assert "Encountered 3 errors:" in caplog.text
    assert "the first" not in caplog.text
    assert "'_id': '00002'" in caplog.text


def test_max_logged_errors_is_ten():
    assert MAX_LOGGED_ERRORS == 10


def test_summary_of_the_import(default_config, caplog):
    results = [
        (0, 100, [_bulk_error(1), _bulk_error(2)]),
        (
            1,
            50,
            [
                _bulk_error(3),
                {"document_preparation_error": {"id": "9", "error": "KeyError: 'x'"}},
            ],
        ),
    ]
    with caplog.at_level("INFO"):
        num_errors = _run_import(results, default_config)
    assert num_errors == 4
    assert (
        "Import of the file: 150 documents indexed, 4 errors: "
        "3 x index/document_parsing_exception, "
        "1 x document_preparation_error/KeyError"
    ) in caplog.text


def test_summary_of_an_import_without_error(default_config, caplog):
    with caplog.at_level("INFO"):
        assert _run_import([(0, 7, [])], default_config) == 0
    assert "Import of the file: 7 documents indexed, 0 errors" in caplog.text
    assert "Encountered" not in caplog.text
