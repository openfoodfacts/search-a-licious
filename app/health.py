"""This module contains the health check functions for the application.

It is based upon the `py-healthcheck`_ library.

.. _py-healthcheck: https://github.com/klen/py-healthcheck
"""

import time
from typing import Any

from healthcheck import HealthCheck

from app.checkpoints import get_updates_state, timestamp_ms_from_stream_id
from app.config import get_config
from app.utils import connection, get_logger

logger = get_logger(__name__)

health = HealthCheck()


def test_connect_redis():
    """Test connection to REDIS."""
    logger.debug("health: testing redis connection")
    client = connection.get_redis_client(socket_connect_timeout=5)
    if client.ping():
        return True, "Redis connection check succedded!"
    return False, "Redis connection check failed!"


def test_connect_es():
    """Test connection to ElasticSearch."""
    logger.debug("health: testing es connection")
    # use a derived client, to not replace the shared default one
    es = connection.current_es_client().options(request_timeout=5)
    if es.ping():
        return True, "es0 connection check succedded!"
    return False, "es0 connection check failed!"


def _updates_state_for(
    redis_client: Any, stream_name: str, index_name: str
) -> dict[str, Any]:
    """Build the reported processing state of the update daemon for a stream.

    Missing values are reported as ``None``, and the age of the last message
    read is computed from the timestamp embedded in its stream ID, relative to
    the current time (so that it keeps growing if the daemon stopped).

    :param redis_client: the Redis client
    :param stream_name: the name of the Redis stream
    :param index_name: the name of the index (the alias)
    :return: a dict suitable for JSON serialization
    """
    state = get_updates_state(redis_client, stream_name, index_name)
    last_read_id = state["last_read_id"] if state is not None else None
    pending_events = state["pending_events"] if state is not None else None
    timestamp_ms = timestamp_ms_from_stream_id(last_read_id) if last_read_id else None
    age_seconds = None
    if timestamp_ms is not None:
        # a small clock skew must not produce a negative age
        age_seconds = round(max(0.0, time.time() - timestamp_ms / 1000), 3)
    return {
        "index": index_name,
        "stream": stream_name,
        "last_read_id": last_read_id,
        "last_message_timestamp_ms": timestamp_ms,
        "last_message_age_seconds": age_seconds,
        "pending_events": pending_events,
    }


def test_updates_state():
    """Report the processing state of the update daemon.

    This is informational only, it never makes the application unhealthy: a
    slow or stopped update daemon must not take the search API out of
    rotation. A daemon that stopped shows up as a growing
    ``last_message_age_seconds``.
    """
    logger.debug("health: reporting update daemon state")
    try:
        config = get_config()
        # small socket timeout as it is only informational
        # (don't clutter health check with long waits)
        redis_client = connection.get_redis_client(
            socket_connect_timeout=5, socket_timeout=5
        )
        streams = [
            _updates_state_for(redis_client, index_config.redis_stream_name, index_name)
            for index_name, index_config in config.indices.items()
            if index_config.redis_stream_name is not None
        ]
    except Exception:
        # never fail: this check is informational
        logger.warning("health: could not read the update daemon state", exc_info=True)
        return True, {"streams": [], "error": "update daemon state unavailable"}
    # Note that the check result is cached by py-healthcheck (27s by default):
    # the age is therefore the one at capture time
    return True, {"streams": streams}


health.add_check(test_connect_redis)
health.add_check(test_connect_es)
health.add_check(test_updates_state)
