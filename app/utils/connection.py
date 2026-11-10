import os
from typing import cast

import elasticsearch
from elasticsearch_dsl.connections import connections
from redis import Redis

from app.config import settings
from app.search_client import create_client

# PID of the process that created the client, and the options it was created with
_client_pid: int | None = None
_client_kwargs: dict = {}


def get_es_client(**kwargs):
    """Create the client of the search engine and make it the default one.

    Each call creates a new client, so callers can ask for their own options
    (timeouts, ...) without inheriting the ones of a previous caller.
    """
    global _client_pid, _client_kwargs
    client = create_client(settings.search_engine, settings.elasticsearch_url, **kwargs)
    connections.add_connection("default", client)
    _client_pid = os.getpid()
    _client_kwargs = kwargs
    return client


def current_es_client() -> elasticsearch.Elasticsearch:
    """Return the default client of the search engine.

    For OpenSearch this is an adapter with the same interface.
    """
    if _client_pid is not None and _client_pid != os.getpid():
        # a forked worker must not reuse the connections of its parent
        get_es_client(**_client_kwargs)
    return cast(elasticsearch.Elasticsearch, connections.get_connection())


def get_redis_client(**kwargs) -> Redis:
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
        **kwargs,
    )
