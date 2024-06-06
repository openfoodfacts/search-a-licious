from healthcheck import HealthCheck

from app.utils import connection, get_logger

logger = get_logger(__name__)

health = HealthCheck()


def test_connect_redis():
    logger.debug("health: testing redis connection")
    client = connection.get_redis_client()
    if client.ping():
        return True, "Redis connection check succedded!"
    return False, "Redis connection check failed!"


def test_connect_es():
    logger.debug("health: testing es connection")
    es = connection.get_es_client()
    if es.ping():
        return True, "es0 connection check succedded!"
    return False, "es0 connection check failed!"


health.add_check(test_connect_redis)
health.add_check(test_connect_es)
