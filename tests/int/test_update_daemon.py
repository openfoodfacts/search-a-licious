"""Integration tests of the update daemon against a real Elasticsearch and Redis.

The daemon is run in a thread (so that it can be stopped from the test), on a
stream that is fed by the test.
"""

import threading
import time
from unittest.mock import patch

import pytest

from app import _import as app_import
from app.checkpoints import checkpoint_key, get_checkpoint

STREAM_NAME = "product_updates_off"


def _document(code: str, last_modified_t: int) -> dict:
    """Return a document suitable for the test index and the TestDocumentFetcher"""
    return {
        "code": code,
        "product_name": {"en": f"Product {code}"},
        "last_modified_t": last_modified_t,
    }


def _reset_stream(redis_client):
    """Delete the stream and the checkpoint so that each test starts clean

    This also avoids appending an ID lower than a previous one, which Redis
    rejects.
    """
    redis_client.delete(STREAM_NAME, checkpoint_key(STREAM_NAME, "test_off"))


def _wait_for(predicate, timeout: float = 30.0, interval: float = 0.1):
    """Wait until predicate() is truthy, or fail the test"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError("condition not met in time")


class DaemonRunner:
    """Run the update daemon in a background thread, and stop it cleanly"""

    def __init__(self, config):
        from app._import import run_update_daemon

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

    monkeypatch.setattr(app_import, "_install_signal_handlers", _install)
    # make the daemon check for a stop request frequently
    monkeypatch.setattr(app_import.settings, "redis_reader_timeout", 0.2)
    # don't wait for minutes when testing the retries
    monkeypatch.setattr(app_import, "RETRY_INITIAL_DELAY", 0.01)
    return events


def _run_daemon_until(config, predicate, stop_events, timeout=60.0):
    """Run the daemon until predicate() holds, then stop it"""
    runner = DaemonRunner(config)
    runner.start()
    try:
        _wait_for(predicate, timeout=timeout)
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
    alias = "test_off"

    # first run: event 1 is indexed, then the daemon is stopped
    redis_client.xadd(
        STREAM_NAME,
        _document("10000000000001", 1700000001),
        id="1700000001000-0",
    )
    _run_daemon_until(
        test_off_config,
        lambda: es_connection.exists(index=alias, id="10000000000001"),
        stop_events,
    )
    # the checkpoint is persisted for the handled event
    assert get_checkpoint(redis_client, STREAM_NAME, alias) == "1700000001000-0"

    # event published while the daemon is not running
    redis_client.xadd(
        STREAM_NAME,
        _document("10000000000002", 1700000002),
        id="1700000002000-0",
    )

    # second run: the daemon must resume from the checkpoint and index event 2
    _run_daemon_until(
        test_off_config,
        lambda: es_connection.exists(index=alias, id="10000000000002"),
        stop_events,
    )
    assert get_checkpoint(redis_client, STREAM_NAME, alias) == "1700000002000-0"
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
    redis_client.xadd(
        STREAM_NAME,
        _document("10000000000003", 1700000003),
        id="1700000003000-0",
    )

    real_index = es_connection.index
    failures = {"left": 2}

    def flaky_index(*args, **kwargs):
        if failures["left"] > 0:
            failures["left"] -= 1
            # a status-less transport error is transient
            raise TransportError("connection reset")
        return real_index(*args, **kwargs)

    # the daemon uses the (cached) connection returned by connection.get_es_client()
    with patch.object(es_connection, "index", side_effect=flaky_index):
        _run_daemon_until(
            test_off_config,
            lambda: es_connection.exists(index="test_off", id="10000000000003"),
            stop_events,
        )

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
    # an old event, before the last modified document (1700525044 s)
    redis_client.xadd(
        STREAM_NAME,
        _document("10000000000004", 1700000004),
        id="1600000000000-0",
    )
    # a recent event
    redis_client.xadd(
        STREAM_NAME,
        _document("10000000000005", 1700000005),
        id="1800000000000-0",
    )

    _run_daemon_until(
        test_off_config,
        lambda: es_connection.exists(index="test_off", id="10000000000005"),
        stop_events,
    )
    # the daemon started after the newest indexed document
    start = get_checkpoint(redis_client, STREAM_NAME, "test_off")
    assert start is not None
    assert int(start.split("-")[0]) >= 1700525044000
    # the old event was not processed
    assert not es_connection.exists(index="test_off", id="10000000000004")


def test_update_daemon_cold_start_with_empty_index(
    test_off_config, es_connection, redis_client, stop_events, monkeypatch
):
    """Without a checkpoint nor data, the daemon starts from the end of the stream

    It must not persist a checkpoint in that case: it would freeze the position
    at "$" even once the index would be populated.

    Note that we don't delete the real index (other tests need it): we only
    make the "newest indexed document" lookup return nothing, which is what
    happens on an empty index.
    """
    captured = {}
    real_get_new_updates = app_import.get_new_updates

    def wrapping_get_new_updates(*args, **kwargs):
        captured["min_ids"] = kwargs.get("min_ids")
        return real_get_new_updates(*args, **kwargs)

    monkeypatch.setattr(app_import, "get_new_updates", wrapping_get_new_updates)
    monkeypatch.setattr(
        app_import, "get_last_indexed_timestamp_ms", lambda *args, **kwargs: None
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
        _wait_for(lambda: captured.get("min_ids") is not None, timeout=30)
    finally:
        assert stop_events, "daemon did not install its signal handlers"
        stop_events[-1].set()
        runner.stop()

    assert captured["min_ids"] == {STREAM_NAME: "$"}
    assert get_checkpoint(redis_client, STREAM_NAME, "test_off") is None
    assert not es_connection.exists(index="test_off", id="10000000000006")
