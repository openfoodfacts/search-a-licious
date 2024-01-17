from elasticsearch_dsl.connections import connections
from redis import Redis

from app.config import settings


def get_es_client(**kwargs):
    return connections.create_connection(
        hosts=[settings.elasticsearch_url],
        **kwargs,
    )


def get_redis_client() -> Redis:
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
    )
