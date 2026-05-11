import os
from typing import Any, Dict, List, Optional

import elasticsearch
import opensearchpy
from elasticsearch.helpers import bulk as es_bulk
from elasticsearch.helpers import parallel_bulk as es_parallel_bulk
from opensearchpy.helpers import bulk as os_bulk
from opensearchpy.helpers import parallel_bulk as os_parallel_bulk

from app.config import settings

_engine = os.getenv("SEARCH_ENGINE", "elasticsearch").lower()

if _engine == "opensearch":
    from opensearchpy.exceptions import NotFoundError
    from opensearchpy.exceptions import TransportError as ApiError
else:
    from elasticsearch import NotFoundError
    from elasticsearch import ApiError


class SearchClient:
    """Abstraction layer for Search Engine operations to support both Elasticsearch and OpenSearch."""

    def __init__(self, **kwargs):
        self.engine = _engine
        if self.engine == "opensearch":
            # For local testing with opensearch without SSL/auth configured fully,
            # or when configured via env variables.
            self.client = opensearchpy.OpenSearch(
                hosts=[settings.elasticsearch_url],
                use_ssl=False,
                verify_certs=False,
                ssl_show_warn=False,
                **kwargs,
            )
        else:
            self.client = elasticsearch.Elasticsearch(
                hosts=[settings.elasticsearch_url],
                **kwargs,
            )

    @property
    def indices(self):
        """Exposes the underlying indices client for both ES and OS."""
        return self.client.indices

    @property
    def cluster(self):
        """Exposes the underlying cluster client."""
        return self.client.cluster

    def delete_script(self, id: str, **kwargs) -> Dict[str, Any]:
        """Delete a script."""
        return dict(self.client.delete_script(id=id, **kwargs))

    def put_script(self, id: str, script: Dict[str, Any], context: str = None, **kwargs) -> Dict[str, Any]:
        """Store a script."""
        if self.engine == "elasticsearch":
            return dict(self.client.put_script(id=id, script=script, context=context, **kwargs))
        else:
            return dict(self.client.put_script(id=id, body={"script": script}, context=context, **kwargs))

    def search(self, index: str, body: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Perform a search query."""
        if self.engine == "elasticsearch":
            # elasticsearch 8+ doesn't use `body` for search natively in all places,
            # but the dict format is accepted if unpacked, or it might just take body if compatibility is ok.
            # Actually, `client.search` in v8 takes kwargs natively. But providing it as `body` works if
            # it's unpacked or using the body parameter depending on the exact version.
            # However, a safe way is to pass body as kwargs.
            # Wait, Elasticsearch-py 8.x supports `**body` for search or `body=` depending on exact version.
            # `elasticsearch-py` v8: `client.search(index=index, body=body, **kwargs)` might raise an error.
            # It's safer to unpack body. Wait, `elasticsearch-dsl` uses `client.search(index=index, body=...)` ?
            # Let's just pass `**body` and `**kwargs`.
            return dict(self.client.search(index=index, **body, **kwargs))
        else:
            return dict(self.client.search(index=index, body=body, **kwargs))

    def index(self, index: str, body: Dict[str, Any], id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Index a document."""
        if self.engine == "elasticsearch":
            return dict(self.client.index(index=index, document=body, id=id, **kwargs))
        else:
            return dict(self.client.index(index=index, body=body, id=id, **kwargs))

    def delete(self, index: str, id: str, **kwargs) -> Dict[str, Any]:
        """Delete a document."""
        return dict(self.client.delete(index=index, id=id, **kwargs))

    def bulk(self, actions: Any, raise_on_error: bool = False, **kwargs) -> tuple:
        """Perform a bulk operation."""
        if self.engine == "elasticsearch":
            return es_bulk(self.client, actions, raise_on_error=raise_on_error, **kwargs)
        else:
            return os_bulk(self.client, actions, raise_on_error=raise_on_error, **kwargs)

    def parallel_bulk(self, actions: Any, **kwargs):
        """Perform a parallel bulk operation."""
        if self.engine == "elasticsearch":
            return es_parallel_bulk(self.client, actions, **kwargs)
        else:
            return os_parallel_bulk(self.client, actions, **kwargs)

    def update_aliases(self, actions: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """Update aliases."""
        if self.engine == "elasticsearch":
            return dict(self.client.indices.update_aliases(actions=actions, **kwargs))
        else:
            return dict(self.client.indices.update_aliases(body={"actions": actions}, **kwargs))

    def get_alias(self, name: str, **kwargs) -> Dict[str, Any]:
        """Get alias mapping."""
        return dict(self.client.indices.get_alias(name=name, **kwargs))

    def delete_index(self, index: str, **kwargs) -> Dict[str, Any]:
        """Delete an index."""
        return dict(self.client.indices.delete(index=index, **kwargs))

    def create_index(self, index: str, body: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Create an index."""
        if self.engine == "elasticsearch":
            mappings = body.get("mappings")
            settings_ = body.get("settings")
            return dict(self.client.indices.create(index=index, mappings=mappings, settings=settings_, **kwargs))
        else:
            return dict(self.client.indices.create(index=index, body=body, **kwargs))

    def refresh_index(self, index: str, **kwargs) -> Dict[str, Any]:
        """Refresh an index."""
        return dict(self.client.indices.refresh(index=index, **kwargs))

    def analyze(self, index: str, body: Dict[str, Any] = None, text: str = None, analyzer: Any = None, **kwargs) -> Dict[str, Any]:
        """Analyze text."""
        if self.engine == "elasticsearch":
            # For elasticsearch-py 8.x, indices.analyze kwargs are used
            req_kwargs = kwargs.copy()
            if text is not None:
                req_kwargs["text"] = text
            if analyzer is not None:
                req_kwargs["analyzer"] = analyzer
            if body:
                req_kwargs.update(body)
            return dict(self.client.indices.analyze(index=index, **req_kwargs))
        else:
            # opensearch py might still use body or text/analyzer kwargs
            req_body = body or {}
            if text is not None:
                req_body["text"] = text
            if analyzer is not None:
                req_body["analyzer"] = analyzer
            return dict(self.client.indices.analyze(index=index, body=req_body, **kwargs))

    def exists(self, index: str, **kwargs) -> bool:
        """Check if an index exists."""
        return bool(self.client.indices.exists(index=index, **kwargs))

    def reload_search_analyzers(self, index: str, **kwargs) -> Dict[str, Any]:
        """Reload search analyzers."""
        return dict(self.client.indices.reload_search_analyzers(index=index, **kwargs))

    def clear_cache(self, index: str, **kwargs) -> Dict[str, Any]:
        """Clear cache."""
        return dict(self.client.indices.clear_cache(index=index, **kwargs))
