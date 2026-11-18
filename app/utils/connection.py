import elasticsearch
from elasticsearch_dsl.connections import connections
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from app.config import settings

# Seconds a probe (like the health check) waits for Redis, to connect and
# then to get each answer
REDIS_PROBE_TIMEOUT = 5


def get_es_client(**kwargs):
    return connections.create_connection(
        hosts=[settings.elasticsearch_url],
        **kwargs,
    )


def get_api_es_client():
    """Create the default connection used by the API,
    with the timeout of the settings"""
    return get_es_client(request_timeout=settings.elasticsearch_request_timeout)


def current_es_client() -> elasticsearch.Elasticsearch:
    """Return ElasticSearch default connection"""
    return connections.get_connection()


def get_redis_client(**kwargs) -> Redis:
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
        **kwargs,
    )


def get_redis_probe_client() -> Redis:
    """Return a Redis client for a probe: it gives up quickly.

    It has a timeout to connect and to wait for each answer
    (`REDIS_PROBE_TIMEOUT`), and does not try again: by default redis-py tries
    a failed connection 10 more times, and has no timeout to wait for an
    answer.
    """
    return get_redis_client(
        socket_connect_timeout=REDIS_PROBE_TIMEOUT,
        socket_timeout=REDIS_PROBE_TIMEOUT,
        retry=Retry(NoBackoff(), 0),
    )
