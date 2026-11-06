from unittest import mock

import elastic_transport
import elasticsearch
import pytest
from elasticsearch_dsl import Search

from app.postprocessing import BaseResultProcessor
from app.query import execute_query


def _es_bad_request():
    return elasticsearch.BadRequestError("bad", mock.Mock(status=400), {"e": 1})


def _es_api_error():
    return elasticsearch.ApiError("boom", mock.Mock(status=500), {"e": 1})


def _es_connection_error():
    return elastic_transport.ConnectionError("down")


def _os_bad_request():
    exceptions = pytest.importorskip("opensearchpy.exceptions")
    return exceptions.RequestError(400, "bad", {"e": 1})


def _os_api_error():
    exceptions = pytest.importorskip("opensearchpy.exceptions")
    return exceptions.TransportError(500, "boom", {"e": 1})


def _os_connection_error():
    exceptions = pytest.importorskip("opensearchpy.exceptions")
    return exceptions.ConnectionError("N/A", "down", Exception("down"))


@pytest.mark.parametrize(
    "make_error,title,status",
    [
        (_es_bad_request, "InvalidLuceneQueryError", 400),
        (_es_api_error, "es_api_error", None),
        (_es_connection_error, "es_connection_error", None),
        (_os_bad_request, "InvalidLuceneQueryError", 400),
        (_os_api_error, "es_api_error", None),
        # a connection error is a TransportError for OpenSearch,
        # it must not be reported as a generic API error
        (_os_connection_error, "es_connection_error", None),
    ],
)
def test_execute_query_reports_engine_errors(make_error, title, status):
    query = mock.Mock(spec=Search)
    query.to_dict.return_value = {}
    query.execute.side_effect = make_error()

    response = execute_query(query, mock.Mock(spec=BaseResultProcessor), 1, 10)

    assert [e.title for e in response.errors] == [title]
    assert response.errors[0].status == status
