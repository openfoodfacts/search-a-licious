"""Integration tests of the update daemon against a real Elasticsearch and Redis.

The daemon is run in a thread (so that it can be stopped from the test), on a
stream that is fed by the test.
"""

import threading
import time
from unittest.mock import patch

import pytest

from app import updates as app_updates
from app.checkpoints import (
    checkpoint_key,
    get_checkpoint,
    get_last_indexed_timestamp_ms,
    stream_id_from_timestamp_ms,
    updates_state_key,
)
from app.config import settings as app_settings

STREAM_NAME = "product_updates_off"
INDEX_NAME = "test_off"


def _document(code: str, last_modified_t: int) -> dict:
    """Return a document suitable for the test index and the TestDocumentFetcher"""
    return {
        "code": code,
        "product_name": f"Product {code}",
        "last_modified_t": last_modified_t,
    }


def _index_stream_id(
    es_connection, offset_ms: int = 0, index_name: str = INDEX_NAME
) -> str:
    """Return the stream ID derived from the newest indexed document.

    An offset of 0 is the position the daemon derives on a cold start; a
    positive offset gives an ID after it.
    """
    timestamp_ms = get_last_indexed_timestamp_ms(
        es_connection, index_name, "last_modified_t"
    )
    assert timestamp_ms is not None
    return stream_id_from_timestamp_ms(timestamp_ms + offset_ms)


def _reset_stream(redis_client):
    """Delete the stream and the daemon state so that each test starts clean

    This also avoids appending an ID lower than a previous one, which Redis
    rejects.
    """
    redis_client.delete(
        STREAM_NAME,
        checkpoint_key(STREAM_NAME, INDEX_NAME),
        updates_state_key(STREAM_NAME, INDEX_NAME),
    )


def _wait_for(predicate, msg: str, timeout: float = 30.0, interval: float = 0.1):
    """Wait until predicate() is truthy, or fail the test"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError(f"condition not met in time: {msg}")


class DaemonRunner:
    """Run the update daemon in a background thread, and stop it cleanly"""

    def __init__(self, config):
        from app.updates import run_update_daemon

        self._run = run_update_daemon
        self._config = config
        self._thread: threading.Thread | None = None
        self._error: BaseException | None = None

    def start(self):
        def _target():
            try:
                self._run(self._config)
            except BaseException as exc:  # noqa: BLE001 - reported in stop()
                self._error = exc

        self._thread = threading.Thread(target=_target, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 30.0):
        """Wait for the thread to end, and re-raise its error if any"""
        if self._thread is None:
            return
        self._thread.join(timeout=timeout)
        assert not self._thread.is_alive(), "daemon did not stop"
        if self._error is not None:
            raise self._error


@pytest.fixture
def stop_events(monkeypatch):
    """Capture the stop events installed by the daemon, and make SIGTERM/sigint
    installation a no-op (signals can only be handled in the main thread)"""
    events: list[threading.Event] = []

    def _install(stop_event):
        events.append(stop_event)

    monkeypatch.setattr(app_updates, "_install_signal_handlers", _install)
    # make the daemon check for a stop request frequently
    monkeypatch.setattr(app_settings, "redis_reader_timeout", 0.2)
    # don't wait for minutes when testing the retries
    monkeypatch.setattr(app_updates, "RETRY_INITIAL_DELAY", 0.01)
    return events


def _run_daemon_until(config, predicate, msg: str, stop_events, timeout=60.0):
    """Run the daemon until predicate() holds, then stop it"""
    runner = DaemonRunner(config)
    runner.start()
    try:
        _wait_for(predicate, msg, timeout=timeout)
    finally:
        # ask for a clean stop, like SIGTERM does
        assert stop_events, "daemon did not install its signal handlers"
        stop_events[-1].set()
        runner.stop()


def test_update_daemon_resumes_from_checkpoint(
    test_off_config, es_connection, redis_client, stop_events, synonyms_created
):
    """An event published while the daemon is stopped must be processed after a
    restart (this is the regression from #469)"""
    from tests.cli_utils import runner_invoke

    # build the index with the first document
    result = runner_invoke(
        "import", "/opt/search/tests/int/data/test_off_data.jsonl", "--skip-updates"
    )
    assert result.exit_code == 0
    assert es_connection.count(index="test_off")["count"] == 9

    _reset_stream(redis_client)
    alias = INDEX_NAME
    # the events must be after the newest indexed document, otherwise the
    # daemon (which has no checkpoint yet) would ignore them
    event_1_id = _index_stream_id(es_connection, offset_ms=1000)
    event_2_id = _index_stream_id(es_connection, offset_ms=2000)

    # first run: event 1 is indexed, then the daemon is stopped
    redis_client.xadd(
        STREAM_NAME,
        _document("10000000000001", 1700000001),
        id=event_1_id,
    )
    _run_daemon_until(
        test_off_config,
        lambda: es_connection.exists(index=alias, id="10000000000001"),
        "daemon did not process new event in time, can't find document 10000000000001",
        stop_events,
    )
    # the checkpoint is persisted for the handled event
    assert get_checkpoint(redis_client, STREAM_NAME, alias) == event_1_id

    # event published while the daemon is not running
    redis_client.xadd(
        STREAM_NAME,
        _document("10000000000002", 1700000002),
        id=event_2_id,
    )

    # second run: the daemon must resume from the checkpoint and index event 2
    _run_daemon_until(
        test_off_config,
        lambda: es_connection.exists(index=alias, id="10000000000002"),
        "daemon did not process new event in time, can't find document 10000000000002",
        stop_events,
    )
    assert get_checkpoint(redis_client, STREAM_NAME, alias) == event_2_id
    # event 1 is still there
    assert es_connection.exists(index=alias, id="10000000000001")


def test_update_daemon_retries_transient_es_errors(
    test_off_config, es_connection, redis_client, stop_events, synonyms_created
):
    """A transient Elasticsearch error must be retried, not skipped"""
    from elasticsearch import TransportError

    # ensure the index exists so that a checkpoint can be derived
    from tests.cli_utils import runner_invoke

    result = runner_invoke(
        "import", "/opt/search/tests/int/data/test_off_data.jsonl", "--skip-updates"
    )
    assert result.exit_code == 0

    _reset_stream(redis_client)
    # the event must be after the newest indexed document, otherwise the
    # daemon (which has no checkpoint yet) would ignore it
    event_id = _index_stream_id(es_connection, offset_ms=1000)
    redis_client.xadd(
        STREAM_NAME,
        _document("10000000000003", 1700000003),
        id=event_id,
    )

    # Patch the ES client's index() method to fail a few times, then succeed.
    real_index = es_connection.index
    failures = {"left": 2}

    def flaky_index(*args, **kwargs):
        if failures["left"] > 0:
            failures["left"] -= 1
            # a status-less transport error is transient
            raise TransportError("connection reset")
        return real_index(*args, **kwargs)

    # connection.get_es_client() is per thread
    # so the daemon would run on a new, unpatched client.
    # Patch it to return the client whose index() is patched instead.
    with (
        patch.object(es_connection, "index", side_effect=flaky_index),
        patch.object(
            app_updates.connection, "get_es_client", return_value=es_connection
        ),
    ):
        _run_daemon_until(
            test_off_config,
            lambda: es_connection.exists(index="test_off", id="10000000000003"),
            "daemon did not process new event in time, can't find document 10000000000003",
            stop_events,
        )
    # index was called three times: two failures, then one success
    assert failures["left"] == 0
    assert es_connection.exists(index="test_off", id="10000000000003")


def test_update_daemon_cold_start_from_last_indexed_document(
    test_off_config, es_connection, redis_client, stop_events, synonyms_created
):
    """Without a checkpoint, the daemon starts from the newest indexed document

    Events older than it are ignored, events after it are processed.
    """
    from tests.cli_utils import runner_invoke

    result = runner_invoke(
        "import", "/opt/search/tests/int/data/test_off_data.jsonl", "--skip-updates"
    )
    assert result.exit_code == 0
    _reset_stream(redis_client)
    derived_start = _index_stream_id(es_connection, offset_ms=0)
    recent_id = _index_stream_id(es_connection, offset_ms=1000)
    # an old event, before the newest indexed document
    redis_client.xadd(
        STREAM_NAME,
        _document("10000000000004", 1700000004),
        id="1600000000000-0",
    )

    runner = DaemonRunner(test_off_config)
    runner.start()
    try:
        # the daemon started after the newest indexed document
        _wait_for(
            lambda: (
                get_checkpoint(redis_client, STREAM_NAME, "test_off") == derived_start
            ),
            f"daemon did not start from the last indexed document {derived_start}",
            timeout=30,
        )
        # the old event was not processed
        assert not es_connection.exists(index="test_off", id="10000000000004")

        redis_client.xadd(
            STREAM_NAME,
            _document("10000000000005", 1700000005),
            id=recent_id,
        )
        _wait_for(
            lambda: es_connection.exists(index="test_off", id="10000000000005"),
            "daemon did not process new event in time, can't find document 10000000000005",
            timeout=30,
        )
        _wait_for(
            lambda: get_checkpoint(redis_client, STREAM_NAME, "test_off") == recent_id,
            "daemon did not persist the checkpoint for the processed event",
            timeout=30,
        )
    finally:
        assert stop_events, "daemon did not install its signal handlers"
        stop_events[-1].set()
        runner.stop()


def test_update_daemon_waits_for_empty_index_to_be_populated(
    test_off_config,
    es_connection,
    redis_client,
    stop_events,
    monkeypatch,
    synonyms_created,
):
    """Without a checkpoint nor data, the daemon waits for the index

    It must neither start from the end of the stream (the events published
    until then would be lost) nor skip the pre-existing events: once the index
    is populated, it starts from the newest indexed document.

    Note that we don't delete the real index (other tests need it): we only
    make the "newest indexed document" lookup return nothing, which is what
    happens on an empty index.
    """
    from tests.cli_utils import runner_invoke

    results = {"empty": True}
    real_get_last_indexed_timestamp_ms = app_updates.get_last_indexed_timestamp_ms
    started = threading.Event()

    def get_last_indexed_timestamp_ms(*args, **kwargs):
        if results["empty"]:
            return None
        timestamp_ms = real_get_last_indexed_timestamp_ms(*args, **kwargs)
        started.set()
        return timestamp_ms

    monkeypatch.setattr(
        app_updates, "get_last_indexed_timestamp_ms", get_last_indexed_timestamp_ms
    )

    _reset_stream(redis_client)
    # a pre-existing event must not be processed
    redis_client.xadd(
        STREAM_NAME,
        _document("10000000000006", 1700000006),
        id="1600000000000-0",
    )

    runner = DaemonRunner(test_off_config)
    runner.start()
    try:
        # the daemon waits: it does not even read the stream
        assert not started.wait(timeout=2)
        assert not es_connection.exists(index="test_off", id="10000000000006")

        # populate the index, as an import would do
        result = runner_invoke(
            "import", "/opt/search/tests/int/data/test_off_data.jsonl", "--skip-updates"
        )
        assert result.exit_code == 0
        results["empty"] = False
        expected_start = _index_stream_id(es_connection, offset_ms=0)
        new_event_id = _index_stream_id(es_connection, offset_ms=1000)

        # the daemon starts from the newest indexed document: the old event is
        # still ignored...
        assert started.wait(timeout=30)
        _wait_for(
            lambda: (
                get_checkpoint(redis_client, STREAM_NAME, "test_off") == expected_start
            ),
            f"daemon did not start from the last indexed document {expected_start}",
            timeout=30,
        )
        assert not es_connection.exists(index="test_off", id="10000000000006")

        # ...but new events are processed
        redis_client.xadd(
            STREAM_NAME,
            _document("10000000000007", 1700000007),
            id=new_event_id,
        )
        _wait_for(
            lambda: es_connection.exists(index="test_off", id="10000000000007"),
            "daemon did not process new event in time, can't find document 10000000000007",
            timeout=30,
        )
    finally:
        assert stop_events, "daemon did not install its signal handlers"
        stop_events[-1].set()
        runner.stop()

    assert es_connection.exists(index="test_off", id="10000000000007")
