from elasticsearch_dsl.connections import connections

from app.config import settings


def get_connection(**kwargs):
    return connections.create_connection(
        hosts=[settings.elasticsearch_url],
        **kwargs,
    )
