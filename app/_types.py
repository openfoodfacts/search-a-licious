from typing import Any, Optional

import elasticsearch_dsl.query
import luqum.tree
from pydantic import BaseModel, ConfigDict

#: A precise expectation of what mappings looks like in json.
#: (dict where keys are always of type `str`).
JSONType = dict[str, Any]


class FacetItem(BaseModel):
    """Describes an entry of a facet"""

    key: str
    name: str
    count: int
    """The number of elements for this value"""

    selected: bool
    """Whether this value is selected"""


class FacetInfo(BaseModel):
    """Search result for a facet"""

    name: str
    """The display name of the facet"""

    items: list[FacetItem]
    """Items in the facets"""

    count_error_margin: int | None = None


FacetsInfos = dict[str, FacetInfo]
"""Information about facets for a search result"""

FacetsFilters = dict[str, list[str]]
"""Data about selected filters for each facet: facet name -> list of values"""


class SearchResponseDebug(BaseModel):
    query: JSONType


class SearchResponseError(BaseModel):
    title: str
    description: str | None = None


class ErrorSearchResponse(BaseModel):
    debug: SearchResponseDebug
    errors: list[SearchResponseError]

    def is_success(self):
        return False


class SuccessSearchResponse(BaseModel):
    hits: list[JSONType]
    aggregations: JSONType | None = None
    facets: FacetsInfos | None = None
    page: int
    page_size: int
    page_count: int
    debug: SearchResponseDebug
    took: int
    timed_out: bool
    count: int
    is_count_exact: bool
    warnings: list[SearchResponseError] | None = None

    def is_success(self):
        return True


SearchResponse = ErrorSearchResponse | SuccessSearchResponse


class QueryAnalysis(BaseModel):
    """An object containing different information about the query."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    text_query: Optional[str] = None
    """The initial text query"""

    luqum_tree: Optional[luqum.tree.Item] = None
    """The luqum tree corresponding to the text query"""

    es_query: Optional[elasticsearch_dsl.query.Query] = None
    """The query as an elasticsearch_dsl object"""

    fulltext: Optional[str] = None
    """The full text part of the query"""

    filter_query: Optional[JSONType] = None
    """The filter part of the query"""

    facets_filters: Optional[FacetsFilters] = None
    """The filters corresponding to the facets:
    a facet name and a list of values"""

    def clone(self, **kwargs):
        new = QueryAnalysis(
            text_query=self.text_query,
            luqum_tree=self.luqum_tree,
            es_query=self.es_query,
            fulltext=self.fulltext,
            filter_query=self.filter_query,
            facets_filters=self.facets_filters,
        )
        for k, v in kwargs.items():
            setattr(new, k, v)
        return new

    def _dict_dump(self):
        """Dumps to a dict, use it only for tests"""
        return {
            "text_query": self.text_query,
            "luqum_tree": str(self.luqum_tree),
            "es_query": self.es_query.to_dict(),
            "fulltext": self.fulltext,
            "filter_query": self.filter_query,
            "facets_filters": self.facets_filters,
        }
