import os

from elasticsearch_dsl.connections import connections
from redis import Redis

from app.config import settings
from app.search_client import SearchClient

_search_client = None
# PID of the process that created the client
_search_client_pid: int | None = None


def get_es_client(**kwargs):
    global _search_client, _search_client_pid
    # a forked worker must not reuse the connection pool of its parent
    if _search_client is None or _search_client_pid != os.getpid():
        _search_client = SearchClient(**kwargs)
        _search_client_pid = os.getpid()
        # Also setup elasticsearch_dsl connection for index creation/mapping if needed,
        # but we bypass it for actual execution
        connections.create_connection(
            hosts=[settings.elasticsearch_url],
            **kwargs,
        )
    return _search_client


def current_es_client():
    """Return ElasticSearch default connection"""
    global _search_client
    if _search_client is None:
        return get_es_client()
    return _search_client


def get_redis_client(**kwargs) -> Redis:
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
        **kwargs,
    )
