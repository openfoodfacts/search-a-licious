from typing import Annotated, Any, Optional, cast, get_type_hints

import elasticsearch_dsl.query
import luqum.tree
from fastapi import Query
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from . import config
from .validations import check_all_facets_fields_are_agg, check_index_id_is_defined

#: A precise expectation of what mappings looks like in json.
#: (dict where keys are always of type `str`).
JSONType = dict[str, Any]


class FacetItem(BaseModel):
    """Describes an entry of a facet"""

    key: str
    name: str
    count: Optional[int]
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


INDEX_ID_QUERY_PARAM = Query(
    description="""Index ID to use for the search, if not provided, the default index is used.
        If there is only one index, this parameter is not needed."""
)


class SearchParameters(BaseModel):
    """Common parameters for search"""

    q: Annotated[
        str | None,
        Query(
            description="""The search query, it supports Lucene search query
syntax (https://lucene.apache.org/core/3_6_0/queryparsersyntax.html). Words
that are not recognized by the lucene query parser are searched as full text
search.

Example: `categories_tags:"en:beverages" strawberry brands:"casino"` query use a
filter clause for categories and brands and look for "strawberry" in multiple
fields.

The query is optional, but `sort_by` value must then be provided."""
        ),
    ] = None

    langs: Annotated[
        list[str],
        Query(
            description="""List of languages we want to support during search.
This list should include the user expected language, and additional languages (such
as english for example).

This is currently used for language-specific subfields to choose in which
subfields we're searching in.

If not provided, `['en']` is used."""
        ),
    ] = ["en"]
    page_size: Annotated[
        int, Query(description="Number of results to return per page.")
    ] = 10
    page: Annotated[int, Query(ge=1, description="Page to request, starts at 1.")] = 1
    fields: Annotated[
        list[str] | None,
        Query(
            description="List of fields to include in the response. All other fields will be ignored."
        ),
    ] = None
    sort_by: Annotated[
        str | None,
        Query(
            description="""Field name to use to sort results, the field should exist
            and be sortable. If it is not provided, results are sorted by descending relevance score.

            If the field name match a known script (defined in your configuration),
            it will be use for sorting.

            In this case you also need to provide additional parameters corresponding to your script parameters.
            If a script needs parameters, you can only use the POST method.

            Beware that this may have a big impact on performance.
            """
        ),
    ] = None
    facets: Annotated[
        list[str] | None,
        Query(
            description="""Name of facets to return in the response as a comma-separated value.
            If None (default) no facets are returned."""
        ),
    ] = None
    index_id: Annotated[
        str,
        INDEX_ID_QUERY_PARAM,
    ]

    @field_validator("index_id")
    @classmethod
    def validate_index_id(cls, index_id: str | None):
        config.check_config_is_defined()
        global_config = cast(config.Config, config.CONFIG)
        check_index_id_is_defined(index_id, global_config)
        index_id, index_config = global_config.get_index_config(index_id)
        return index_id

    @model_validator(mode="after")
    def validate_q_or_sort_by(self):
        if self.q is None and self.sort_by is None:
            raise ValueError("`sort_by` must be provided when `q` is missing")
        return self

    def get_index_config(self):
        global_config = cast(config.Config, config.CONFIG)
        _, index_config = global_config.get_index_config(self.index_id)
        return index_config

    @model_validator(mode="after")
    def check_facets_are_valid(self):
        """Check that the facets names are valid."""
        errors = check_all_facets_fields_are_agg(self.index_id, self.facets)
        if errors:
            raise ValueError(errors)
        return self

    @model_validator(mode="after")
    def check_max_results(self):
        if self.page * self.page_size > 10_000:
            raise ValueError(
                f"Maximum number of returned results is 10 000 (here: page * page_size = {self.page * self.page_size})",
            )
        return self

    @property
    def langs_set(self):
        return set(self.langs)


def _annotation_new_type(type_, annotation):
    """Use a new type for a given annotation"""
    return Annotated[type_, *annotation.__metadata__]


# types for search parameters for GET
SEARCH_PARAMS_ANN = get_type_hints(SearchParameters, include_extras=True)


class GetSearchParamsTypes:
    q = SEARCH_PARAMS_ANN["q"]
    langs = _annotation_new_type(str, SEARCH_PARAMS_ANN["langs"])
    page_size = SEARCH_PARAMS_ANN["page_size"]
    page = SEARCH_PARAMS_ANN["page"]
    fields = _annotation_new_type(str, SEARCH_PARAMS_ANN["fields"])
    sort_by = SEARCH_PARAMS_ANN["sort_by"]
    facets = _annotation_new_type(str, SEARCH_PARAMS_ANN["facets"])
    index_id = SEARCH_PARAMS_ANN["index_id"]
