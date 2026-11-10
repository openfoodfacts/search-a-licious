import datetime
import json
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import elasticsearch
import pytest
import redis.exceptions as redis_exceptions
from elasticsearch import NotFoundError
from redis import Redis

from app._import import (
    BaseDocumentFetcher,
    gen_documents,
    gen_taxonomy_documents,
    get_document_dict,
    get_new_updates,
    get_processed_since,
    get_redis_updates,
    is_retryable_error,
    load_document_fetcher,
    reset_checkpoint_after_import,
    retry_delay,
    run_items_import,
    run_update_daemon,
    update_alias,
)
from app._types import FetcherResult, FetcherStatus, JSONType
from app.config import Config, IndexConfig
from app.indexing import DocumentProcessor
from app.taxonomy import Taxonomy, TaxonomyNode


def api_meta_response(status: int):
    """Build the response metadata needed to construct an ApiError"""
    import elastic_transport

    return elastic_transport.ApiResponseMeta(
        status=status,
        http_version="1.1",
        headers=elastic_transport.HttpHeaders(),
        duration=0.0,
        node=None,  # type: ignore[arg-type]
    )


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

    def fetch_document(self, stream_name: str, item: JSONType) -> FetcherResult:
        assert stream_name == "product_updates_off"
        id_ = item["code"]
        if id_ in self.missing_documents:
            return FetcherResult(status=FetcherStatus.REMOVED, document=None)
        return FetcherResult(
            status=FetcherStatus.FOUND,
            document={"code": id_, "name": f"Document {id_}"},
        )


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
    assert len(results) == 4
    assert results[0] == (
        1629878400000,
        FetcherResult(
            status=FetcherStatus.FOUND, document={"code": "1", "name": "Document 1"}
        ),
    )
    assert results[1] == (
        1629878400001,
        FetcherResult(
            status=FetcherStatus.FOUND, document={"code": "2", "name": "Document 2"}
        ),
    )
    assert results[2] == (
        1629878400002,
        FetcherResult(
            status=FetcherStatus.FOUND, document={"code": "3", "name": "Document 3"}
        ),
    )
    assert results[3] == (
        1629878400004,
        FetcherResult(status=FetcherStatus.REMOVED, document=None),
    )
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
        self.streams_history: list[dict] = []

    def xread(self, streams: dict, block: int, count: int | None = None):
        assert set(streams.keys()) == {"product_updates_off"}
        assert block > 0
        assert count == 100
        self.streams_history.append(dict(streams))
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

    result = next(updates_iter)
    assert result == (
        redis_stream_name,
        1629878400002,
        "1629878400002-0",
        FetcherResult(status=FetcherStatus.REMOVED, document=None),
    )

    result = next(updates_iter)
    assert result == (
        redis_stream_name,
        1629878400000,
        "1629878400000-0",
        FetcherResult(
            status=FetcherStatus.FOUND, document={"code": "1", "name": "Document 1"}
        ),
    )

    result = next(updates_iter)
    assert result == (
        redis_stream_name,
        1629878400001,
        "1629878400001-0",
        FetcherResult(
            status=FetcherStatus.FOUND, document={"code": "2", "name": "Document 2"}
        ),
    )

    result = next(updates_iter)
    assert result == (
        redis_stream_name,
        1629878400003,
        "1629878400003-0",
        FetcherResult(
            status=FetcherStatus.FOUND, document={"code": "3", "name": "Document 3"}
        ),
    )
    # we started from "$" (no position given) as there is no checkpoint
    assert redis_client.streams_history[0] == {redis_stream_name: "$"}  # type: ignore


def test_get_new_updates_starts_from_given_position(default_config: IndexConfig):
    """The generator must start from the given position, not from `$`"""
    redis_stream_name = cast(str, default_config.redis_stream_name)
    return_values = [
        [(redis_stream_name, [("1629878400005-0", {"code": "5"})])],
    ]
    redis_client = cast(Redis, RedisXreadClient(return_values))
    document_fetcher = DocumentFetcher(default_config)

    updates_iter = get_new_updates(
        redis_client,
        [redis_stream_name],
        {redis_stream_name: default_config.index.id_field_name},
        {redis_stream_name: document_fetcher},
        min_ids={redis_stream_name: "1629878400004-0"},
    )
    result = next(updates_iter)
    assert result[2] == "1629878400005-0"
    assert redis_client.streams_history[0] == {  # type: ignore
        redis_stream_name: "1629878400004-0"
    }


def test_get_new_updates_stops_when_stop_event_is_set(default_config: IndexConfig):
    """The generator must end when the stop event is set"""
    redis_stream_name = cast(str, default_config.redis_stream_name)
    redis_client = cast(Redis, RedisXreadClient([]))
    document_fetcher = DocumentFetcher(default_config)
    stop_event = threading.Event()

    updates_iter = get_new_updates(
        redis_client,
        [redis_stream_name],
        {redis_stream_name: default_config.index.id_field_name},
        {redis_stream_name: document_fetcher},
        stop_event=stop_event,
    )
    stop_event.set()
    assert list(updates_iter) == []
    # xread was never called: the stop was noticed before reading
    assert redis_client.streams_history == []  # type: ignore


def test_load_document_fetcher(default_config):
    fetcher = load_document_fetcher(default_config)
    assert isinstance(fetcher, BaseDocumentFetcher)


def test_get_document_dict(default_config):
    class MockDocumentProcessor:
        def from_result(self, row):
            doc = row.document
            if doc["_id"] == "id1":
                return FetcherResult(
                    status=FetcherStatus.FOUND,
                    document={
                        "field1_processed": doc["field1"],
                        "field2_processed": doc["field2"],
                        "_id": doc["_id"],
                    },
                )
            elif doc["_id"] == "id2":
                return FetcherResult(
                    status=FetcherStatus.REMOVED, document={"_id": doc["_id"]}
                )
            elif doc["_id"] == "id3":
                return FetcherResult(
                    status=FetcherStatus.SKIP, document={"_id": doc["_id"]}
                )
            else:
                return FetcherResult(status=FetcherStatus.FOUND, document=None)

    processor = MockDocumentProcessor()
    next_index = "index1"
    row_1 = FetcherResult(
        status=FetcherStatus.FOUND,
        document={"field1": "value1", "field2": "value2", "_id": "id1"},
    )
    # will be removed
    row_2 = FetcherResult(
        status=FetcherStatus.FOUND,
        document={"field1": "value1", "field2": "value2", "_id": "id2"},
    )
    # will be skipped
    row_3 = FetcherResult(
        status=FetcherStatus.FOUND,
        document={"field1": "value1", "field2": "value2", "_id": "id3"},
    )
    # will be skipped too
    row_4 = FetcherResult(
        status=FetcherStatus.FOUND,
        document={"field1": "value1", "field2": "value2", "_id": "id4"},
    )

    action = get_document_dict(processor, row_1, next_index)
    assert action == {
        "_source": {"field1_processed": "value1", "field2_processed": "value2"},
        "_index": "index1",
        "_id": "id1",
    }
    action = get_document_dict(processor, row_2, next_index)
    assert action == {
        "_op_type": "delete",
        "_index": "index1",
        "_id": "id2",
    }

    action = get_document_dict(processor, row_3, next_index)
    assert action is None

    action = get_document_dict(processor, row_4, next_index)
    assert action is None


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
        assert document["_source"] == {
            "obsolete": False,
            "categories": ["en:beverages"],
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


def make_daemon_mocks(off_config: IndexConfig, updates: list):
    """Return (connection_mock, es_client_mock, redis_client_mock) for the daemon.

    The checkpoint is pre-populated so that the daemon does not try to derive
    its start position from the index (that's tested separately).
    """
    es_client_mock = MagicMock()
    redis_client_mock = MagicMock()
    # a checkpoint exists: the daemon resumes from it
    redis_client_mock.get.return_value = "1629878399999-0"
    redis_client_mock.ping.return_value = True
    connection_mock = MagicMock()
    connection_mock.get_es_client.return_value = es_client_mock
    connection_mock.get_redis_client.return_value = redis_client_mock
    return connection_mock, es_client_mock, redis_client_mock


class StopWhenExhausted:
    """Wrap updates so that the daemon stops once they are all processed.

    The real generator blocks until new events arrive; a finite test list does
    not, so the daemon would loop forever. Setting the stop event mimics the
    daemon being stopped after the last event.
    """

    def __init__(self, updates: list):
        self.updates = updates
        self.stop_event: threading.Event | None = None

    def __iter__(self):
        yield from self.updates
        assert self.stop_event is not None
        self.stop_event.set()


STOP_EVENTS: list[threading.Event] = []


def _install_stop_after_first_read(stop_event):
    """Fake _install_signal_handlers that stops the daemon after one read

    The real generator blocks until new events arrive, while the mocked one
    returns immediately: without this the daemon would spin forever.
    """
    STOP_EVENTS.append(stop_event)


def empty_updates_then_stop(*args, **kwargs):
    """Empty generator mock that stops the daemon once it was read"""
    assert STOP_EVENTS
    STOP_EVENTS[-1].set()
    return iter([])


def run_daemon_for_test(
    global_config: Config,
    off_config: IndexConfig,
    updates: list,
    connection_mock: MagicMock | None = None,
):
    """Run the daemon on a fixed list of updates, patching the exit paths."""
    if connection_mock is None:
        connection_mock, _, _ = make_daemon_mocks(off_config, updates)
    updates_wrapper = StopWhenExhausted(updates)
    stop_events: list[threading.Event] = []

    def _install(stop_event):
        stop_events.append(stop_event)
        updates_wrapper.stop_event = stop_event

    with (
        patch("app._import.connection", connection_mock),
        patch(
            "app._import.load_document_fetcher",
            MagicMock(return_value=DocumentFetcher(off_config)),
        ),
        patch(
            "app._import.get_new_updates",
            MagicMock(side_effect=lambda *args, **kwargs: iter(updates_wrapper)),
        ),
        # the signal handlers can't be installed outside the main thread
        patch("app._import._install_signal_handlers", _install),
    ):
        run_update_daemon(global_config)
    return connection_mock


def test_run_update_daemon_ignores_removal_of_absent_document(
    default_global_config: Config,
):
    off_config: IndexConfig = default_global_config.indices["off"]
    es_client_mock = MagicMock()
    es_client_mock.delete.side_effect = NotFoundError(
        "not found", api_meta_response(404), {}
    )
    connection_mock, _, redis_client_mock = make_daemon_mocks(off_config, [])
    connection_mock.get_es_client.return_value = es_client_mock
    updates = [
        (
            "product_updates_off",
            1629878400000,
            "1629878400000-0",
            FetcherResult(status=FetcherStatus.REMOVED, document={"code": "4"}),
        ),
        (
            "product_updates_off",
            1629878400001,
            "1629878400001-0",
            FetcherResult(
                status=FetcherStatus.FOUND, document={"code": "5", "name": "Doc 5"}
            ),
        ),
    ]
    run_daemon_for_test(
        default_global_config, off_config, updates, connection_mock=connection_mock
    )

    es_client_mock.delete.assert_called_once()
    # the daemon went on with the next update
    es_client_mock.index.assert_called_once()
    # the checkpoint was moved after each event
    set_calls = [c.args for c in redis_client_mock.set.mock_calls]
    assert set_calls == [
        (
            "searchalicious:checkpoint:product_updates_off:openfoodfacts",
            "1629878400000-0",
        ),
        (
            "searchalicious:checkpoint:product_updates_off:openfoodfacts",
            "1629878400001-0",
        ),
    ]


def test_get_redis_updates_ignores_removal_of_absent_document(
    default_global_config: Config,
):
    off_config: IndexConfig = default_global_config.indices["off"]
    results = [
        # the document was created then deleted after the dump
        (False, {"delete": {"_id": "4", "status": 404}}),
        (False, {"index": {"_id": "5", "status": 400}}),
    ]
    with (
        patch("app._import.Index"),
        patch("app._import.load_document_fetcher"),
        patch("app._import.get_redis_products", MagicMock(return_value=iter([]))),
        patch(
            "app._import.get_last_indexed_timestamp_ms",
            MagicMock(return_value=1629878400000),
        ),
        patch("app._import.parallel_bulk", MagicMock(return_value=results)) as bulk,
    ):
        num_errors = get_redis_updates(MagicMock(), "off-index", off_config)

    # parallel_bulk must not raise on a 404 delete
    assert bulk.call_args.kwargs["ignore_status"] == 404
    # only the real failure is counted
    assert num_errors == 1


def test_run_update_daemon(default_global_config: Config):
    off_config: IndexConfig = default_global_config.indices["off"]
    document_fetcher_mock = DocumentFetcher(off_config)

    updates = [
        (
            "product_updates_off",
            1629878400000,
            "1629878400000-0",
            FetcherResult(
                status=FetcherStatus.FOUND, document={"code": "1", "name": "Document 1"}
            ),
        ),
        (
            "product_updates_off",
            1629878400001,
            "1629878400001-0",
            FetcherResult(
                status=FetcherStatus.FOUND, document={"code": "2", "name": "Document 2"}
            ),
        ),
        (
            "product_updates_off",
            1629878400002,
            "1629878400002-0",
            FetcherResult(
                status=FetcherStatus.FOUND, document={"code": "3", "name": "Document 3"}
            ),
        ),
        (
            "product_updates_off",
            1629878400003,
            "1629878400003-0",
            FetcherResult(
                status=FetcherStatus.REMOVED,
                document={"code": "4", "name": "Document 4"},
            ),
        ),
        (
            "product_updates_off",
            1629878400004,
            "1629878400004-0",
            FetcherResult(status=FetcherStatus.FOUND, document=None),
        ),
        # to skip
        (
            "product_updates_off",
            1629878400005,
            "1629878400005-0",
            FetcherResult(
                status=FetcherStatus.SKIP, document={"code": "6", "name": "Document 6"}
            ),
        ),
        # this corresponds to id in document_denylist
        (
            "product_updates_off",
            1629878400006,
            "1629878400006-0",
            FetcherResult(
                status=FetcherStatus.FOUND,
                document={"code": "8901552007122", "name": "Denyed Document"},
            ),
        ),
    ]

    connection_mock, _, redis_client_mock = make_daemon_mocks(off_config, updates)
    es_client_mock = connection_mock.get_es_client.return_value
    load_document_fetcher_mock = MagicMock(return_value=document_fetcher_mock)

    updates_wrapper = StopWhenExhausted(updates)
    stop_events: list[threading.Event] = []

    def _install(stop_event):
        stop_events.append(stop_event)
        updates_wrapper.stop_event = stop_event

    with (
        patch("app._import.connection", connection_mock),
        patch("app._import.load_document_fetcher", load_document_fetcher_mock),
        patch(
            "app._import.get_new_updates",
            MagicMock(side_effect=lambda *args, **kwargs: iter(updates_wrapper)),
        ),
        patch("app._import._install_signal_handlers", _install),
    ):
        run_update_daemon(default_global_config)

    # Assertions
    connection_mock.get_es_client.assert_called()
    connection_mock.get_redis_client.assert_called()
    load_document_fetcher_mock.assert_called_once_with(off_config)
    # only three first elements are indexed
    assert len(es_client_mock.index.mock_calls) == 3
    for i, mock_call in enumerate(es_client_mock.index.mock_calls):
        assert mock_call.args == ()
        kwargs = mock_call.kwargs
        assert set(kwargs.keys()) == {"index", "body", "id"}
        assert kwargs["id"] == str(i + 1)
        assert kwargs["body"]["code"] == str(i + 1)
        assert isinstance(kwargs["body"]["last_indexed_datetime"], str)
    # one element removed
    assert len(es_client_mock.delete.mock_calls) == 1
    mock_call = es_client_mock.delete.mock_calls[0]
    assert mock_call.args == ()
    kwargs = mock_call.kwargs
    assert set(kwargs.keys()) == {"index", "id"}
    assert kwargs["id"] == "4"
    # the checkpoint is moved after every handled event, including the
    # skipped ones and the denylisted document
    set_calls = [c.args for c in redis_client_mock.set.mock_calls]
    assert [c[1] for c in set_calls] == [u[2] for u in updates]
    assert all(
        c[0] == "searchalicious:checkpoint:product_updates_off:openfoodfacts"
        for c in set_calls
    )


def test_run_update_daemon_retries_transient_errors(default_global_config: Config):
    """An Elasticsearch outage must not make the daemon skip an event"""
    off_config: IndexConfig = default_global_config.indices["off"]
    connection_mock, _, _ = make_daemon_mocks(off_config, [])
    es_client_mock = connection_mock.get_es_client.return_value
    # first attempt fails with a transient error, second one succeeds
    es_client_mock.index.side_effect = [
        elasticsearch.TransportError("unavailable"),
        None,
    ]
    updates = [
        (
            "product_updates_off",
            1629878400000,
            "1629878400000-0",
            FetcherResult(
                status=FetcherStatus.FOUND, document={"code": "1", "name": "Document 1"}
            ),
        ),
    ]

    with patch("app._import.retry_delay", MagicMock(return_value=0)):
        run_daemon_for_test(
            default_global_config, off_config, updates, connection_mock=connection_mock
        )

    assert es_client_mock.index.call_count == 2


def test_run_update_daemon_skips_non_retryable_errors(default_global_config: Config):
    """A document rejected by Elasticsearch must be skipped, not block the stream"""
    off_config: IndexConfig = default_global_config.indices["off"]
    connection_mock, _, redis_client_mock = make_daemon_mocks(off_config, [])
    es_client_mock = connection_mock.get_es_client.return_value
    es_client_mock.index.side_effect = [
        elasticsearch.BadRequestError("bad request", api_meta_response(400), {}),
        None,
    ]
    updates = [
        (
            "product_updates_off",
            1629878400000,
            "1629878400000-0",
            FetcherResult(
                status=FetcherStatus.FOUND,
                document={"code": "invalid", "name": "Invalid"},
            ),
        ),
        (
            "product_updates_off",
            1629878400001,
            "1629878400001-0",
            FetcherResult(
                status=FetcherStatus.FOUND, document={"code": "2", "name": "Document 2"}
            ),
        ),
    ]

    run_daemon_for_test(
        default_global_config, off_config, updates, connection_mock=connection_mock
    )

    # the first document failed once and was skipped, the second one indexed
    assert es_client_mock.index.call_count == 2
    set_calls = [c.args for c in redis_client_mock.set.mock_calls]
    assert [c[1] for c in set_calls] == ["1629878400000-0", "1629878400001-0"]


def test_run_update_daemon_cold_start_from_last_indexed_document(
    default_global_config: Config,
):
    """Without a checkpoint, start from the newest indexed document"""
    off_config: IndexConfig = default_global_config.indices["off"]
    connection_mock, _, redis_client_mock = make_daemon_mocks(off_config, [])
    # no checkpoint yet
    redis_client_mock.get.return_value = None
    STOP_EVENTS.clear()
    get_new_updates_mock = MagicMock(side_effect=empty_updates_then_stop)

    with (
        patch("app._import.connection", connection_mock),
        patch("app._import.load_document_fetcher", MagicMock()),
        patch("app._import.get_new_updates", get_new_updates_mock),
        patch(
            "app._import.get_last_indexed_timestamp_ms",
            MagicMock(return_value=1629878400999),
        ),
        # stop the daemon after the (empty) stream was read once
        patch("app._import._install_signal_handlers", _install_stop_after_first_read),
    ):
        run_update_daemon(default_global_config)

    # the derived position is passed to the reader and persisted
    assert get_new_updates_mock.call_args.kwargs["min_ids"] == {
        "product_updates_off": "1629878400999-0"
    }
    redis_client_mock.set.assert_called_once_with(
        "searchalicious:checkpoint:product_updates_off:openfoodfacts", "1629878400999-0"
    )


def test_run_update_daemon_cold_start_with_empty_index(
    default_global_config: Config,
):
    """Without a checkpoint nor data, start from the end of the stream"""
    off_config: IndexConfig = default_global_config.indices["off"]
    connection_mock, _, redis_client_mock = make_daemon_mocks(off_config, [])
    redis_client_mock.get.return_value = None
    STOP_EVENTS.clear()
    get_new_updates_mock = MagicMock(side_effect=empty_updates_then_stop)

    with (
        patch("app._import.connection", connection_mock),
        patch("app._import.load_document_fetcher", MagicMock()),
        patch("app._import.get_new_updates", get_new_updates_mock),
        patch(
            "app._import.get_last_indexed_timestamp_ms", MagicMock(return_value=None)
        ),
        patch("app._import._install_signal_handlers", _install_stop_after_first_read),
    ):
        run_update_daemon(default_global_config)

    assert get_new_updates_mock.call_args.kwargs["min_ids"] == {
        "product_updates_off": "$"
    }
    # nothing is persisted for a "$" position: it would freeze the checkpoint
    redis_client_mock.set.assert_not_called()


def _patch_last_modified_search(hits: list[dict]):
    """Make the search of the most recently modified document return `hits`"""
    results = [MagicMock(to_dict=MagicMock(return_value=hit)) for hit in hits]
    search = MagicMock()
    search.return_value.sort.return_value.extra.return_value.execute.return_value = (
        results
    )
    return search


def test_get_redis_updates_catches_up_from_last_modified(default_config: IndexConfig):
    last_modified = default_config.index.last_modified_field_name
    products = MagicMock(return_value=iter([]))
    with (
        patch("app._import.Index"),
        patch(
            "app.checkpoints.Search",
            _patch_last_modified_search([{last_modified: 12.5}]),
        ),
        patch("app._import.get_redis_products", products),
        patch("app._import.parallel_bulk", return_value=[]) as bulk,
    ):
        assert get_redis_updates(MagicMock(), "idx", default_config) == 0
    bulk.assert_called_once()
    # timestamp in milliseconds
    assert products.call_args.args[5] == 12500


def test_get_redis_updates_fails_on_empty_index(default_config: IndexConfig):
    """An empty index has no date to catch up from: skipping would lose updates"""
    with (
        patch("app._import.Index"),
        patch("app.checkpoints.Search", _patch_last_modified_search([])),
        patch("app._import.get_redis_products") as products,
        patch("app._import.parallel_bulk") as bulk,
        pytest.raises(RuntimeError, match="--skip-updates"),
    ):
        get_redis_updates(MagicMock(), "idx", default_config)
    products.assert_not_called()
    bulk.assert_not_called()


def test_get_redis_updates_fails_without_last_modified(default_config: IndexConfig):
    with (
        patch("app._import.Index"),
        patch("app.checkpoints.Search", _patch_last_modified_search([{"code": "1"}])),
        patch("app._import.get_redis_products") as products,
        patch("app._import.parallel_bulk") as bulk,
        pytest.raises(RuntimeError, match="--skip-updates"),
    ):
        get_redis_updates(MagicMock(), "idx", default_config)
    products.assert_not_called()
    bulk.assert_not_called()


def test_gen_taxonomy_documents_synonyms_without_name(default_config: IndexConfig):
    """A language may have synonyms but no name for an entry"""
    taxonomy = Taxonomy("categories")
    taxonomy.nodes["en:milk"] = TaxonomyNode(
        id="en:milk",
        names={"en": "Milk"},
        # no name in French, but synonyms
        synonyms={"en": ["Cow milk"], "fr": ["lait de vache", "lait"]},
    )
    default_config.taxonomy.preprocessor = None
    with patch("app._import.iter_taxonomies", return_value=[taxonomy]):
        documents = list(
            gen_taxonomy_documents(default_config, "next-index", {"en", "fr"})
        )

    assert len(documents) == 1
    source = documents[0]["_source"]
    assert source["name"] == {"en": "Milk"}
    # without a name, synonyms are only sorted by length
    assert source["synonyms"]["fr"]["input"] == ["lait", "lait de vache"]
    # the name comes first when there is one
    assert source["synonyms"]["en"]["input"][0] == "Milk"


@contextmanager
def _mock_full_import():
    """Mock everything of a full import but the catch-up and the alias update"""
    pool = MagicMock()
    pool.return_value.__enter__.return_value = pool.return_value
    with (
        patch("app._import.connection"),
        patch("app._import.generate_index_object"),
        patch("app._import.wait_index_health"),
        patch("app._import.Pool", pool),
        patch("app._import.import_parallel", return_value=(0, 0, [])),
        patch("app._import.update_alias") as update_alias_mock,
    ):
        yield update_alias_mock


def test_run_items_import_does_not_publish_empty_index_without_catch_up(
    default_config: IndexConfig,
):
    """An empty import must not replace the live index while skipping updates"""
    with (
        _mock_full_import() as update_alias_mock,
        patch("app._import.Index"),
        patch("app.checkpoints.Search", _patch_last_modified_search([])),
        pytest.raises(RuntimeError),
    ):
        run_items_import(Path("items.jsonl"), 1, default_config)
    update_alias_mock.assert_not_called()


def test_run_items_import_skip_updates_still_publishes(default_config: IndexConfig):
    with _mock_full_import() as update_alias_mock:
        run_items_import(Path("items.jsonl"), 1, default_config, skip_updates=True)
    update_alias_mock.assert_called_once()


def test_is_retryable_error():
    """Transient errors are retried, document-level errors are not"""
    # Elasticsearch transient errors
    assert is_retryable_error(elasticsearch.ConnectionError("boom"))
    assert is_retryable_error(elasticsearch.ConnectionTimeout("timeout"))
    assert is_retryable_error(elasticsearch.TransportError("unavailable"))
    assert is_retryable_error(
        elasticsearch.ApiError("too many requests", api_meta_response(429), "body")
    )
    # NotFoundError and ConflictError are subclasses of ApiError but must not
    # be retried
    assert not is_retryable_error(
        NotFoundError("not found", api_meta_response(404), {})
    )
    assert not is_retryable_error(
        elasticsearch.ConflictError("conflict", api_meta_response(409), {})
    )
    assert not is_retryable_error(
        elasticsearch.BadRequestError("bad", api_meta_response(400), {})
    )
    # Redis transient errors
    assert is_retryable_error(redis_exceptions.ConnectionError("boom"))
    assert is_retryable_error(redis_exceptions.TimeoutError("slow"))
    assert is_retryable_error(redis_exceptions.BusyLoadingError("loading"))
    # other errors
    assert not is_retryable_error(ValueError("bug"))
    assert not is_retryable_error(redis_exceptions.ResponseError("wrong type"))


def test_retry_delay():
    """The delay doubles and is capped, with a bounded jitter"""
    with patch("app._import.random.uniform", MagicMock(return_value=0)):
        assert retry_delay(0) == 1.0
        assert retry_delay(1) == 2.0
        assert retry_delay(2) == 4.0
        # capped
        assert retry_delay(20) == 60.0
    # jitter is applied in both directions and never negative
    with patch("app._import.random.uniform", MagicMock(return_value=0.2)):
        assert retry_delay(0) == 1.2
    with patch("app._import.random.uniform", MagicMock(return_value=-0.2)):
        assert retry_delay(0) == 0.8
    with patch("app._import.random.uniform", MagicMock(return_value=-1)):
        assert retry_delay(0) >= 0


def test_reset_checkpoint_after_import(default_config: IndexConfig):
    """The import moves the daemon checkpoint to the most recent document"""
    redis_client_mock = MagicMock()
    es_client_mock = MagicMock()
    with (
        patch(
            "app._import.connection.get_redis_client",
            MagicMock(return_value=redis_client_mock),
        ),
        patch(
            "app._import.get_last_indexed_timestamp_ms",
            MagicMock(return_value=1629878400123),
        ),
    ):
        reset_checkpoint_after_import(es_client_mock, default_config)

    redis_client_mock.set.assert_called_once_with(
        "searchalicious:checkpoint:product_updates_off:openfoodfacts", "1629878400123-0"
    )


def test_reset_checkpoint_after_import_with_empty_index(default_config: IndexConfig):
    """An empty index leaves the checkpoint untouched"""
    redis_client_mock = MagicMock()
    with (
        patch(
            "app._import.connection.get_redis_client",
            MagicMock(return_value=redis_client_mock),
        ),
        patch(
            "app._import.get_last_indexed_timestamp_ms", MagicMock(return_value=None)
        ),
    ):
        reset_checkpoint_after_import(MagicMock(), default_config)

    redis_client_mock.set.assert_not_called()


def test_reset_checkpoint_after_import_redis_failure(default_config: IndexConfig):
    """A Redis failure does not fail the import"""
    redis_client_mock = MagicMock()
    redis_client_mock.set.side_effect = redis_exceptions.ConnectionError("boom")
    with (
        patch(
            "app._import.connection.get_redis_client",
            MagicMock(return_value=redis_client_mock),
        ),
        patch(
            "app._import.get_last_indexed_timestamp_ms",
            MagicMock(return_value=1629878400123),
        ),
    ):
        # must not raise
        reset_checkpoint_after_import(MagicMock(), default_config)


def test_run_update_daemon_restarts_reader_after_redis_error(
    default_global_config: Config,
):
    """A Redis error while reading must restart the reader from the checkpoint"""
    off_config: IndexConfig = default_global_config.indices["off"]
    connection_mock, _, redis_client_mock = make_daemon_mocks(off_config, [])
    calls: list[int] = []

    def failing_then_empty(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise redis_exceptions.ConnectionError("redis is gone")
        # stop the daemon after the rebuild
        STOP_EVENTS[-1].set()
        return iter([])

    STOP_EVENTS.clear()
    get_new_updates_mock = MagicMock(side_effect=failing_then_empty)
    with (
        patch("app._import.connection", connection_mock),
        patch("app._import.load_document_fetcher", MagicMock()),
        patch("app._import.get_new_updates", get_new_updates_mock),
        patch("app._import._install_signal_handlers", _install_stop_after_first_read),
        patch("app._import.retry_delay", MagicMock(return_value=0)),
    ):
        run_update_daemon(default_global_config)

    # the reader was rebuilt once, from the persisted checkpoint
    assert len(calls) == 2
    assert get_new_updates_mock.call_args.kwargs["min_ids"] == {
        "product_updates_off": "1629878399999-0"
    }
    # the Elasticsearch client was reopened after the failure
    assert connection_mock.get_es_client.call_count >= 2


def test_run_update_daemon_raises_non_retryable_reader_error(
    default_global_config: Config,
):
    """A non-retryable error while reading must stop the daemon"""
    off_config: IndexConfig = default_global_config.indices["off"]
    connection_mock, _, _ = make_daemon_mocks(off_config, [])

    def raising(*args, **kwargs):
        raise ValueError("a bug")

    with (
        patch("app._import.connection", connection_mock),
        patch("app._import.load_document_fetcher", MagicMock()),
        patch("app._import.get_new_updates", MagicMock(side_effect=raising)),
        patch("app._import._install_signal_handlers", _install_stop_after_first_read),
    ):
        with pytest.raises(ValueError, match="a bug"):
            run_update_daemon(default_global_config)
