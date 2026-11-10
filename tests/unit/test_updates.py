"""Tests of the update daemon (app.updates)."""

import threading
from typing import cast
from unittest.mock import MagicMock, patch

import elasticsearch
import pytest
import redis.exceptions as redis_exceptions
from elasticsearch import NotFoundError

from app._import import BaseDocumentFetcher
from app._types import FetcherResult, FetcherStatus
from app.config import Config, IndexConfig
from app.updates import (
    is_retryable_error,
    retry_delay,
    run_update_daemon,
    wait_for_start_position,
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

    # the derived position is passed to the reader and persisted
    assert get_new_updates_mock.call_args.kwargs["min_ids"] == {
        "product_updates_off": "1629878400999-0"
    }
    redis_client_mock.set.assert_called_once_with(
        "searchalicious:checkpoint:product_updates_off:openfoodfacts", "1629878400999-0"
    )


def test_run_update_daemon_waits_for_empty_index_to_be_populated(
    default_global_config: Config,
):
    """Without a checkpoint nor data, wait for the index instead of starting"""
    off_config: IndexConfig = default_global_config.indices["off"]
    connection_mock, _, redis_client_mock = make_daemon_mocks(off_config, [])
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


def test_wait_for_start_position_waits_until_the_index_is_populated():
    """The position is only derived once the index has a document"""
    redis_client_mock = MagicMock()
    redis_client_mock.get.return_value = None
    stop_event = threading.Event()
    # first two checks see an empty index, then the import has run
    timestamp_mock = MagicMock(side_effect=[None, None, 1629878400999])

    with (
        patch("app.updates.get_last_indexed_timestamp_ms", timestamp_mock),
        patch("app.updates.retry_delay", MagicMock(return_value=0)),
    ):
        start_id = wait_for_start_position(
            redis_client_mock,
            MagicMock(),
            "product_updates_off",
            "openfoodfacts",
            "last_modified_t",
            stop_event,
        )

    assert start_id == "1629878400999-0"
    assert timestamp_mock.call_count == 3
    # the checkpoint is persisted once the position is known
    redis_client_mock.set.assert_called_once_with(
        "searchalicious:checkpoint:product_updates_off:openfoodfacts",
        "1629878400999-0",
    )


def test_wait_for_start_position_stops_waiting():
    """A stop request interrupts the wait for the index"""
    redis_client_mock = MagicMock()
    redis_client_mock.get.return_value = None
    stop_event = threading.Event()
    stop_event.set()

    with patch(
        "app.updates.get_last_indexed_timestamp_ms", MagicMock(return_value=None)
    ):
        start_id = wait_for_start_position(
            redis_client_mock,
            MagicMock(),
            "product_updates_off",
            "openfoodfacts",
            "last_modified_t",
            stop_event,
        )

    assert start_id is None
    redis_client_mock.set.assert_not_called()


def test_wait_for_start_position_resumes_from_checkpoint():
    """An existing checkpoint is used without querying the index"""
    redis_client_mock = MagicMock()
    redis_client_mock.get.return_value = "1629878399999-0"
    timestamp_mock = MagicMock()

    with patch("app.updates.get_last_indexed_timestamp_ms", timestamp_mock):
        start_id = wait_for_start_position(
            redis_client_mock,
            MagicMock(),
            "product_updates_off",
            "openfoodfacts",
            "last_modified_t",
            threading.Event(),
        )

    assert start_id == "1629878399999-0"
    timestamp_mock.assert_not_called()


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
