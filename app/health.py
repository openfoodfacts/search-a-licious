"""This module contains the health check functions for the application.

It is based upon the `py-healthcheck`_ library.

.. _py-healthcheck: https://github.com/klen/py-healthcheck
"""

from healthcheck import HealthCheck

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


health.add_check(test_connect_redis)
health.add_check(test_connect_es)
