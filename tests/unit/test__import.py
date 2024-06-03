import datetime
import json
import tempfile
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

from redis import Redis

from app._import import (
    BaseDocumentFetcher,
    gen_documents,
    get_document_dict,
    get_new_updates,
    get_processed_since,
    load_document_fetcher,
    run_update_daemon,
    update_alias,
)
from app._types import JSONType
from app.config import Config, IndexConfig
from app.indexing import DocumentProcessor


class RedisXrangeClient:
    def __init__(self, xrange_return_values: list):
        self.xrange_return_values = xrange_return_values
        self.call_count = 0

    def xrange(
        self, name: str, min: str = "-", max: str = "+", count: int | None = None
    ):
        assert name == "product_updates_off"
        assert max == "+"
        assert count == 100
        if self.call_count >= len(self.xrange_return_values):
            return []
        self.call_count += 1
        return self.xrange_return_values[self.call_count - 1]


class DocumentFetcher(BaseDocumentFetcher):
    def __init__(self, config: IndexConfig, *args, **kwargs):
        self.missing_documents = kwargs.pop("missing_documents", set())
        super().__init__(config, *args, **kwargs)

    def fetch_document(self, stream_name: str, item: JSONType) -> JSONType | None:
        assert stream_name == "product_updates_off"
        id_ = item["code"]
        if id_ in self.missing_documents:
            return None
        return {"code": id_, "name": f"Document {id_}"}


def test_get_processed_since(default_config: IndexConfig):
    id_field_name = default_config.index.id_field_name
    return_values = [
        [
            ("1629878400000-0", {"code": "1"}),
            ("1629878400001-0", {"code": "2"}),
            ("1629878400002-0", {"code": "3"}),
            # Two updates for the same document, only the first one should be
            # returned
            ("1629878400003-0", {"code": "1"}),
            # Document 4 is missing, it should be skipped
            ("1629878400004-0", {"code": "4"}),
        ]
    ]
    redis_client = cast(Redis, RedisXrangeClient(return_values))
    # Wed Aug 25 08:00:00 2021 UTC
    start_timestamp_ms = 1629878400000  # Example start timestamp
    document_fetcher = DocumentFetcher(default_config, missing_documents={"4"})

    # Call the function and iterate over the results
    results = list(
        get_processed_since(
            redis_client,
            cast(str, default_config.redis_stream_name),
            start_timestamp_ms,
            id_field_name,
            document_fetcher,
        )
    )

    # Assertions
    assert len(results) == 3
    assert results[0] == (1629878400000, {"code": "1", "name": "Document 1"})
    assert results[1] == (1629878400001, {"code": "2", "name": "Document 2"})
    assert results[2] == (1629878400002, {"code": "3", "name": "Document 3"})

    results = list(
        get_processed_since(
            redis_client,
            cast(str, default_config.redis_stream_name),
            start_timestamp_ms,
            id_field_name,
            document_fetcher,
        )
    )
    # Check that results are empty
    assert not results


class RedisXreadClient:
    def __init__(self, xread_return_values: list):
        self.xread_return_values = xread_return_values
        self.call_count = 0

    def xread(self, streams: dict, block: int, count: int | None = None):
        assert set(streams.keys()) == {"product_updates_off"}
        assert block == 0
        assert count == 100
        if self.call_count >= len(self.xread_return_values):
            raise ValueError("No more values")
        self.call_count += 1
        return self.xread_return_values[self.call_count - 1]


def test_get_new_updates(default_config: IndexConfig):
    redis_stream_name = cast(str, default_config.redis_stream_name)
    return_values = [
        [
            (
                redis_stream_name,
                [("1629878400002-0", {"code": "4"})],
            )
        ],
        [
            (
                redis_stream_name,
                [("1629878400000-0", {"code": "1"})],
            )
        ],
        [
            (
                redis_stream_name,
                [("1629878400001-0", {"code": "2"})],
            )
        ],
        [
            (
                redis_stream_name,
                [("1629878400003-0", {"code": "3"})],
            )
        ],
    ]
    redis_client = cast(Redis, RedisXreadClient(return_values))
    document_fetcher = DocumentFetcher(default_config, missing_documents={"4"})

    # Call the function and iterate over the results
    updates_iter = get_new_updates(
        redis_client,
        [redis_stream_name],
        {redis_stream_name: default_config.index.id_field_name},
        {redis_stream_name: document_fetcher},
    )

    results = next(updates_iter)
    assert results == (
        redis_stream_name,
        1629878400000,
        {"code": "1", "name": "Document 1"},
    )


def test_load_document_fetcher(default_config):
    fetcher = load_document_fetcher(default_config)
    assert isinstance(fetcher, BaseDocumentFetcher)


def test_get_document_dict(default_config):
    class MockDocumentProcessor:
        def from_dict(self, row):
            if row["_id"] == "id1":
                return {
                    "field1_processed": row["field1"],
                    "field2_processed": row["field2"],
                    "_id": row["_id"],
                }
            return None

    processor = MockDocumentProcessor()
    next_index = "index1"
    row_1 = {"field1": "value1", "field2": "value2", "_id": "id1"}
    row_2 = {"field1": "value1", "field2": "value2", "_id": "id2"}

    assert get_document_dict(processor, row_1, next_index) == {
        "_source": {"field1_processed": "value1", "field2_processed": "value2"},
        "_index": "index1",
        "_id": "id1",
    }
    assert get_document_dict(processor, row_2, next_index) is None


def test_gen_documents(default_config):
    processor = DocumentProcessor(default_config)
    tmp_path = Path(tempfile.mkdtemp()) / "input.jsonl"

    items = [
        {"categories_tags": ["en:beverages"], "code": f"{i:03}"} for i in range(150)
    ]
    # Make the first item invalid
    items[0].pop("code")
    tmp_path.write_text("\n".join(json.dumps(item) for item in items))
    next_index = "index1"
    start_datetime = datetime.datetime.utcnow()
    num_items = 100
    num_processes = 4
    process_id = 0

    documents = list(
        gen_documents(
            processor,
            tmp_path,
            next_index,
            num_items,
            num_processes,
            process_id,
        )
    )
    tmp_path.unlink()
    tmp_path.parent.rmdir()

    assert len(documents) == 24  # (100 / 4) - 1 = 24

    ids = [f"{i:03}" for i in range(num_items) if i % num_processes == 0]
    ids.pop(0)  # Remove the first item which is invalid
    for i in range(len(documents)):
        document = documents[i]
        assert (
            document["_index"] == next_index
        )  # All documents should have the same index
        assert "last_indexed_datetime" in document["_source"]
        last_indexed_datetime = document["_source"].pop("last_indexed_datetime")
        assert isinstance(last_indexed_datetime, str)
        assert datetime.datetime.fromisoformat(last_indexed_datetime) > start_datetime
        assert "categories" in document["_source"]
        categories = {
            lang: set(names)
            for lang, names in document["_source"].pop("categories").items()
        }
        assert categories == {
            "de": {"Getränke"},
            "en": {"Beverages", "Drinks"},
            "es": {"Bebidas"},
            "fr": {"Boissons"},
            "it": {"Bevande"},
            "nl": {"Drank", "Dranken"},
        }
        assert document["_source"] == {
            "categories_tags": ["en:beverages"],
            "code": ids[i],
        }


def test_update_alias(default_config):
    es_mock = MagicMock()
    next_index = "index1"
    index_alias = "alias1"

    update_alias(es_mock, next_index, index_alias)

    es_mock.indices.update_aliases.assert_called_once_with(
        actions=[
            {
                "remove": {
                    "alias": index_alias,
                    "index": f"{index_alias}-*",
                },
            },
            {"add": {"alias": index_alias, "index": next_index}},
        ]
    )


def test_run_update_daemon(default_global_config: Config):
    off_config: IndexConfig = default_global_config.indices["off"]
    es_client_mock = MagicMock()
    redis_client_mock = MagicMock()
    document_fetcher_mock = DocumentFetcher(off_config)

    # Replace with your desired test data
    updates = [
        ("product_updates_off", 1629878400000, {"code": "1", "name": "Document 1"}),
        ("product_updates_off", 1629878400001, {"code": "2", "name": "Document 2"}),
        ("product_updates_off", 1629878400002, {"code": "3", "name": "Document 3"}),
    ]

    # Mock the necessary dependencies
    connection_mock = MagicMock()
    connection_mock.get_es_client.return_value = es_client_mock
    connection_mock.get_redis_client.return_value = redis_client_mock
    load_document_fetcher_mock = MagicMock(return_value=document_fetcher_mock)

    # Patch the necessary functions and objects
    with patch("app._import.connection", connection_mock), patch(
        "app._import.load_document_fetcher", load_document_fetcher_mock
    ), patch("app._import.get_new_updates", MagicMock(return_value=updates)):
        # Call the function
        run_update_daemon(default_global_config)

    # Assertions
    connection_mock.get_es_client.assert_called_once()
    connection_mock.get_redis_client.assert_called_once()
    load_document_fetcher_mock.assert_called_once_with(off_config)

    for i, mock_call in enumerate(es_client_mock.index.mock_calls):
        assert mock_call.args == ()
        kwargs = mock_call.kwargs
        assert set(kwargs.keys()) == {"index", "body", "id"}
        assert kwargs["id"] == str(i + 1)
        assert kwargs["body"]["code"] == str(i + 1)
        assert isinstance(kwargs["body"]["last_indexed_datetime"], str)
