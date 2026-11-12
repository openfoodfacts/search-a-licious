"""Persist the position reached in a Redis stream.

The update daemon reads a Redis stream to know which documents changed. To be
able to resume where it stopped after a restart (deployment, crash, ES blip),
it stores the ID of the last handled stream entry in Redis.

A checkpoint is identified by both the stream name *and* the index alias the
events are written to, because the same stream may be consumed for different
indexes.

This module also stores *informational* processing state of the update daemon
(:func:`set_updates_state`), read by the health endpoint. It lives under its
own key prefix, so that it can never interfere with the durability contract of
the checkpoints.
"""

from typing import Any, cast

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search
from redis import Redis

CHECKPOINT_KEY_PREFIX = "searchalicious:checkpoint"
UPDATES_STATE_KEY_PREFIX = "searchalicious:updates_state"


def checkpoint_key(stream_name: str, index_name: str) -> str:
    """Return the Redis key storing the checkpoint of a stream for an index.

    :param stream_name: the name of the Redis stream
    :param index_name: the name of the index (the alias) the events are
        written to
    :return: the Redis key, e.g.
        ``searchalicious:checkpoint:product_updates_off:off``
    """
    return f"{CHECKPOINT_KEY_PREFIX}:{stream_name}:{index_name}"


def get_checkpoint(
    redis_client: Redis, stream_name: str, index_name: str
) -> str | None:
    """Return the last handled stream ID for this stream and index.

    :param redis_client: the Redis client
    :param stream_name: the name of the Redis stream
    :param index_name: the name of the index (the alias)
    :return: the last handled stream ID, or ``None`` if there is no checkpoint
        (i.e. the daemon never ran for this stream and index)

    Any Redis error is propagated, so that the caller can distinguish "no
    checkpoint" (``None``) from "could not read the checkpoint" (exception).
    """
    # the client is configured with decode_responses=True, so the value is a str
    return cast(str | None, redis_client.get(checkpoint_key(stream_name, index_name)))


def set_checkpoint(
    redis_client: Redis, stream_name: str, index_name: str, stream_id: str
) -> None:
    """Record the last handled stream ID for this stream and index.

    :param redis_client: the Redis client
    :param stream_name: the name of the Redis stream
    :param index_name: the name of the index (the alias)
    :param stream_id: the Redis stream ID of the last handled event
    """
    redis_client.set(checkpoint_key(stream_name, index_name), stream_id)


def updates_state_key(stream_name: str, index_name: str) -> str:
    """Return the Redis key storing the processing state of the update daemon.

    :param stream_name: the name of the Redis stream
    :param index_name: the name of the index (the alias) the events are
        written to
    :return: the Redis key, e.g.
        ``searchalicious:updates_state:product_updates_off:off``
    """
    return f"{UPDATES_STATE_KEY_PREFIX}:{stream_name}:{index_name}"


def set_updates_state(
    redis_client: Redis,
    stream_name: str,
    index_name: str,
    last_read_id: str | None,
    pending_events: int,
) -> None:
    """Record the processing state of the update daemon for this stream/index.

    This is purely informational (for monitoring): it is written atomically so
    that a reader never sees a torn state, but it is not part of the resume
    contract.

    :param redis_client: the Redis client
    :param stream_name: the name of the Redis stream
    :param index_name: the name of the index (the alias)
    :param last_read_id: the stream ID of the last event read by the daemon
    :param pending_events: the number of read events still to be processed
    """
    redis_client.hset(
        updates_state_key(stream_name, index_name),
        mapping={
            "last_read_id": last_read_id if last_read_id is not None else "",
            "pending_events": pending_events,
        },
    )


def get_updates_state(
    redis_client: Redis, stream_name: str, index_name: str
) -> dict[str, Any] | None:
    """Return the processing state of the update daemon for this stream/index.

    :param redis_client: the Redis client
    :param stream_name: the name of the Redis stream
    :param index_name: the name of the index (the alias)
    :return: a dict with the ``last_read_id`` (str or ``None``) and
        ``pending_events`` (int) keys, or ``None`` if the daemon never
        recorded its state (e.g. it never ran)
    """
    raw = cast(
        dict[str, str], redis_client.hgetall(updates_state_key(stream_name, index_name))
    )
    if not raw:
        return None
    last_read_id = raw.get("last_read_id") or None
    pending_events = raw.get("pending_events")
    return {
        "last_read_id": last_read_id,
        "pending_events": int(pending_events) if pending_events is not None else None,
    }


def get_last_indexed_timestamp_ms(
    es_client: Elasticsearch, index: str, last_modified_field_name: str
) -> int | None:
    """Return the ``last_modified`` timestamp of the most recent document
    in the given index, in milliseconds.

    This is used to derive a starting position in the Redis stream, both at
    the end of a full import and when the daemon has no checkpoint yet.

    :param es_client: the Elasticsearch client
    :param index: the index (or alias) to query
    :param last_modified_field_name: the name of the field holding the last
        modification timestamp (in seconds)
    :return: the newest timestamp in milliseconds, or ``None`` if the index
        is empty
    """
    query = (
        Search(index=index, using=es_client)
        .sort(f"-{last_modified_field_name}")
        .extra(size=1)
    )
    # Note that we can't use index() because we don't want to also query the
    # main alias (the index may be a temporary one during an import)
    query._index = [index]
    results = query.execute()
    for result in results:
        timestamp = result.to_dict().get(last_modified_field_name)
        if timestamp is None:
            continue
        return int(timestamp * 1000)
    return None


def stream_id_from_timestamp_ms(timestamp_ms: int) -> str:
    """Build a Redis stream ID from a timestamp in milliseconds.

    We use sequence ``0``, the lowest possible sequence for this millisecond,
    so that events sharing the same millisecond as the last indexed document
    are replayed rather than skipped (re-indexing a document is idempotent,
    skipping it is not).

    :param timestamp_ms: the timestamp in milliseconds
    :return: a stream ID such as ``"1629878400000-0"``
    """
    return f"{timestamp_ms}-0"


def timestamp_ms_from_stream_id(stream_id: str) -> int | None:
    """Return the timestamp part of a Redis stream ID, in milliseconds.

    :param stream_id: a stream ID such as ``"1629878400000-0"``
    :return: the timestamp in milliseconds, or ``None`` if the ID cannot be
        parsed
    """
    try:
        return int(stream_id.split("-")[0])
    except (AttributeError, ValueError):
        return None
