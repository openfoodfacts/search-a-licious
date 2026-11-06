import os
from unittest import mock

import elasticsearch
import pytest
import yaml
from elasticsearch_dsl import Index, Search
from elasticsearch_dsl.connections import connections

from app import search_client
from app.config import Config, settings
from app.search_client import SearchClient
from app.utils import connection

from .conftest import DEFAULT_CONFIG_PATH


@pytest.fixture
def native():
    return mock.MagicMock()


@pytest.fixture
def client(native):
    return SearchClient(native)


@pytest.fixture
def restore_connections():
    """Restore the default connection and the module state after a test"""
    previous = connections._conns.get("default")
    state = (connection._client_pid, connection._client_kwargs)
    yield
    connections._conns.pop("default", None)
    if previous is not None:
        connections.add_connection("default", previous)
    connection._client_pid, connection._client_kwargs = state


def test_elasticsearch_is_the_default_engine():
    assert settings.search_engine == "elasticsearch"


def test_elasticsearch_client_is_native_and_not_wrapped():
    client = search_client.create_client("elasticsearch", "http://es:9200")
    assert isinstance(client, elasticsearch.Elasticsearch)


def test_unknown_engine_is_rejected():
    with pytest.raises(ValueError, match="Unsupported search engine"):
        search_client.create_client("openseach", "http://es:9200")


def test_search_response_has_a_body_for_the_dsl(client, native):
    native.search.return_value = {"hits": {"hits": []}}
    response = client.search(index="a", body={"query": {}})
    assert response.body == {"hits": {"hits": []}}
    native.search.assert_called_once_with(index="a", body={"query": {}})


def test_unknown_operations_are_delegated(client, native):
    assert client.cat is native.cat
    client.cluster.health()
    native.cluster.health.assert_called_once_with()


def test_exists_keeps_document_semantics(client, native):
    """`exists(index, id)` checks a document, it is not redefined"""
    client.exists(index="a", id="1")
    native.exists.assert_called_once_with(index="a", id="1")


def test_create_index_arguments_go_to_the_body(client, native):
    client.indices.create(
        index="a", mappings={"m": 1}, settings={"s": 1}, timeout="3600s"
    )
    native.indices.create.assert_called_once_with(
        index="a", body={"mappings": {"m": 1}, "settings": {"s": 1}}, timeout="3600s"
    )


def test_create_index_keeps_the_dsl_body(client, native):
    client.indices.create(index="a", body={"mappings": {"m": 1}})
    native.indices.create.assert_called_once_with(
        index="a", body={"mappings": {"m": 1}}
    )


def test_update_aliases_actions_go_to_the_body(client, native):
    actions = [{"add": {"index": "a", "alias": "b"}}]
    client.indices.update_aliases(actions=actions)
    native.indices.update_aliases.assert_called_once_with(body={"actions": actions})


def test_analyze_arguments_go_to_the_body(client, native):
    client.indices.analyze(index="a", text="Milk", analyzer="std")
    native.indices.analyze.assert_called_once_with(
        index="a", body={"text": "Milk", "analyzer": "std"}
    )


def test_other_indices_operations_are_delegated(client, native):
    client.indices.get_alias(index="off-*")
    native.indices.get_alias.assert_called_once_with(index="off-*")


def test_put_script_wraps_the_script(client, native):
    client.put_script(id="s", script={"lang": "painless"}, context="score")
    native.put_script.assert_called_once_with(
        id="s", body={"script": {"lang": "painless"}}, context="score"
    )


def test_options_gives_request_timeout_to_calls_without_altering_the_client(
    client, native
):
    derived = client.options(request_timeout=5)
    derived.ping()
    native.ping.assert_called_once_with(request_timeout=5)
    client.ping()
    assert native.ping.call_args_list[-1] == mock.call()


def test_synonyms_sets_are_not_available(client):
    with pytest.raises(NotImplementedError, match="synonyms_strategy: none"):
        client.synonyms


def test_request_timeout_is_translated_for_opensearch():
    # opensearch-py silently ignores `request_timeout` as a client argument
    assert search_client._opensearch_kwargs(
        {"request_timeout": 120, "retry_on_timeout": True}
    ) == {"timeout": 120, "retry_on_timeout": True}


def test_opensearch_client_uses_the_requested_timeout():
    pytest.importorskip("opensearchpy")
    client = search_client.create_client(
        "opensearch", "http://localhost:9200", request_timeout=120
    )
    assert isinstance(client, SearchClient)
    assert client.client.transport.connection_pool.connections[0].timeout == 120


@pytest.mark.parametrize(
    "client_class,helper",
    [(SearchClient, "os_helpers"), (mock.MagicMock, "es_helpers")],
)
def test_bulk_helpers_follow_the_engine(client_class, helper):
    client = (
        client_class(mock.MagicMock())
        if client_class is SearchClient
        else client_class()
    )
    with mock.patch.object(search_client, helper) as helpers:
        search_client.bulk(client, [])
        search_client.parallel_bulk(client, [])
    assert helpers.bulk.called and helpers.parallel_bulk.called


def test_error_body():
    assert search_client.error_body(mock.Mock(body={"a": 1})) == {"a": 1}
    assert search_client.error_body(mock.Mock(body=None, info={"b": 2})) == {"b": 2}


def test_clients_get_their_own_options(restore_connections):
    """A caller asking for another timeout must not get the first client"""
    short = connection.get_es_client(request_timeout=120)
    long = connection.get_es_client(request_timeout=600)
    assert short is not long
    assert connection.current_es_client() is long
    assert long._request_timeout == 600


def test_client_is_recreated_after_a_fork(restore_connections):
    first = connection.get_es_client(request_timeout=120)
    assert connection.current_es_client() is first
    with mock.patch.object(os, "getpid", return_value=os.getpid() + 1):
        second = connection.current_es_client()
    assert second is not first
    assert second._request_timeout == 120


def _config_with(strategy: str) -> dict:
    with DEFAULT_CONFIG_PATH.open() as f:
        data = yaml.safe_load(f)
    data["indices"]["off"]["synonyms_strategy"] = strategy
    return data


@pytest.mark.parametrize("strategy", ["index", "none"])
def test_elasticsearch_supports_every_synonyms_strategy(strategy):
    Config(**_config_with(strategy))


def test_opensearch_supports_only_no_synonyms(monkeypatch):
    monkeypatch.setattr(settings, "search_engine", "opensearch")
    Config(**_config_with("none"))
    with pytest.raises(ValueError, match="not supported with SEARCH_ENGINE=opensearch"):
        Config(**_config_with("index"))


def test_dsl_search_and_index_work_with_the_adapter(client, native):
    """`Search.execute()` and `Index.create()` are used as is with OpenSearch"""
    native.search.return_value = {
        "took": 3,
        "timed_out": False,
        "hits": {
            "total": {"value": 1, "relation": "eq"},
            "hits": [{"_id": "1", "_score": 1.0, "_source": {"code": "1"}}],
        },
    }
    response = Search(using=client, index="off").query("match", code="1").execute()
    assert response.hits.total["value"] == 1
    assert response.hits[0].to_dict() == {"code": "1"}
    assert response.hits[0].meta.score == 1.0

    Index("off", using=client).settings(number_of_shards=1).create(timeout="3600s")
    native.indices.create.assert_called_once_with(
        index="off", body={"settings": {"number_of_shards": 1}}, timeout="3600s"
    )


def test_index_translates_document_to_body(client, native):
    client.index(index="idx", id="1", document={"a": 1})
    native.index.assert_called_once_with(index="idx", id="1", body={"a": 1})


def test_index_keeps_body(client, native):
    client.index(index="idx", id="1", body={"a": 1})
    native.index.assert_called_once_with(index="idx", id="1", body={"a": 1})


def test_search_moves_query_to_body(client, native):
    native.search.return_value = {"hits": {}}
    client.search(index="idx", query={"match_all": {}})
    native.search.assert_called_once_with(
        index="idx", body={"query": {"match_all": {}}}
    )


def test_search_keeps_body(client, native):
    native.search.return_value = {"hits": {}}
    client.search(index="idx", body={"query": {"match_all": {}}})
    native.search.assert_called_once_with(
        index="idx", body={"query": {"match_all": {}}}
    )


def test_clone_translates_source(client, native):
    client.indices.clone(source="a", target="b", wait_for_completion=True)
    native.indices.clone.assert_called_once_with(
        index="a", target="b", wait_for_completion=True
    )
