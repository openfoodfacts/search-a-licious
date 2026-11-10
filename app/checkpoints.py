"""Persist the position reached in a Redis stream.

The update daemon reads a Redis stream to know which documents changed. To be
able to resume where it stopped after a restart (deployment, crash, ES blip),
it stores the ID of the last handled stream entry in Redis.

A checkpoint is identified by both the stream name *and* the index alias the
events are written to, because the same stream may be consumed for different
indexes.
"""

from typing import cast

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search
from redis import Redis

CHECKPOINT_KEY_PREFIX = "searchalicious:checkpoint"


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
