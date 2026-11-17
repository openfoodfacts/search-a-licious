"""Tests of the update daemon (app.updates)."""

import threading
import unittest.mock
from typing import cast
from unittest.mock import MagicMock, patch

import elasticsearch
import pytest
import redis.exceptions as redis_exceptions
from elasticsearch import NotFoundError

from app._import import BaseDocumentFetcher
from app._types import FetcherResult, FetcherStatus
from app.config import Config, IndexConfig
from app.exceptions import TransientFetcherError
from app.updates import (
    ALIAS_CHECK_INTERVAL,
    UpdatesStateRecorder,
    index_result_and_track_event,
    is_retryable_error,
    resolve_start_position,
    retry_delay,
    run_update_daemon,
)


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


class DocumentFetcher(BaseDocumentFetcher):
    """Document fetcher returning a ready-made document, without any network"""

    def __init__(self, config: IndexConfig, *args, **kwargs):
        super().__init__(config)

    def fetch_document(self, stream_name: str, item: dict) -> FetcherResult:
        return cast(FetcherResult, item)


def alias_index_name(off_config: IndexConfig) -> str:
    """The concrete index name the daemon mock sees behind the alias"""
    return f"{off_config.index.name}-2021-01-01"


def configure_alias(es_client_mock: MagicMock, off_config: IndexConfig) -> MagicMock:
    """Make the ES client mock report the alias of the test index"""
    es_client_mock.indices.get_alias.return_value = {
        alias_index_name(off_config): {"aliases": {off_config.index.name: {}}}
    }
    return es_client_mock


def make_daemon_mocks(off_config: IndexConfig, updates: list):
    """Return (connection_mock, es_client_mock, redis_client_mock) for the daemon.

    The checkpoint is pre-populated, and tied to the index the alias points to,
    so that the daemon resumes from it instead of deriving its start position
    from the index (the derivation is tested separately).

    The index behind the alias is fixed, so that the periodic alias check sees
    no change. Use :func:`configure_alias` if you replace the ES client mock.
    """
    es_client_mock = configure_alias(MagicMock(), off_config)
    redis_client_mock = MagicMock()
    # a checkpoint exists, and belongs to the current index: the daemon resumes
    # from it
    redis_client_mock.get.side_effect = lambda key: (
        alias_index_name(off_config)
        if key.startswith("searchalicious:checkpoint_index:")
        else "1629878399999-0"
    )
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

    def __init__(self, updates: list, reader=None):
        self.updates = updates
        self.stop_event: threading.Event | None = None
        self.reader = reader

    def __iter__(self):
        yield from (self.reader() if self.reader is not None else iter(self.updates))
        assert self.stop_event is not None
        self.stop_event.set()


def _patch_last_modified_search(hits: list[dict]):
    """Make the search of the most recently modified document return `hits`"""
    results = [MagicMock(to_dict=MagicMock(return_value=hit)) for hit in hits]
    search = MagicMock()
    search.return_value.sort.return_value.extra.return_value.execute.return_value = (
        results
    )
    return search


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


def with_batch_count(updates: list, pending_ref: list[int] | None = None):
    """Yield updates while a shared counter mimics the events read in advance.

    The real generator reads a whole batch from Redis before yielding its
    entries, so the events of the batch that were not yielded yet are "in
    memory". This fake reader reproduces that: `pending_ref` is incremented
    for each event before the first one is yielded.
    """

    def _reader():
        if pending_ref is not None:
            pending_ref[0] += len(updates)
        for update in updates:
            if pending_ref is not None:
                pending_ref[0] -= 1
            yield update

    return _reader


def run_daemon_for_test(
    global_config: Config,
    off_config: IndexConfig,
    updates: list,
    connection_mock: MagicMock | None = None,
    pending_ref: list[int] | None = None,
):
    """Run the daemon on a fixed list of updates, patching the exit paths."""
    if connection_mock is None:
        connection_mock, _, _ = make_daemon_mocks(off_config, updates)
    updates_wrapper = StopWhenExhausted(
        updates, reader=with_batch_count(updates, pending_ref)
    )
    stop_events: list[threading.Event] = []

    def _install(stop_event):
        stop_events.append(stop_event)
        updates_wrapper.stop_event = stop_event

    with (
        patch("app.updates.connection", connection_mock),
        patch(
            "app.updates.load_document_fetcher",
            MagicMock(return_value=DocumentFetcher(off_config)),
        ),
        patch(
            "app.updates.get_new_updates",
            MagicMock(side_effect=lambda *args, **kwargs: iter(updates_wrapper)),
        ),
        # the signal handlers can't be installed outside the main thread
        patch("app.updates._install_signal_handlers", _install),
    ):
        run_update_daemon(global_config)
    return connection_mock


def test_run_update_daemon_ignores_removal_of_absent_document(
    default_global_config: Config,
):
    off_config: IndexConfig = default_global_config.indices["off"]
    es_client_mock = configure_alias(MagicMock(), off_config)
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
        patch("app.updates.connection", connection_mock),
        patch("app.updates.load_document_fetcher", load_document_fetcher_mock),
        patch(
            "app.updates.get_new_updates",
            MagicMock(side_effect=lambda *args, **kwargs: iter(updates_wrapper)),
        ),
        patch("app.updates._install_signal_handlers", _install),
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


def test_run_update_daemon_handles_skipped_events(default_global_config: Config):
    """A skipped event (None result) is checkpointed without being indexed"""
    off_config: IndexConfig = default_global_config.indices["off"]
    connection_mock, es_client_mock, redis_client_mock = make_daemon_mocks(
        off_config, []
    )
    updates = [
        ("product_updates_off", None, "1629878400000-0", None),
        (
            "product_updates_off",
            1629878400001,
            "1629878400001-0",
            FetcherResult(
                status=FetcherStatus.FOUND, document={"code": "1", "name": "Document 1"}
            ),
        ),
    ]

    run_daemon_for_test(
        default_global_config, off_config, updates, connection_mock=connection_mock
    )

    # the skipped event did not reach Elasticsearch...
    es_client_mock.index.assert_called_once()
    # ...but it was checkpointed, and the daemon went on with the next event
    set_calls = [c.args for c in redis_client_mock.set.mock_calls]
    assert [c[1] for c in set_calls] == [
        "1629878400000-0",
        "1629878400001-0",
    ]


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

    with patch("app.updates.retry_delay", MagicMock(return_value=0)):
        run_daemon_for_test(
            default_global_config, off_config, updates, connection_mock=connection_mock
        )

    assert es_client_mock.index.call_count == 2


def test_run_update_daemon_retries_fetcher_retry_status(
    default_global_config: Config,
):
    """A RETRY result must be retried from the checkpoint, not skipped"""
    off_config: IndexConfig = default_global_config.indices["off"]
    connection_mock, es_client_mock, redis_client_mock = make_daemon_mocks(
        off_config, []
    )
    stream_id = "1629878400000-0"
    calls: list[int] = []
    STOP_EVENTS.clear()

    def get_new_updates_side_effect(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:

            def _retry():
                yield (
                    "product_updates_off",
                    1629878400000,
                    stream_id,
                    FetcherResult(status=FetcherStatus.RETRY, document=None),
                )

            return _retry()

        def _success():
            yield (
                "product_updates_off",
                1629878400000,
                stream_id,
                FetcherResult(
                    status=FetcherStatus.FOUND,
                    document={"code": "1", "name": "Document 1"},
                ),
            )
            STOP_EVENTS[-1].set()

        return _success()

    get_new_updates_mock = MagicMock(side_effect=get_new_updates_side_effect)
    with (
        patch("app.updates.connection", connection_mock),
        patch("app.updates.load_document_fetcher", MagicMock()),
        patch("app.updates.get_new_updates", get_new_updates_mock),
        patch("app.updates._install_signal_handlers", _install_stop_after_first_read),
        patch("app.updates.retry_delay", MagicMock(return_value=0)),
    ):
        run_update_daemon(default_global_config)

    # the reader was rebuilt after the RETRY...
    assert get_new_updates_mock.call_count == 2
    # ...the event was indexed once, and only the successful attempt was
    # checkpointed
    assert es_client_mock.index.call_count == 1
    set_calls = [c.args for c in redis_client_mock.set.mock_calls]
    assert set_calls == [
        ("searchalicious:checkpoint:product_updates_off:openfoodfacts", stream_id)
    ]


@pytest.mark.parametrize(
    "es_exception",
    [
        elasticsearch.ConflictError("conflict", api_meta_response(409), {}),
        elasticsearch.BadRequestError("bad", api_meta_response(400), {}),
        elasticsearch.SerializationError("malformed"),
    ],
)
def test_run_update_daemon_skips_non_retryable_errors(
    es_exception, default_global_config: Config
):
    """A document rejected by Elasticsearch must be skipped, not block the stream"""
    off_config: IndexConfig = default_global_config.indices["off"]
    connection_mock, _, redis_client_mock = make_daemon_mocks(off_config, [])
    es_client_mock = connection_mock.get_es_client.return_value
    es_client_mock.index.side_effect = [
        es_exception,
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
    redis_client_mock.get.side_effect = None
    redis_client_mock.get.return_value = None
    STOP_EVENTS.clear()
    get_new_updates_mock = MagicMock(side_effect=empty_updates_then_stop)

    with (
        patch("app.updates.connection", connection_mock),
        patch("app.updates.load_document_fetcher", MagicMock()),
        patch("app.updates.get_new_updates", get_new_updates_mock),
        patch(
            "app.updates.get_last_indexed_timestamp_ms",
            MagicMock(return_value=1629878400999),
        ),
        # stop the daemon after the (empty) stream was read once
        patch("app.updates._install_signal_handlers", _install_stop_after_first_read),
    ):
        run_update_daemon(default_global_config)

    # the derived position is passed to the reader and persisted, together with
    # the index it was derived from
    assert get_new_updates_mock.call_args.kwargs["min_ids"] == {
        "product_updates_off": "1629878400999-0"
    }
    assert [c.args[1] for c in redis_client_mock.set.mock_calls] == [
        "1629878400999-0",
        f"{off_config.index.name}-2021-01-01",
    ]


def test_run_update_daemon_waits_for_empty_index_to_be_populated(
    default_global_config: Config,
):
    """Without a checkpoint nor data, wait for the index instead of starting"""
    off_config: IndexConfig = default_global_config.indices["off"]
    connection_mock, _, redis_client_mock = make_daemon_mocks(off_config, [])
    redis_client_mock.get.side_effect = None
    redis_client_mock.get.return_value = None
    STOP_EVENTS.clear()
    get_new_updates_mock = MagicMock(side_effect=empty_updates_then_stop)

    # the index stays empty: the daemon must not start the reader
    def _install_and_stop(stop_event):
        # stop the daemon while it waits for the index
        stop_event.set()

    with (
        patch("app.updates.connection", connection_mock),
        patch("app.updates.load_document_fetcher", MagicMock()),
        patch("app.updates.get_new_updates", get_new_updates_mock),
        patch(
            "app.updates.get_last_indexed_timestamp_ms", MagicMock(return_value=None)
        ),
        patch("app.updates._install_signal_handlers", _install_and_stop),
        patch("app.updates.retry_delay", MagicMock(return_value=0)),
    ):
        run_update_daemon(default_global_config)

    # the reader was never started: events published before the import must
    # not be silently skipped
    get_new_updates_mock.assert_not_called()
    redis_client_mock.set.assert_not_called()


def test_resolve_start_position_waits_until_the_index_is_populated():
    """The position is only derived once the index has a document"""
    redis_client_mock = MagicMock()
    redis_client_mock.get.return_value = None
    stop_event = threading.Event()
    # first two checks see an empty index, then the import has run
    timestamp_mock = MagicMock(side_effect=[None, None, 1629878400999])
    es_client_mock = MagicMock()
    es_client_mock.indices.get_alias.return_value = {
        "openfoodfacts-2021-01-01": {"aliases": {"openfoodfacts": {}}}
    }

    with (
        patch("app.updates.get_last_indexed_timestamp_ms", timestamp_mock),
        patch("app.updates.retry_delay", MagicMock(return_value=0)),
    ):
        start_id = resolve_start_position(
            redis_client_mock,
            es_client_mock,
            "product_updates_off",
            "openfoodfacts",
            "last_modified_t",
            stop_event,
        )

    assert start_id == "1629878400999-0"
    assert timestamp_mock.call_count == 3
    # the checkpoint and the index it belongs to are persisted once the
    # position is known
    assert redis_client_mock.set.mock_calls == [
        unittest.mock.call(
            "searchalicious:checkpoint:product_updates_off:openfoodfacts",
            "1629878400999-0",
        ),
        unittest.mock.call(
            "searchalicious:checkpoint_index:product_updates_off:openfoodfacts",
            "openfoodfacts-2021-01-01",
        ),
    ]


def test_resolve_start_position_stops_waiting():
    """A stop request interrupts the wait for the index"""
    redis_client_mock = MagicMock()
    redis_client_mock.get.return_value = None
    stop_event = threading.Event()
    stop_event.set()

    with patch(
        "app.updates.get_last_indexed_timestamp_ms", MagicMock(return_value=None)
    ):
        start_id = resolve_start_position(
            redis_client_mock,
            MagicMock(),
            "product_updates_off",
            "openfoodfacts",
            "last_modified_t",
            stop_event,
        )

    assert start_id is None
    redis_client_mock.set.assert_not_called()


def test_resolve_start_position_resumes_from_checkpoint():
    """A checkpoint belonging to the current index is used as is"""
    redis_client_mock = MagicMock()
    redis_client_mock.get.side_effect = lambda key: (
        "1629878399999-0"
        if key.startswith("searchalicious:checkpoint:")
        else "openfoodfacts-2021-01-01"
    )
    timestamp_mock = MagicMock()
    es_client_mock = MagicMock()
    es_client_mock.indices.get_alias.return_value = {
        "openfoodfacts-2021-01-01": {"aliases": {"openfoodfacts": {}}}
    }

    with patch("app.updates.get_last_indexed_timestamp_ms", timestamp_mock):
        start_id = resolve_start_position(
            redis_client_mock,
            es_client_mock,
            "product_updates_off",
            "openfoodfacts",
            "last_modified_t",
            threading.Event(),
        )

    assert start_id == "1629878399999-0"
    timestamp_mock.assert_not_called()
    redis_client_mock.set.assert_not_called()


def test_resolve_start_position_ignores_checkpoint_of_another_index():
    """A checkpoint derived from the previous index must not be resumed from"""
    redis_client_mock = MagicMock()
    redis_client_mock.get.side_effect = lambda key: (
        "1629878399999-0"
        if key.startswith("searchalicious:checkpoint:")
        else "openfoodfacts-2020-01-01"
    )
    es_client_mock = MagicMock()
    es_client_mock.indices.get_alias.return_value = {
        "openfoodfacts-2021-01-01": {"aliases": {"openfoodfacts": {}}}
    }

    with patch(
        "app.updates.get_last_indexed_timestamp_ms",
        MagicMock(return_value=1629878400999),
    ):
        start_id = resolve_start_position(
            redis_client_mock,
            es_client_mock,
            "product_updates_off",
            "openfoodfacts",
            "last_modified_t",
            threading.Event(),
        )

    # the position is derived from the new index, and both keys are persisted
    assert start_id == "1629878400999-0"
    assert redis_client_mock.set.mock_calls == [
        unittest.mock.call(
            "searchalicious:checkpoint:product_updates_off:openfoodfacts",
            "1629878400999-0",
        ),
        unittest.mock.call(
            "searchalicious:checkpoint_index:product_updates_off:openfoodfacts",
            "openfoodfacts-2021-01-01",
        ),
    ]


def test_resolve_start_position_ignores_checkpoint_without_index():
    """A checkpoint with no known index (daemon predating the key) is ignored"""
    redis_client_mock = MagicMock()
    redis_client_mock.get.side_effect = lambda key: (
        "1629878399999-0" if key.startswith("searchalicious:checkpoint:") else None
    )
    es_client_mock = MagicMock()
    es_client_mock.indices.get_alias.return_value = {
        "openfoodfacts-2021-01-01": {"aliases": {"openfoodfacts": {}}}
    }

    with patch(
        "app.updates.get_last_indexed_timestamp_ms",
        MagicMock(return_value=1629878400999),
    ):
        start_id = resolve_start_position(
            redis_client_mock,
            es_client_mock,
            "product_updates_off",
            "openfoodfacts",
            "last_modified_t",
            threading.Event(),
        )

    assert start_id == "1629878400999-0"
    assert len(redis_client_mock.set.mock_calls) == 2


def test_resolve_start_position_does_not_block_when_reading():
    """While reading, an empty index gives no verdict instead of blocking"""
    redis_client_mock = MagicMock()
    redis_client_mock.get.return_value = None
    es_client_mock = MagicMock()
    es_client_mock.indices.get_alias.return_value = {}

    with (
        patch(
            "app.updates.get_last_indexed_timestamp_ms", MagicMock(return_value=None)
        ),
        patch("app.updates.retry_delay", MagicMock(return_value=0)),
    ):
        start_id = resolve_start_position(
            redis_client_mock,
            es_client_mock,
            "product_updates_off",
            "openfoodfacts",
            "last_modified_t",
            threading.Event(),
            wait_for_index=False,
        )

    assert start_id is None
    redis_client_mock.set.assert_not_called()


def test_resolve_start_position_does_not_block_on_es_error_when_reading():
    """While reading, an Elasticsearch error gives no verdict instead of raising"""
    redis_client_mock = MagicMock()
    redis_client_mock.get.return_value = None
    es_client_mock = MagicMock()
    es_client_mock.indices.get_alias.return_value = {
        "openfoodfacts-2021-01-01": {"aliases": {"openfoodfacts": {}}}
    }
    error = elasticsearch.TransportError("connection reset")

    with patch(
        "app.updates.get_last_indexed_timestamp_ms", MagicMock(side_effect=error)
    ):
        start_id = resolve_start_position(
            redis_client_mock,
            es_client_mock,
            "product_updates_off",
            "openfoodfacts",
            "last_modified_t",
            threading.Event(),
            wait_for_index=False,
        )

    assert start_id is None
    redis_client_mock.set.assert_not_called()


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
        patch("app.updates.connection", connection_mock),
        patch("app.updates.load_document_fetcher", MagicMock()),
        patch("app.updates.get_new_updates", get_new_updates_mock),
        patch("app.updates._install_signal_handlers", _install_stop_after_first_read),
        patch("app.updates.retry_delay", MagicMock(return_value=0)),
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
        patch("app.updates.connection", connection_mock),
        patch("app.updates.load_document_fetcher", MagicMock()),
        patch("app.updates.get_new_updates", MagicMock(side_effect=raising)),
        patch("app.updates._install_signal_handlers", _install_stop_after_first_read),
    ):
        with pytest.raises(ValueError, match="a bug"):
            run_update_daemon(default_global_config)


def test_track_event_returns_plain_stream_id():
    """The cursor is the event ID itself: XREAD is already exclusive"""
    stream_id = "1629878400001-0"
    processor = MagicMock()
    processor.from_result.return_value = FetcherResult(
        status=FetcherStatus.FOUND, document={"_id": "1", "code": "1"}
    )
    redis_client = MagicMock()
    es_client = MagicMock()

    cursor = index_result_and_track_event(
        redis_client,
        es_client,
        "product_updates_off",
        stream_id,
        FetcherResult(status=FetcherStatus.FOUND, document={"code": "1"}),
        processor,
        "openfoodfacts",
        threading.Event(),
    )

    assert cursor == stream_id
    es_client.index.assert_called_once_with(
        index="openfoodfacts", body={"code": "1"}, id="1"
    )
    redis_client.set.assert_called_once_with(
        "searchalicious:checkpoint:product_updates_off:openfoodfacts", stream_id
    )


def test_is_retryable_error():
    """Transient errors are retried, document-level errors are not"""
    # the fetcher asked for a retry
    assert is_retryable_error(TransientFetcherError("retry"))
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
    with patch("app.updates.random.uniform", MagicMock(return_value=0)):
        assert retry_delay(0) == 1.0
        assert retry_delay(1) == 2.0
        assert retry_delay(2) == 4.0
        # capped
        assert retry_delay(20) == 60.0
    # jitter is applied in both directions and never negative
    with patch("app.updates.random.uniform", MagicMock(return_value=0.2)):
        assert retry_delay(0) == 1.2
    with patch("app.updates.random.uniform", MagicMock(return_value=-0.2)):
        assert retry_delay(0) == 0.8
    with patch("app.updates.random.uniform", MagicMock(return_value=-1)):
        assert retry_delay(0) >= 0


class FakeClock:
    """A manually advanced clock"""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_recorder(interval: float = 10.0):
    redis_client = MagicMock()
    clock = FakeClock()
    recorder = UpdatesStateRecorder(
        redis_client, "stream", "off", interval=interval, clock=clock
    )
    return recorder, redis_client, clock


def state_writes(redis_client) -> list[dict]:
    """Return the mapping of each hset call on the updates state key"""
    return [c.kwargs["mapping"] for c in redis_client.hset.mock_calls]


def test_recorder_writes_once_per_interval():
    """Writes are throttled: intermediate states are skipped"""
    recorder, redis_client, clock = make_recorder(interval=10.0)

    recorder.set("1000-0", 5)
    assert state_writes(redis_client) == [
        {"last_read_id": "1000-0", "pending_events": 5}
    ]

    clock.advance(1)
    recorder.set("1001-0", 4)
    clock.advance(1)
    recorder.add_pending(-1)
    # still within the interval: nothing written
    assert len(state_writes(redis_client)) == 1

    clock.advance(9)
    recorder.set("1002-0", 2)
    assert state_writes(redis_client)[-1] == {
        "last_read_id": "1002-0",
        "pending_events": 2,
    }
    assert len(state_writes(redis_client)) == 2


def test_recorder_flush_bypasses_throttle():
    """The idle flush writes the latest value whatever the throttle says"""
    recorder, redis_client, clock = make_recorder(interval=10.0)
    recorder.set("1000-0", 3)
    recorder.add_pending(-3)

    recorder.flush()

    assert state_writes(redis_client)[-1] == {
        "last_read_id": "1000-0",
        "pending_events": 0,
    }


def test_recorder_flush_if_due_respects_throttle():
    recorder, redis_client, clock = make_recorder(interval=10.0)
    recorder.set("1000-0", 1)
    recorder.pending_events = 0
    recorder.flush_if_due()
    assert len(state_writes(redis_client)) == 1

    clock.advance(10)
    recorder.flush_if_due()
    assert len(state_writes(redis_client)) == 2


def test_recorder_pending_never_negative():
    recorder, _, _ = make_recorder()
    recorder.add_pending(-1)
    assert recorder.pending_events == 0


def test_recorder_ignores_redis_errors():
    """Recording the state is informational: a failure must not propagate"""
    redis_client = MagicMock()
    redis_client.hset.side_effect = RuntimeError("redis is down")
    recorder = UpdatesStateRecorder(redis_client, "stream", "off", clock=FakeClock())

    recorder.set("1000-0", 1)
    recorder.flush()

    # the failure is not remembered as a successful write
    assert recorder._last_write is None


def test_run_update_daemon_records_processing_state(
    default_global_config: Config,
):
    """The daemon records the last read ID and the pending count"""
    off_config: IndexConfig = default_global_config.indices["off"]
    connection_mock, _, redis_client_mock = make_daemon_mocks(off_config, [])
    updates = [
        (
            "product_updates_off",
            1629878400000,
            "1629878400000-0",
            FetcherResult(status=FetcherStatus.FOUND, document={"code": "1"}),
        ),
        (
            "product_updates_off",
            1629878400001,
            "1629878400001-0",
            FetcherResult(status=FetcherStatus.FOUND, document={"code": "2"}),
        ),
    ]

    run_daemon_for_test(
        default_global_config, off_config, updates, connection_mock=connection_mock
    )

    state_keys = {c.args[0] for c in redis_client_mock.hset.mock_calls if c.args}
    assert state_keys == {
        "searchalicious:updates_state:product_updates_off:openfoodfacts"
    }
    written = state_writes(redis_client_mock)
    # initial state: resuming from the checkpoint, nothing pending, and the
    # index the checkpoint belongs to
    assert written[0]["last_read_id"] == "1629878399999-0"
    assert written[0]["pending_events"] == 0
    assert written[0]["index"] == f"{off_config.index.name}-2021-01-01"
    # the final flush records the last event read as a plain stream ID, which
    # is also the cursor used to read the next event
    assert written[-1]["last_read_id"] == "1629878400001-0"
    assert written[-1]["pending_events"] == 0


def test_get_new_updates_calls_on_batch_end():
    """The reader reports the end of a batch, including on an empty read"""
    from app._import import get_new_updates

    redis_client = MagicMock()
    redis_client.xread.return_value = []
    stop_event = threading.Event()

    def on_batch_end():
        stop_event.set()

    list(
        get_new_updates(
            redis_client,
            ["stream"],
            id_field_names={"stream": "id"},
            document_fetchers={},
            stop_event=stop_event,
            on_batch_end=on_batch_end,
        )
    )

    assert stop_event.is_set()


def make_alias_es_client(index_name: str, alias: str = "openfoodfacts"):
    """ES client whose alias points to `index_name`"""
    es_client = MagicMock()
    es_client.indices.get_alias.return_value = {index_name: {"aliases": {alias: {}}}}
    return es_client


def run_daemon_with_alias_sequence(
    global_config: Config,
    off_config: IndexConfig,
    index_names: list[str | None | Exception],
    start_checkpoint: str = "1629878399999-0",
    start_index: str | None = None,
    derived_ms: int = 1629878405000,
):
    """Run the daemon while the alias points to successive indexes.

    Each entry of `index_names` is what one alias check returns: an index
    name, ``None`` (the alias points nowhere) or an exception instance to
    raise. The startup check consumes the first entry, then one entry is
    consumed per batch end.

    .. note:: the reader stops itself after enough batch ends.

    Unless `start_index` is given, the checkpoint is tied to the index the
    startup check returns, so that the startup does not reset anything.

    Returns the ES client mock, the Redis client mock, the ``min_ids`` each
    generation of the reader was built with, and the number of checks.
    """

    first = index_names[0]
    store = {
        "index": start_index if start_index is not None else first,
        "checkpoint": start_checkpoint,
    }

    def redis_get(key):
        if key.startswith("searchalicious:checkpoint_index:"):
            return store["index"]
        return store["checkpoint"]

    def redis_set(key, value):
        if key.startswith("searchalicious:checkpoint_index:"):
            store["index"] = value
        elif key.startswith("searchalicious:checkpoint:"):
            store["checkpoint"] = value

    redis_client_mock = MagicMock()
    redis_client_mock.get.side_effect = redis_get
    redis_client_mock.set.side_effect = redis_set
    redis_client_mock.ping.return_value = True

    es_client_mock = MagicMock()

    checks: list[int] = []

    def get_alias_side_effect(es, alias):
        assert es is es_client_mock
        value = index_names[min(len(checks), len(index_names) - 1)]
        checks.append(1)
        if isinstance(value, Exception):
            raise value
        return value

    connection_mock = MagicMock()
    connection_mock.get_es_client.return_value = es_client_mock
    connection_mock.get_redis_client.return_value = redis_client_mock

    min_ids_seen: list[dict] = []
    reads: list[int] = []

    def reader(*args, **kwargs):
        min_ids_seen.append(dict(kwargs["min_ids"]))
        reads.append(1)
        on_batch_end = kwargs.get("on_batch_end")
        if on_batch_end is not None:
            # the real generator calls it once the read returns, including
            # when it returned nothing
            on_batch_end()
        # enough reads to consume every entry of the sequence after the
        # startup check: stop instead of looping on an empty stream
        if len(reads) > len(index_names):
            STOP_EVENTS[-1].set()
        return iter([])

    STOP_EVENTS.clear()
    clock = {"now": 0.0}

    def monotonic():
        value = clock["now"]
        # each batch end happens more than ALIAS_CHECK_INTERVAL later
        clock["now"] += ALIAS_CHECK_INTERVAL + 1
        return value

    with (
        patch("app.updates.connection", connection_mock),
        patch("app.updates.load_document_fetcher", MagicMock()),
        patch("app.updates.get_new_updates", MagicMock(side_effect=reader)),
        patch("app.updates.get_alias", MagicMock(side_effect=get_alias_side_effect)),
        patch(
            "app.updates.get_last_indexed_timestamp_ms",
            MagicMock(return_value=derived_ms),
        ),
        patch("app.updates.time.monotonic", monotonic),
        patch("app.updates._install_signal_handlers", _install_stop_after_first_read),
        patch("app.updates.retry_delay", MagicMock(return_value=0)),
    ):
        run_update_daemon(global_config)

    return es_client_mock, redis_client_mock, min_ids_seen, checks


def test_run_update_daemon_resets_position_when_alias_moves(
    default_global_config: Config,
):
    """When the alias points to a new index, the position is derived again"""
    off_config: IndexConfig = default_global_config.indices["off"]
    _es, redis_client, min_ids_seen, _checks = run_daemon_with_alias_sequence(
        default_global_config,
        off_config,
        ["openfoodfacts-2020-01-01", "openfoodfacts-2021-01-01"],
    )

    # the reader was rebuilt from the derived position of the new index
    assert min_ids_seen[0] == {"product_updates_off": "1629878399999-0"}
    assert min_ids_seen[1] == {"product_updates_off": "1629878405000-0"}
    set_calls = [c.args for c in redis_client.set.mock_calls]
    assert set_calls == [
        (
            "searchalicious:checkpoint:product_updates_off:openfoodfacts",
            "1629878405000-0",
        ),
        (
            "searchalicious:checkpoint_index:product_updates_off:openfoodfacts",
            "openfoodfacts-2021-01-01",
        ),
    ]
    # the reported state is the new position, with nothing pending
    last_write = state_writes(redis_client)[-1]
    assert last_write["last_read_id"] == "1629878405000-0"
    assert last_write["pending_events"] == 0
    assert last_write["index"] == "openfoodfacts-2021-01-01"


def test_run_update_daemon_applies_position_behind_current_cursor(
    default_global_config: Config,
):
    """The derived position is applied even when it is older than the cursor"""
    off_config: IndexConfig = default_global_config.indices["off"]
    # the checkpoint is ahead of the derived position of the new index
    _es, _redis, min_ids_seen, _checks = run_daemon_with_alias_sequence(
        default_global_config,
        off_config,
        ["openfoodfacts-2020-01-01", "openfoodfacts-2021-01-01"],
        start_checkpoint="1629878409000-0",
        derived_ms=1629878405000,
    )

    assert min_ids_seen[-1] == {"product_updates_off": "1629878405000-0"}


def test_run_update_daemon_does_not_reset_when_alias_is_unchanged(
    default_global_config: Config,
):
    """An unchanged alias does not touch the checkpoint"""
    off_config: IndexConfig = default_global_config.indices["off"]
    _es, redis_client, min_ids_seen, checks = run_daemon_with_alias_sequence(
        default_global_config,
        off_config,
        ["openfoodfacts-2020-01-01"],
    )

    assert len(checks) >= 1
    assert all(m == {"product_updates_off": "1629878399999-0"} for m in min_ids_seen)
    redis_client.set.assert_not_called()


def test_run_update_daemon_ignores_alias_lookup_errors(
    default_global_config: Config,
):
    """A failing alias lookup is logged, and indexing goes on"""
    off_config: IndexConfig = default_global_config.indices["off"]
    _es, redis_client, min_ids_seen, checks = run_daemon_with_alias_sequence(
        default_global_config,
        off_config,
        [
            "openfoodfacts-2020-01-01",
            elasticsearch.TransportError("connection reset"),
        ],
    )

    # the failed check did not reset anything
    assert not redis_client.set.mock_calls
    # the daemon never restarted the reader
    assert all(m == {"product_updates_off": "1629878399999-0"} for m in min_ids_seen)
    assert len(checks) >= 2


def test_run_update_daemon_ignores_missing_alias(
    default_global_config: Config,
):
    """An alias that starts pointing nowhere is not a change"""
    off_config: IndexConfig = default_global_config.indices["off"]
    _es, redis_client, min_ids_seen, _checks = run_daemon_with_alias_sequence(
        default_global_config,
        off_config,
        ["openfoodfacts-2020-01-01", None],
    )

    # the second check gets no verdict: the position is kept
    assert not redis_client.set.mock_calls
    assert all(m == {"product_updates_off": "1629878399999-0"} for m in min_ids_seen)


def test_run_update_daemon_throttles_alias_checks(default_global_config: Config):
    """The alias is not looked up more than once per interval"""
    es_client_mock = make_alias_es_client("openfoodfacts-2020-01-01")
    redis_client_mock = MagicMock()
    redis_client_mock.get.side_effect = lambda key: (
        "openfoodfacts-2020-01-01"
        if key.startswith("searchalicious:checkpoint_index:")
        else "1629878399999-0"
    )
    redis_client_mock.ping.return_value = True
    connection_mock = MagicMock()
    connection_mock.get_es_client.return_value = es_client_mock
    connection_mock.get_redis_client.return_value = redis_client_mock

    reads: list[int] = []

    def reader(*args, **kwargs):
        reads.append(1)
        on_batch_end = kwargs["on_batch_end"]
        on_batch_end()
        if len(reads) > 5:
            STOP_EVENTS[-1].set()
        return iter([])

    STOP_EVENTS.clear()
    get_alias_mock = MagicMock(return_value="openfoodfacts-2020-01-01")
    with (
        patch("app.updates.connection", connection_mock),
        patch("app.updates.load_document_fetcher", MagicMock()),
        patch("app.updates.get_new_updates", MagicMock(side_effect=reader)),
        patch("app.updates.get_alias", get_alias_mock),
        # the clock does not advance: every check is within the interval
        patch("app.updates.time.monotonic", MagicMock(return_value=0.0)),
        patch("app.updates._install_signal_handlers", _install_stop_after_first_read),
        patch("app.updates.retry_delay", MagicMock(return_value=0)),
    ):
        run_update_daemon(default_global_config)

    assert len(reads) >= 6
    # the startup lookup, plus a single check: the clock never advances, so
    # every batch end after the first falls within the throttle interval
    assert get_alias_mock.call_count == 2
