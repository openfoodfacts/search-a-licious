from __future__ import annotations

import os

from elasticsearch_dsl.connections import connections


def get_connection(**kwargs):
    return connections.create_connection(
        hosts=[os.getenv('ELASTICSEARCH_URL', '127.0.0.1:9200')], **kwargs,
    )
