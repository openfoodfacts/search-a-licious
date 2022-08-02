import os
from elasticsearch_dsl.connections import connections


def get_connection():
    return connections.create_connection(hosts=[os.getenv('ELASTICSEARCH_URL', '127.0.0.1:9200')])