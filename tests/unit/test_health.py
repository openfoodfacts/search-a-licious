from unittest import mock

import pytest
from elasticsearch_dsl.connections import connections

from app import health
from app.config import Config


@pytest.fixture
def default_client():
    """Register a mock "default" client and restore the previous state after."""
    previous = connections._conns.get("default")
    client = mock.MagicMock()
    connections.add_connection("default", client)
    yield client
    connections.remove_connection("default")
    if previous is not None:
        connections.add_connection("default", previous)


def test_connect_es_does_not_replace_default_client(default_client):
    default_client.options.return_value.ping.return_value = True

    ok, _ = health.test_connect_es()

    assert ok
    # the shared client is still the registered one
    assert connections.get_connection() is default_client
    # and the ping used a short timeout, without touching the shared client
    default_client.options.assert_called_once_with(request_timeout=5)


def test_connect_es_reports_failure(default_client):
    default_client.options.return_value.ping.return_value = False

    ok, _ = health.test_connect_es()

    assert not ok


def _patched_redis(state: dict | None):
    """Patch the Redis client of the health module with a mock returning state"""
    redis_client = mock.MagicMock()
    redis_client.hgetall.return_value = state or {}
    return mock.patch.object(
        health.connection, "get_redis_client", return_value=redis_client
    )


def test_updates_state_is_always_healthy_and_reports_lag(
    default_global_config: Config,
):
    """The daemon state is informational: it never makes the app unhealthy"""
    state = {"last_read_id": "1629878400000-0", "pending_events": "4"}
    now_ms = 1629878400000 + 12500
    with (
        _patched_redis(state),
        mock.patch.object(health.time, "time", return_value=now_ms / 1000),
    ):
        ok, details = health.test_updates_state()

    assert ok
    assert details == {
        "streams": [
            {
                "index": "off",
                "stream": "product_updates_off",
                "last_read_id": "1629878400000-0",
                "last_message_timestamp_ms": 1629878400000,
                "last_message_age_seconds": 12.5,
                "pending_events": 4,
            }
        ]
    }


def test_updates_state_missing_is_reported_as_null(
    default_global_config: Config,
):
    """A daemon that never recorded its state is reported with null values"""
    with _patched_redis(None):
        ok, details = health.test_updates_state()

    assert ok
    assert details["streams"] == [
        {
            "index": "off",
            "stream": "product_updates_off",
            "last_read_id": None,
            "last_message_timestamp_ms": None,
            "last_message_age_seconds": None,
            "pending_events": None,
        }
    ]


def test_updates_state_age_never_negative(default_global_config: Config):
    """A small clock skew must not produce a negative age"""
    state = {"last_read_id": "1629878400000-0", "pending_events": "0"}
    # the "current" time is before the timestamp of the message
    with (
        _patched_redis(state),
        mock.patch.object(health.time, "time", return_value=1629878399.0),
    ):
        ok, details = health.test_updates_state()

    assert ok
    assert details["streams"][0]["last_message_age_seconds"] == 0


def test_updates_state_failure_is_not_fatal(default_global_config: Config):
    """A Redis failure must not make the health check fail"""
    with mock.patch.object(
        health.connection,
        "get_redis_client",
        side_effect=RuntimeError("redis is down"),
    ):
        ok, details = health.test_updates_state()

    assert ok
    assert details["streams"] == []
    assert "redis is down" in details["error"]
