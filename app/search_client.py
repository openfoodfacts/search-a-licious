"""Support for running against OpenSearch instead of Elasticsearch.

Elasticsearch is the default engine and is used as is: nothing in this module
wraps the Elasticsearch client.

OpenSearch is opt-in (`SEARCH_ENGINE=opensearch`). Its client is wrapped by
:class:`SearchClient`, which gives it the call style of `elasticsearch-py` 8
used in the application, so the Elasticsearch DSL (`Search`, `Index`) keeps
working. Everything the wrapper does not define is delegated to the native
OpenSearch client.
"""

import functools
from typing import Any

import elastic_transport
import elasticsearch
from elasticsearch import helpers as es_helpers

try:  # OpenSearch support is optional
    import opensearchpy
    from opensearchpy import exceptions as os_exceptions
    from opensearchpy import helpers as os_helpers
except ImportError:  # pragma: no cover
    opensearchpy = None  # type: ignore[assignment]
    os_exceptions = None  # type: ignore[assignment]
    os_helpers = None  # type: ignore[assignment]

SUPPORTED_ENGINES = ("elasticsearch", "opensearch")


def _exceptions(es_exc: type[Exception], os_name: str) -> Any:
    """Exceptions to catch, whatever the engine (usable in `except`)"""
    if os_exceptions is None:
        return es_exc
    return (es_exc, getattr(os_exceptions, os_name))


# Exceptions to use in `except` clauses.
# Keep the order `BadRequestError`, `ConnectionError_`, then `ApiError`:
# for OpenSearch, all of them derive from `TransportError`.
ApiError = _exceptions(elasticsearch.ApiError, "TransportError")
BadRequestError = _exceptions(elasticsearch.BadRequestError, "RequestError")
NotFoundError = _exceptions(elasticsearch.NotFoundError, "NotFoundError")
ConnectionError_ = _exceptions(elastic_transport.ConnectionError, "ConnectionError")


def error_body(error: Exception) -> Any:
    """Body of an error response (`body` for Elasticsearch, `info` for OpenSearch)"""
    return getattr(error, "body", None) or getattr(error, "info", None)


class _Body(dict):
    """A search response, with the `body` attribute of the Elasticsearch client
    responses, as expected by the Elasticsearch DSL."""

    @property
    def body(self) -> dict:
        return dict(self)


class _IndicesAdapter:
    """`client.indices` with Elasticsearch 8 style arguments"""

    def __init__(self, indices):
        self._indices = indices

    def __getattr__(self, name: str):
        return getattr(self._indices, name)

    def create(self, index: str, body: dict | None = None, **kwargs):
        # Elasticsearch takes `mappings`, `settings` and `aliases` as arguments
        body = dict(body or {})
        for key in ("mappings", "settings", "aliases"):
            if key in kwargs:
                body[key] = kwargs.pop(key)
        return self._indices.create(index=index, body=body, **kwargs)

    def clone(self, source: str, target: str, **kwargs):
        # Elasticsearch calls the source index `source`
        return self._indices.clone(index=source, target=target, **kwargs)

    def update_aliases(self, actions: list[dict], **kwargs):
        return self._indices.update_aliases(body={"actions": actions}, **kwargs)

    def analyze(
        self,
        index: str | None = None,
        body: dict | None = None,
        **kwargs,
    ):
        # Elasticsearch takes `text`, `analyzer`, ... as arguments
        body = dict(body or {})
        for key in ("text", "analyzer", "tokenizer", "filter", "char_filter", "field"):
            if key in kwargs:
                body[key] = kwargs.pop(key)
        return self._indices.analyze(index=index, body=body, **kwargs)


class _Options:
    """Per-request options, as returned by `Elasticsearch.options()`"""

    def __init__(self, client: "SearchClient", options: dict):
        self._client = client
        self._options = options

    def __getattr__(self, name: str):
        attr = getattr(self._client, name)
        if callable(attr):
            return functools.partial(attr, **self._options)
        return attr


class SearchClient:
    """Adapter that makes an OpenSearch client usable like an Elasticsearch 8 one.

    Only the methods whose arguments differ are defined here,
    anything else is delegated to the native client.
    """

    engine = "opensearch"

    def __init__(self, client):
        self.client = client
        self.indices = _IndicesAdapter(client.indices)

    def __getattr__(self, name: str):
        # only called for what is not defined on the adapter
        return getattr(self.client, name)

    def options(self, request_timeout: float | None = None, **kwargs) -> _Options:
        """Derive a client with other options, without altering this one"""
        options = dict(kwargs)
        if request_timeout is not None:
            options["request_timeout"] = request_timeout
        return _Options(self, options)

    def index(self, index: str, document: dict | None = None, **kwargs):
        # Elasticsearch takes the document as `document`
        if document is not None:
            kwargs["body"] = document
        return self.client.index(index=index, **kwargs)

    def search(self, *args, **kwargs) -> _Body:
        # Elasticsearch takes `query` ... as arguments, OpenSearch in the body
        body = dict(kwargs.pop("body", None) or {})
        for key in ("query", "aggs", "aggregations"):
            if key in kwargs:
                body[key] = kwargs.pop(key)
        if body:
            kwargs["body"] = body
        return _Body(self.client.search(*args, **kwargs))

    def put_script(self, id: str, script: dict, context: str | None = None, **kwargs):
        return self.client.put_script(
            id=id, body={"script": script}, context=context, **kwargs
        )

    @property
    def synonyms(self):
        raise NotImplementedError(
            "The synonyms sets API is not available on OpenSearch, "
            "use `synonyms_strategy: none`"
        )


def _opensearch_kwargs(kwargs: dict) -> dict:
    """Translate Elasticsearch client arguments to OpenSearch ones.

    OpenSearch ignores `request_timeout` as a client argument, it is `timeout`.
    """
    kwargs = dict(kwargs)
    if "request_timeout" in kwargs:
        kwargs["timeout"] = kwargs.pop("request_timeout")
    return kwargs


def create_client(engine: str, url: str, **kwargs):
    """Create the client for an engine. Elasticsearch gets a native client."""
    if engine == "elasticsearch":
        return elasticsearch.Elasticsearch(hosts=[url], **kwargs)
    if engine == "opensearch":
        if opensearchpy is None:
            raise RuntimeError(
                "SEARCH_ENGINE=opensearch needs the opensearch-py package"
            )
        return SearchClient(
            opensearchpy.OpenSearch(hosts=[url], **_opensearch_kwargs(kwargs))
        )
    raise ValueError(
        f"Unsupported search engine '{engine}', expected one of {SUPPORTED_ENGINES}"
    )


def bulk(client, *args, **kwargs):
    """`helpers.bulk` for the engine of the client"""
    if isinstance(client, SearchClient):
        return os_helpers.bulk(client.client, *args, **kwargs)
    return es_helpers.bulk(client, *args, **kwargs)


def parallel_bulk(client, *args, **kwargs):
    """`helpers.parallel_bulk` for the engine of the client"""
    if isinstance(client, SearchClient):
        return os_helpers.parallel_bulk(client.client, *args, **kwargs)
    return es_helpers.parallel_bulk(client, *args, **kwargs)
