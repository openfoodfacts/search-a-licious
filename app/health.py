"""This module contains the health check functions for the application.

It is based upon the `py-healthcheck`_ library.

.. _py-healthcheck: https://github.com/klen/py-healthcheck
"""

from healthcheck import HealthCheck

from app.search import _get_es_query_builder_cached, _get_result_processor_cached
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
    es = connection.get_es_client(timeout=5)
    if es.ping():
        return True, "es0 connection check succedded!"
    return False, "es0 connection check failed!"


def get_cache_stats():
    """Return metrics on internal caches."""
    return True, {
        "es_query_builder_cache": _get_es_query_builder_cached.cache_info()._asdict(),
        "result_processor_cache": _get_result_processor_cached.cache_info()._asdict(),
    }


health.add_check(test_connect_redis)
health.add_check(test_connect_es)
health.add_check(get_cache_stats)
