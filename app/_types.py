from functools import cached_property
from typing import Annotated, Any, Optional, Tuple, cast, get_type_hints

import elasticsearch_dsl.query
import luqum.tree
from fastapi import Query
from pydantic import BaseModel, ConfigDict, model_validator

from . import config
from .utils import str_utils
from .validations import (
    check_all_charts_are_valid,
    check_all_facets_fields_are_agg,
    check_index_id_is_defined,
)

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

ChartsInfos = dict[str, JSONType]
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
    charts: ChartsInfos | None = None
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

            If you put a minus before the name, the results will be sorted by descending order.

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
    charts: Annotated[
        list[str] | None,
        Query(
            description="""Name of vega representations to return in the response.
            If None (default) no charts are returrned."""
        )
    ] = None
    sort_params: Annotated[
        JSONType | None,
        Query(
            description="""Additional parameters when using  a sort script in sort_by.
            If the sort script needs parameters, you can only be used the POST method.""",
        ),
    ] = None
    index_id: Annotated[
        str | None,
        INDEX_ID_QUERY_PARAM,
    ] = None

    @model_validator(mode="after")
    def validate_index_id(self):
        """
        Validate index_id is known, or use default index if not provided

        We call this validator as a model validator,
        because we want to be able to substitute the default None value,
        by the default index
        """
        config.check_config_is_defined()
        global_config = cast(config.Config, config.CONFIG)
        check_index_id_is_defined(self.index_id, global_config)
        self.index_id, _ = global_config.get_index_config(self.index_id)
        return self

    @property
    def valid_index_id(self) -> str:
        """Give a not None index_id

        This is mainly to avoid typing errors
        """
        if self.index_id is None:
            raise ValueError("`index_id` was not yet provided or computed")
        return self.index_id

    @model_validator(mode="after")
    def validate_q_or_sort_by(self):
        """We want at least one of q or sort_by before launching a request"""
        if self.q is None and self.sort_by is None:
            raise ValueError("`sort_by` must be provided when `q` is missing")
        return self

    @cached_property
    def index_config(self):
        """Get the index config once and for all"""
        global_config = cast(config.Config, config.CONFIG)
        _, index_config = global_config.get_index_config(self.index_id)
        return index_config

    @cached_property
    def uses_sort_script(self):
        """Does sort_by use a script?"""
        index_config = self.index_config
        _, sort_by = self.sign_sort_by
        return sort_by in index_config.scripts.keys()

    @model_validator(mode="after")
    def sort_by_is_field_or_script(self):
        """Verify sort_by is a valid field or script name"""
        index_config = self.index_config
        _, sort_by = self.sign_sort_by
        is_field = sort_by in index_config.fields
        # TODO: verify field type is compatible with sorting
        if not (self.sort_by is None or is_field or self.uses_sort_script):
            raise ValueError("`sort_by` must be a valid field name or script name")
        return self

    @model_validator(mode="after")
    def sort_by_scripts_needs_params(self):
        """If sort_by is a script,
        verify we got corresponding parameters in sort_params
        """
        if self.uses_sort_script:
            if self.sort_params is None:
                raise ValueError(
                    "`sort_params` must be provided when using a sort script"
                )
            if not isinstance(self.sort_params, dict):
                raise ValueError("`sort_params` must be a dict")
            # verifies keys are those expected
            request_keys = set(self.sort_params.keys())
            sort_sign, sort_by = self.sign_sort_by
            expected_keys = set(self.index_config.scripts[sort_by].params.keys())
            if request_keys != expected_keys:
                missing = expected_keys - request_keys
                missing_str = ("missing keys: " + ", ".join(missing)) if missing else ""
                new = request_keys - expected_keys
                new_str = ("unexpected keys: " + ", ".join(new)) if new else ""
                raise ValueError(
                    f"sort_params keys must match expected keys. {missing_str} {new_str}"
                )
        return self

    @model_validator(mode="after")
    def check_facets_are_valid(self):
        """Check that the facets names are valid."""
        errors = check_all_facets_fields_are_agg(self.index_id, self.facets)
        if errors:
            raise ValueError(errors)
        return self

    @model_validator(mode="after")
    def check_charts_are_valid(self):
        """Check that the graph names are valid."""
        errors = check_all_charts_are_valid(self.charts)
        if errors:
            raise ValueError(errors)
        return self

    @model_validator(mode="after")
    def check_max_results(self):
        """Check we don't ask too many results at once"""
        if self.page * self.page_size > 10_000:
            raise ValueError(
                f"Maximum number of returned results is 10 000 (here: page * page_size = {self.page * self.page_size})",
            )
        return self

    @property
    def langs_set(self):
        return set(self.langs)

    @property
    def sign_sort_by(self) -> Tuple[str_utils.BoolOperator, str | None]:
        return (
            ("+", None)
            if self.sort_by is None
            else str_utils.split_sort_by_sign(self.sort_by)
        )

    @property
    def main_lang(self):
        """Get the main lang of the query"""
        return self.langs[0] if self.langs else "en"


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
    charts = _annotation_new_type(str, SEARCH_PARAMS_ANN["charts"])
    index_id = SEARCH_PARAMS_ANN["index_id"]
