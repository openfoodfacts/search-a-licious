from unittest import mock

from elasticsearch_dsl.connections import connections

from app import health


def test_connect_es_does_not_replace_default_client():
    default_client = mock.MagicMock()
    connections.add_connection("default", default_client)
    try:
        default_client.options.return_value.ping.return_value = True

        ok, _ = health.test_connect_es()

        assert ok
        # the shared client is still the registered one
        assert connections.get_connection() is default_client
        # and the ping used a short timeout, without touching the shared client
        default_client.options.assert_called_once_with(request_timeout=5)
    finally:
        connections.remove_connection("default")


def test_connect_es_reports_failure():
    default_client = mock.MagicMock()
    connections.add_connection("default", default_client)
    try:
        default_client.options.return_value.ping.return_value = False

        ok, _ = health.test_connect_es()

        assert not ok
    finally:
        connections.remove_connection("default")
