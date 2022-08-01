from elasticsearch_dsl.connections import connections


def get_connection():
    return connections.create_connection(hosts=['localhost:9200'])