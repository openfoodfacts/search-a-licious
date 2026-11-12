"""Update daemon: keep an Elasticsearch index up to date from Redis streams.

Applications publish the documents that changed to a Redis stream. This module
consumes such a stream, fetches each changed document and writes it to the
index, forever.

Two properties matter here:

* **no lost event**: the position reached in the stream is persisted in Redis
  after each handled event (see :mod:`app.checkpoints`), so a restart resumes
  where it stopped, and an event is never acknowledged before being indexed;
* **no crash on a transient error**: Elasticsearch and Redis outages are
  retried with an exponential backoff, instead of stopping the daemon.

The reader of the stream (:func:`app._import.get_new_updates`) and the
document fetchers are shared with the import process, which uses the same
stream to catch up with the events published during a full import.
"""

import random
import signal
import threading
import time
from typing import Callable

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.exceptions import ApiError, ConflictError
from elasticsearch.exceptions import ConnectionError as ESConnectionError
from elasticsearch.exceptions import TransportError
from redis import Redis
from redis.exceptions import BusyLoadingError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app._import import BaseDocumentFetcher, get_new_updates, load_document_fetcher
from app._types import FetcherResult, FetcherStatus
from app.checkpoints import (
    get_checkpoint,
    get_last_indexed_timestamp_ms,
    set_checkpoint,
    set_updates_state,
    stream_id_from_timestamp_ms,
)
from app.config import Config, IndexConfig
from app.indexing import DocumentProcessor
from app.utils import connection, get_logger

logger = get_logger(__name__)

# Retry policy for transient errors.
# The delay starts at RETRY_INITIAL_DELAY seconds, doubles after each attempt
# and is capped at RETRY_MAX_DELAY seconds, with a +-RETRY_JITTER relative
# random variation to avoid synchronized retries.
RETRY_INITIAL_DELAY = 1.0
RETRY_MAX_DELAY = 60.0
RETRY_JITTER = 0.2

# HTTP statuses that mean "the cluster is temporarily unable to serve this
# request" (rate limiting, shard/node unavailable, gateway timeouts).
RETRYABLE_HTTP_STATUSES = frozenset({429, 502, 503, 504})

# Minimum delay between two writes of the processing state in Redis (see
# UpdatesStateRecorder). The state is informational only: throttling it avoids
# a Redis write per event on a busy stream.
UPDATES_STATE_WRITE_INTERVAL = 10.0


class UpdatesStateRecorder:
    """Record the processing state of the daemon for the health endpoint.

    The state (the ID of the last event read by the daemon and the number of
    read events still to be processed) is informational: writing it must never
    slow down or break the daemon. Writes are therefore throttled to at most
    one per ``UPDATES_STATE_WRITE_INTERVAL`` seconds, and errors are logged and
    ignored.

    A throttled write is "leading edge": the value is written as soon as it
    changes after the interval, the intermediate values being skipped. The
    stream being quiet is the signal to flush the latest value (see
    :meth:`flush_if_due`), so that the state settles at its final value when
    the daemon has nothing left to do.
    """

    def __init__(
        self,
        redis_client: Redis,
        stream_name: str,
        index_name: str,
        interval: float = UPDATES_STATE_WRITE_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        :param redis_client: the Redis client
        :param stream_name: the name of the Redis stream
        :param index_name: the name of the index (the alias)
        :param interval: the minimum delay between two writes, in seconds
        :param clock: the clock used to measure elapsed time
        """
        self.redis_client = redis_client
        self.stream_name = stream_name
        self.index_name = index_name
        self.interval = interval
        self.clock = clock
        self.last_read_id: str | None = None
        self.pending_events = 0
        self._last_write: float | None = None

    def set(self, last_read_id: str | None, pending_events: int) -> None:
        """Record the current state, throttled.

        :param last_read_id: the ID of the last event read by the daemon
        :param pending_events: the number of read events still to be processed
        """
        self.last_read_id = last_read_id
        self.pending_events = pending_events
        self.flush_if_due()

    def add_pending(self, delta: int) -> None:
        """Update the number of pending events, keeping the last read ID.

        The write is throttled like :meth:`set`.

        :param delta: the number of events to add to (or remove from) the
            pending count
        """
        self.pending_events = max(0, self.pending_events + delta)
        self.flush_if_due()

    def flush_if_due(self) -> None:
        """Write the state if the throttle interval has elapsed.

        Does nothing if a write happened less than ``interval`` seconds ago.
        """
        now = self.clock()
        if self._last_write is not None and now - self._last_write < self.interval:
            return
        self.flush()

    def flush(self) -> None:
        """Write the state now, whatever the throttle says.

        Failures are logged and ignored: the state is not critical.
        """
        try:
            set_updates_state(
                self.redis_client,
                self.stream_name,
                self.index_name,
                self.last_read_id,
                self.pending_events,
            )
        except Exception as exc:
            logger.warning(
                "Could not record the processing state for stream %s and index %s: %s",
                self.stream_name,
                self.index_name,
                exc,
            )
            return
        self._last_write = self.clock()


def is_retryable_error(exc: Exception) -> bool:
    """Tell whether an error is transient and the operation should be retried.

    The check order matters: in elasticsearch-py 8.x, ``NotFoundError`` and
    ``ConflictError`` are subclasses of ``ApiError``, which is itself a
    subclass of ``TransportError``. Subclasses must therefore be tested before
    their parents.

    :param exc: the exception raised
    :return: True if waiting and retrying may succeed
    """
    if isinstance(exc, (NotFoundError, ConflictError)):
        # Document-level errors: retrying the same request will not help.
        return False
    if isinstance(exc, ApiError):
        status = getattr(exc, "status_code", None)
        return status in RETRYABLE_HTTP_STATUSES
    if isinstance(exc, ESConnectionError):
        # Covers TimeoutError and SSLError, which are subclasses
        return True
    if isinstance(exc, TransportError):
        # Status-less transport error (e.g. malformed/unexpected response):
        # usually the cluster is in a bad state, give it a chance to recover.
        return True
    if isinstance(exc, (RedisConnectionError, RedisTimeoutError, BusyLoadingError)):
        return True
    if isinstance(exc, RedisError):
        # Other Redis errors (wrong type, data error...) will not heal by
        # themselves.
        return False
    return False


def retry_delay(attempt: int) -> float:
    """Return the delay to wait before the n-th retry of a transient error.

    The delay is ``RETRY_INITIAL_DELAY`` doubled on each attempt, capped at
    ``RETRY_MAX_DELAY``, with a random jitter of +-``RETRY_JITTER`` (relative)
    so that several processes don't retry at the exact same time.

    :param attempt: the number of retries already performed (0 for the first)
    :return: the delay in seconds
    """
    delay = min(RETRY_INITIAL_DELAY * (2**attempt), RETRY_MAX_DELAY)
    jitter = delay * RETRY_JITTER
    return max(0.0, delay + random.uniform(-jitter, jitter))


def process_event(
    stream_name: str,
    result: FetcherResult,
    processor: DocumentProcessor,
    es_client: Elasticsearch,
    index_name: str,
) -> None:
    """Index (or remove) a single document in Elasticsearch.

    This is idempotent: indexing the same document twice only refreshes its
    ``last_indexed_datetime``, so it is safe to retry the whole event.

    :param stream_name: the name of the Redis stream (for logging)
    :param result: the document fetched from the stream
    :param processor: the document processor of the target index
    :param es_client: the Elasticsearch client
    :param index_name: the index (alias) to write to
    """
    processed_result = processor.from_result(result)
    processed_document = processed_result.document
    if (
        processed_result.status not in (FetcherStatus.FOUND, FetcherStatus.REMOVED)
        or processed_document is None
    ):
        return
    _id = processed_document.pop("_id")
    logger.debug("Document:\n%s", processed_document)
    if processed_result.status == FetcherStatus.REMOVED:
        try:
            es_client.delete(index=index_name, id=_id)
        except NotFoundError:
            # already absent from the index, nothing to do
            logger.info("Document %s to remove is not in the index", _id)
    else:
        es_client.index(index=index_name, body=processed_document, id=_id)


def retry_until_done(
    what: str,
    func: Callable[[], None],
    stop_event: threading.Event,
    skip_non_retryable: bool = True,
) -> bool:
    """Call func, retrying on transient errors until it is done.

    Transient errors (see :func:`is_retryable_error`) are retried with an
    exponential backoff, forever: no event is ever skipped because of a
    temporary Elasticsearch or Redis outage. Non-retryable errors are logged
    and skipped by default, so that a single invalid document cannot block the
    whole stream forever (the checkpoint is still advanced by the caller,
    which means the document is only re-indexed if it changes again).

    :param what: a short description of the operation, for logging
    :param func: the (idempotent) function to call
    :param stop_event: if set while waiting, give up retrying and return
    :param skip_non_retryable: if True (the default), a non-retryable error is
        logged and the operation is skipped. If False, it is re-raised to the
        caller (used for operations that must not be silently dropped).
    :return: True if the operation was not canceled, False otherwise
    """
    attempt = 0
    while True:
        try:
            func()
            return True
        except Exception as exc:
            if not is_retryable_error(exc):
                if not skip_non_retryable:
                    raise
                logger.exception("Non-retryable error while %s, skipping it", what)
                return True
            delay = retry_delay(attempt)
            attempt += 1
            logger.warning(
                "Transient error while %s, retrying in %.1fs (attempt %d): %s",
                what,
                delay,
                attempt,
                exc,
            )
            # `wait` returns as soon as the event is set, so a stop request
            # does not have to wait for the whole backoff delay.
            if stop_event.wait(delay):
                logger.info("Stop requested, giving up retries")
                return False


def track_event(
    redis_client: Redis,
    es_client: Elasticsearch,
    stream_name: str,
    stream_id: str,
    result: FetcherResult,
    processor: DocumentProcessor,
    index_name: str,
    stop_event: threading.Event,
) -> str | None:
    """Index an event and persist the position it allows to resume from.

    Both steps are retried on transient errors (see :func:`retry_until_done`).
    The position is only persisted once the event has been handled (indexed,
    removed, skipped or permanently failed), which gives at-least-once
    semantics: after a crash, the last unconfirmed event is processed again
    (indexing is idempotent).

    :param redis_client: the Redis client, storing the checkpoints
    :param es_client: the Elasticsearch client
    :param stream_name: the name of the Redis stream
    :param stream_id: the ID of the event in the stream
    :param result: the document fetched from the stream
    :param processor: the document processor of the target index
    :param index_name: the index (alias) the documents are written to
    :param stop_event: if set while retrying, give up
    :return: the stream cursor to use to read the next event, or ``None`` if
        the daemon was stopped before the event could be handled
    """
    what = f"processing event {stream_id} from {stream_name}"
    canceled = not retry_until_done(
        what,
        lambda: process_event(stream_name, result, processor, es_client, index_name),
        stop_event,
    )
    if canceled:
        # not handled: keep the previous cursor and checkpoint
        return None
    # A checkpoint failure must not be silently ignored: without it, a restart
    # would replay the event, which is safe but hides the problem.
    retry_until_done(
        f"persisting the checkpoint after event {stream_id} from {stream_name}",
        lambda: set_checkpoint(redis_client, stream_name, index_name, stream_id),
        stop_event,
        skip_non_retryable=False,
    )
    # XREAD returns the entries strictly after the given ID, so returning the
    # ID of this event is enough to not read it again (a rebuilt generator
    # starts from the checkpoint).
    return stream_id


def wait_for_start_position(
    redis_client: Redis,
    es_client: Elasticsearch,
    stream_name: str,
    index_name: str,
    last_modified_field_name: str,
    stop_event: threading.Event,
) -> str | None:
    """Wait for the index to be populated, then return the stream ID to start
    reading from.

    The position is read from the persisted checkpoint. If there is none (first
    run, or checkpoint deleted), it is derived from the most recent document of
    the index, so that events published while the daemon was not running are
    not lost.

    Deriving that position requires the index to be populated (usually by an
    import). As long as it is empty, the daemon waits: starting from the end of
    the stream instead would silently drop the events published meanwhile.
    A stop request interrupts the wait.

    :param redis_client: the Redis client
    :param es_client: the Elasticsearch client
    :param stream_name: the name of the Redis stream
    :param index_name: the name of the index alias the events are written to
    :param last_modified_field_name: the field holding the last modification
        timestamp of the documents
    :param stop_event: if set while waiting for the index, give up
    :return: the stream ID to start from, or ``None`` if the daemon was asked
        to stop while the index was still empty
    """
    checkpoint = get_checkpoint(redis_client, stream_name, index_name)
    if checkpoint is not None:
        logger.info(
            "Resuming stream %s for index %s from checkpoint %s",
            stream_name,
            index_name,
            checkpoint,
        )
        return checkpoint

    attempt = 0
    while not stop_event.is_set():
        try:
            last_indexed_ms = get_last_indexed_timestamp_ms(
                es_client, index_name, last_modified_field_name
            )
        except Exception as exc:
            if not (isinstance(exc, NotFoundError) or is_retryable_error(exc)):
                raise
            logger.info("Index %s is not available yet: %s", index_name, exc)
            last_indexed_ms = None
        if last_indexed_ms is not None:
            start_id = stream_id_from_timestamp_ms(last_indexed_ms)
            # Persist immediately: the derived position is meaningful, and this
            # avoids querying Elasticsearch again on every restart.
            set_checkpoint(redis_client, stream_name, index_name, start_id)
            logger.info(
                "No checkpoint for stream %s and index %s, starting from the "
                "last indexed document (%s)",
                stream_name,
                index_name,
                start_id,
            )
            return start_id
        delay = retry_delay(attempt)
        attempt += 1
        logger.info(
            "No checkpoint and no document yet for stream %s and index %s: "
            "waiting for the index to be populated (checked in %.0fs)",
            stream_name,
            index_name,
            delay,
        )
        if stop_event.wait(delay):
            return None

    return None


def reset_checkpoint_after_import(
    es_client: Elasticsearch, config: IndexConfig
) -> None:
    """Move the update daemon checkpoint to the end of the imported data.

    The import already took into account the stream events up to the most
    recent document (see :func:`app._import.get_redis_updates`), and the alias
    now points to the new index. Keeping the previous checkpoint would only
    cause a (harmless but wasteful) replay of old events by the daemon.

    This is best effort: a failure here is logged and does not fail the
    import, since a stale checkpoint only leads to a replay.

    :param es_client: the Elasticsearch client
    :param config: the index configuration used for the import
    """
    if config.redis_stream_name is None:
        logger.info("Redis updates are disabled for index %s", config.index.name)
        return
    try:
        last_indexed_ms = get_last_indexed_timestamp_ms(
            es_client, config.index.name, config.index.last_modified_field_name
        )
        if last_indexed_ms is None:
            logger.warning(
                "Index %s is empty, leaving the update checkpoint untouched",
                config.index.name,
            )
            return
        stream_id = stream_id_from_timestamp_ms(last_indexed_ms)
        redis_client = connection.get_redis_client()
        set_checkpoint(
            redis_client, config.redis_stream_name, config.index.name, stream_id
        )
        logger.info(
            "Update checkpoint for stream %s and index %s set to %s",
            config.redis_stream_name,
            config.index.name,
            stream_id,
        )
    except Exception as exc:
        logger.warning("Could not reset the update checkpoint: %s", exc)


def _install_signal_handlers(stop_event: threading.Event) -> None:
    """Make SIGTERM/SIGINT request a clean stop of the daemon.

    The handler only sets the event: the main loop notices it when it comes
    back from its read timeout and exits normally.

    :param stop_event: the event to set when a signal is received
    """

    def _handler(signum, _frame):
        logger.info("Received signal %s, requesting a clean stop", signum)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _handler)


def _init_min_ids(
    redis_client: Redis,
    es_client: Elasticsearch,
    stream_index_configs: dict[str, IndexConfig],
    stop_event: threading.Event,
) -> dict[str, str] | None:
    """Read the start position of each stream from the persisted checkpoints.

    Checkpoints are read once at startup. After that, the daemon keeps track
    of its position itself and persists it after each handled event.

    :param redis_client: the Redis client
    :param es_client: the Elasticsearch client
    :param stream_index_configs: the index configuration of each stream
    :param stop_event: if set while waiting for an index, give up
    :return: the stream ID to start reading from, for each stream, or ``None``
        if a stop was requested before an index was ready
    """
    min_ids: dict[str, str] = {}
    for stream_name, index_config in stream_index_configs.items():
        start_id = wait_for_start_position(
            redis_client,
            es_client,
            stream_name,
            index_config.index.name,
            index_config.index.last_modified_field_name,
            stop_event,
        )
        if start_id is None:
            return None
        min_ids[stream_name] = start_id
    return min_ids


def _init_state_recorders(
    redis_client: Redis,
    stream_index_configs: dict[str, IndexConfig],
    min_ids: dict[str, str],
) -> dict[str, UpdatesStateRecorder]:
    """Create the processing state recorders, read by the health endpoint.

    :param redis_client: the Redis client
    :param stream_index_configs: the index configuration of each stream
    :param min_ids: the stream ID the daemon starts reading from, for each
        stream
    :return: the state recorder of each stream, initialized with the start
        position and no pending event
    """
    state_recorders = {
        stream_name: UpdatesStateRecorder(
            redis_client, stream_name, index_config.index.name
        )
        for stream_name, index_config in stream_index_configs.items()
    }
    for stream_name, recorder in state_recorders.items():
        recorder.set(min_ids[stream_name], 0)
    return state_recorders


def _consume_streams(
    redis_client: Redis,
    es_client: Elasticsearch,
    processors: dict[str, DocumentProcessor],
    document_fetchers: dict[str, BaseDocumentFetcher],
    id_field_names: dict[str, str],
    stream_index_configs: dict[str, IndexConfig],
    state_recorders: dict[str, UpdatesStateRecorder],
    min_ids: dict[str, str] | None,
    stop_event: threading.Event,
) -> None:
    """Read the streams and track the events until a stop is requested.

    If the generator fails (e.g. a Redis error during xread), it is rebuilt
    from the persisted checkpoints: the events of the in-flight batch that
    were not handled yet are then read again. Transient errors are retried
    with a backoff (see :func:`is_retryable_error`), while other errors are
    re-raised.

    :param redis_client: the Redis client
    :param es_client: the Elasticsearch client
    :param processors: the document processor of each stream
    :param document_fetchers: the document fetcher of each stream
    :param id_field_names: the name of the ID field of each stream
    :param stream_index_configs: the index configuration of each stream
    :param state_recorders: the processing state recorder of each stream
    :param min_ids: the stream ID to start reading from, for each stream
    :param stop_event: the event requesting a clean stop
    """

    def flush_state_if_due() -> None:
        for recorder in state_recorders.values():
            recorder.flush_if_due()

    def track_pending_entries(
        stream_name: str, entries: list[tuple[str, dict]]
    ) -> None:
        state_recorders[stream_name].add_pending(len(entries))

    attempt = 0
    while not stop_event.is_set():
        try:
            if min_ids is None:
                # ask for min_ids to be re-read from the persisted checkpoints
                min_ids = _init_min_ids(
                    redis_client, es_client, stream_index_configs, stop_event
                )
                if min_ids is None:
                    logger.info("Stop requested before the index was ready, exiting")
                    return
            for stream_name, _, stream_id, result in get_new_updates(
                redis_client,
                list(id_field_names.keys()),
                id_field_names=id_field_names,
                document_fetchers=document_fetchers,
                min_ids=min_ids,
                stop_event=stop_event,
                # The stream is quiet: flush the state so that it settles at
                # its final value instead of waiting for the next event.
                on_batch_end=flush_state_if_due,
                on_batch_read=track_pending_entries,
            ):
                recorder = state_recorders[stream_name]
                recorder.add_pending(-1)
                _min_id = track_event(
                    redis_client,
                    es_client,
                    stream_name=stream_name,
                    stream_id=stream_id,
                    result=result,
                    processor=processors[stream_name],
                    index_name=stream_index_configs[stream_name].index.name,
                    stop_event=stop_event,
                )
                if _min_id is not None:
                    min_ids[stream_name] = _min_id
                    recorder.set(stream_id, recorder.pending_events)
                    # A retry may have been successful after several failures:
                    # reset the backoff.
                    attempt = 0
        except Exception as exc:
            if not is_retryable_error(exc):
                raise
            delay = retry_delay(attempt)
            attempt += 1
            logger.warning(
                "Transient error while reading updates, restarting from the "
                "checkpoint in %.1fs (attempt %d): %s",
                delay,
                attempt,
                exc,
            )
            if stop_event.wait(delay):
                break
            # The connection may be dead after an outage: open a new one.
            es_client = connection.get_es_client()
            # ask for min_ids to be re-read from the persisted checkpoints
            min_ids = None


def run_update_daemon(config: Config) -> None:
    """Run the update import daemon.

    This daemon listens to the Redis stream containing information about
    updated documents, fetches the full document and indexes it in
    Elasticsearch.

    Its position in the stream is persisted in Redis (see
    :mod:`app.checkpoints`) after each handled event, so that a restart resumes
    where it stopped instead of skipping the events published meanwhile.
    Transient Elasticsearch/Redis errors are retried with a backoff instead of
    crashing the process. If the index is empty and there is no checkpoint yet,
    it waits for the import to populate the index before starting.

    :param config: the configuration to use
    """
    logger.info("Starting update import daemon")
    es_client = connection.get_es_client()
    # redis-py defaults to a read timeout of 5s, which would make a blocking
    # xread raise. We use a finite block timeout instead (see
    # settings.redis_reader_timeout), so that the daemon can react to a stop
    # request even when the stream is idle.
    redis_client = connection.get_redis_client(socket_timeout=None)

    if redis_client.ping():
        logger.info("Connected to Redis")
    else:
        logger.error("Could not connect to Redis")
        return

    if len(list(config.indices)) != 1:
        raise ValueError("Only one index is supported")

    processors: dict[str, DocumentProcessor] = {}
    document_fetchers: dict[str, BaseDocumentFetcher] = {}
    id_field_names: dict[str, str] = {}
    stream_index_configs: dict[str, IndexConfig] = {}

    for index_config in config.indices.values():
        stream_name = index_config.redis_stream_name
        if stream_name is not None:
            processors[stream_name] = DocumentProcessor(index_config)
            document_fetchers[stream_name] = load_document_fetcher(index_config)
            id_field_names[stream_name] = index_config.index.id_field_name
            stream_index_configs[stream_name] = index_config

    if not id_field_names:
        logger.info("No Redis stream configured, nothing to listen to")
        return

    stop_event = threading.Event()
    _install_signal_handlers(stop_event)

    min_ids = _init_min_ids(redis_client, es_client, stream_index_configs, stop_event)
    if min_ids is None:
        logger.info("Stop requested before the index was ready, exiting")
        return

    state_recorders = _init_state_recorders(redis_client, stream_index_configs, min_ids)

    _consume_streams(
        redis_client,
        es_client,
        processors,
        document_fetchers,
        id_field_names,
        stream_index_configs,
        state_recorders,
        min_ids,
        stop_event,
    )

    # Flush the state one last time without throttling
    for recorder in state_recorders.values():
        recorder.flush()

    logger.info("Stop requested, exiting")
