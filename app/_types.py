from enum import Enum, StrEnum
from functools import cached_property
from inspect import cleandoc as cd_
from typing import Annotated, Any, Literal, Optional, Tuple, Union, cast

import elasticsearch_dsl.query
import luqum.tree
from fastapi import Query
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from . import config
from .utils import str_utils
from .validations import (
    check_all_values_are_fields_agg,
    check_fields_are_numeric,
    check_index_id_is_defined,
)

#: A precise expectation of what mappings looks like in json.
#: (dict where keys are always of type `str`).
JSONType = dict[str, Any]


class DistributionChartType(BaseModel):
    """Describes an entry for a distribution chart"""

    chart_type: Literal["DistributionChartType"] = "DistributionChartType"
    field: str


class ScatterChartType(BaseModel):
    """Describes an entry for a scatter plot"""

    chart_type: Literal["ScatterChartType"] = "ScatterChartType"
    x: str
    y: str


ChartType = Union[DistributionChartType, ScatterChartType]


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
"""Information about charts for a search result"""

FacetsFilters = dict[str, list[str]]
"""Data about selected filters for each facet: facet name -> list of values"""


class DebugInfo(StrEnum):
    """Debug information to return in the API"""

    aggregations = "aggregations"
    lucene_query = "lucene_query"
    es_query = "es_query"


class SearchResponseDebug(BaseModel):
    lucene_query: str | None = None
    es_query: JSONType | None = None
    aggregations: JSONType | None = None


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
    debug: SearchResponseDebug | None = None
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

    facets_filters: Optional[FacetsFilters] = None
    """The filters corresponding to the facets:
    a facet name and a list of values"""

    def clone(self, **kwargs):
        new = QueryAnalysis(
            text_query=self.text_query,
            luqum_tree=self.luqum_tree,
            es_query=self.es_query,
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
            "facets_filters": self.facets_filters,
        }


class CommonParametersQuery:
    """Documentation and constraints for some common query parameters"""

    index_id = Query(
        description=cd_(
            """Index ID to use for the search, if not provided, the default index is used.
            If there is only one index, this parameter is not needed.
            """
        )
    )


class SearchParametersQuery(CommonParametersQuery):
    """Documentation and constraints for search parameters

    We put this in a class because we want to reuse the same description
    in SearchParameters and GetSearchParameters
    """

    q = Query(
        description=cd_(
            """The search query, it supports Lucene search query
            syntax (https://lucene.apache.org/core/3_6_0/queryparsersyntax.html). Words
            that are not recognized by the lucene query parser are searched as full text
            search.

            Example: `categories_tags:"en:beverages" strawberry brands:"casino"` query use a
            filter clause for categories and brands and look for "strawberry" in multiple
            fields.

            The query is optional, but `sort_by` value must then be provided.
            """
        )
    )
    boost_phrase = Query(
        description=cd_(
            """This enables an heuristic that will favor,
            matching terms that are consecutive.

            Technically, if you have a query with the two words `whole milk`
            it will boost entries with `"whole milk"` exact match.
            The boost factor is defined by `match_phrase_boost` value in Configuration

            Note, that it only make sense if you use best match sorting.
            So in any other case it is ignored.
            """
        )
    )
    langs = Query(
        description=cd_(
            """List of languages we want to support during search.
            This list should include the user expected language, and additional languages (such
            as english for example).

            This is currently used for language-specific subfields to choose in which
            subfields we're searching in.

            If not provided, `['en']` is used.
            """
        )
    )
    page_size = Query(description="Number of results to return per page.")
    page = Query(ge=1, description="Page to request, starts at 1.")
    fields = Query(
        description="List of fields to include in the response. All other fields will be ignored."
    )
    sort_by = Query(
        description=cd_(
            """Field name to use to sort results,
            the field should exist and be sortable.
            If it is not provided, results are sorted by descending relevance score.
            (aka best match)

            If you put a minus before the name, the results will be sorted by descending order.

            If the field name match a known script (defined in your configuration),
            it will be use for sorting.

            In this case you also need to provide additional parameters corresponding to your script parameters.
            If a script needs parameters, you can only use the POST method.

            Beware that this may have a big [impact on performance][perf_link]

            Also bare in mind [privacy considerations][privacy_link] if your script parameters contains sensible data.

            [perf_link]: https://openfoodfacts.github.io/search-a-licious/users/how-to-use-scripts/#performance-considerations
            [privacy_link]: https://openfoodfacts.github.io/search-a-licious/users/how-to-use-scripts/#performance-considerations
            """
        )
    )
    facets = Query(
        description=cd_(
            """Name of facets to return in the response as a comma-separated value.
            If None (default) no facets are returned.
            """
        )
    )
    charts = Query(
        description=cd_(
            """Name of vega representations to return in the response.
            Can be distribution chart or scatter plot
            """
        )
    )
    sort_params = (
        Query(
            description=cd_(
                """Additional parameters when using  a sort script in sort_by.
            If the sort script needs parameters, you can only be used the POST method.
            """
            ),
        ),
    )
    debug_info = Query(
        description=cd_(
            """Tells which debug information to return in the response.
            It can be a comma separated list of values
            """
        ),
    )


class BaseSearchParameters(BaseModel):
    """Common parameters for search"""

    q: Annotated[
        str | None,
        SearchParametersQuery.q,
    ] = None

    boost_phrase: Annotated[
        bool,
        SearchParametersQuery.boost_phrase,
    ] = False

    page_size: Annotated[int, SearchParametersQuery.page_size] = 10

    page: Annotated[int, SearchParametersQuery.page] = 1

    sort_by: Annotated[
        str | None,
        SearchParametersQuery.sort_by,
    ] = None

    index_id: Annotated[
        str | None,
        SearchParametersQuery.index_id,
    ] = None

    debug_info: Annotated[
        list[DebugInfo] | None,
        SearchParametersQuery.debug_info,
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
        return index_config.scripts and sort_by in index_config.scripts.keys()

    @model_validator(mode="after")
    def check_max_results(self):
        """Check we don't ask too many results at once"""
        if self.page * self.page_size > 10_000:
            raise ValueError(
                f"Maximum number of returned results is 10 000 (here: page * page_size = {self.page * self.page_size})",
            )
        return self

    @field_validator("debug_info")
    @classmethod
    def debug_info_list_from_str(
        cls, debug_info: str | list[DebugInfo] | None
    ) -> list[DebugInfo] | None:
        """We can pass a comma separated list of DebugInfo values as a string"""
        if isinstance(debug_info, str):
            values = [getattr(DebugInfo, part, None) for part in debug_info.split(",")]
            debug_info = [v for v in values if v is not None]
        return debug_info


# TODO: this way of doing could be simplified simply using inheritance
class SearchParameters(BaseSearchParameters):
    """POST parameters for search"""

    # forbid extra parameters to prevent failed expectations because of typos
    model_config = {"extra": "forbid"}

    langs: Annotated[
        list[str],
        SearchParametersQuery.langs,
    ] = ["en"]

    fields: Annotated[
        list[str] | None,
        SearchParametersQuery.fields,
    ] = None

    facets: Annotated[
        list[str] | None,
        SearchParametersQuery.facets,
    ] = None

    charts: Annotated[
        list[ChartType] | None,
        SearchParametersQuery.charts,
    ] = None

    sort_params: Annotated[
        JSONType | None,
        SearchParametersQuery.sort_params,
    ] = None

    @model_validator(mode="after")
    def sort_by_is_field_or_script(self):
        """Verify sort_by is a valid field or script name"""
        index_config = self.index_config
        _, sort_by = self.sign_sort_by
        is_field = sort_by in index_config.fields
        # TODO: verify field type is compatible with sorting
        if not (self.sort_by is None or is_field or self.uses_sort_script):
            raise ValueError(
                "`sort_by` must be a valid field name or script name or None"
            )
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
        errors = check_all_values_are_fields_agg(self.index_id, self.facets)
        if errors:
            raise ValueError(errors)
        return self

    @model_validator(mode="after")
    def check_charts_are_valid(self):
        """Check that the graph names are valid."""
        if self.charts is None:
            return self

        errors = check_all_values_are_fields_agg(
            self.index_id,
            [
                chart.field
                for chart in self.charts
                if chart.chart_type == "DistributionChartType"
            ],
        )

        errors.extend(
            check_fields_are_numeric(
                self.index_id,
                [
                    chart.x
                    for chart in self.charts
                    if chart.chart_type == "ScatterChartType"
                ]
                + [
                    chart.y
                    for chart in self.charts
                    if chart.chart_type == "ScatterChartType"
                ],
            )
        )

        if errors:
            raise ValueError(errors)
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


class GetSearchParameters(BaseSearchParameters):
    """Parameters for GET /search"""

    # forbid extra parameters to prevent failed expectations because of typos
    model_config = {"extra": "forbid"}

    langs: Annotated[
        str,
        SearchParametersQuery.langs,
    ] = "en"

    fields: Annotated[
        str | None,
        SearchParametersQuery.fields,
    ] = None

    facets: Annotated[
        str | None,
        SearchParametersQuery.facets,
    ] = None

    charts: Annotated[
        str | None,
        SearchParametersQuery.charts,
    ] = None

    def parse_charts_get(self, charts_params: str):
        """
        Parse for get params are 'field' or 'xfield:yfield'
        separated by ',' for Distribution and Scatter charts.

        Directly the dictionnaries in POST request
        """
        charts = []
        for c in charts_params.split(","):
            if ":" in c:
                [x, y] = c.split(":")
                charts.append(ScatterChartType(x=x, y=y))
            else:
                charts.append(DistributionChartType(field=c))
        return charts

    def to_search_parameters(self) -> SearchParameters:
        """Convert to a SearchParameters object"""
        # str to lists
        langs_list = self.langs.split(",") if self.langs else ["en"]
        fields_list = self.fields.split(",") if self.fields else None
        facets_list = self.facets.split(",") if self.facets else None
        charts_list = self.parse_charts_get(self.charts) if self.charts else None
        # str to good type
        debug_info_list = SearchParameters.debug_info_list_from_str(self.debug_info)
        return SearchParameters(
            q=self.q,
            boost_phrase=self.boost_phrase,
            langs=langs_list,
            page_size=self.page_size,
            page=self.page,
            fields=fields_list,
            sort_by=self.sort_by,
            facets=facets_list,
            charts=charts_list,
            index_id=self.index_id,
            debug_info=debug_info_list,
        )


class FetcherStatus(Enum):
    """Status of a fetcher

    * FOUND - document was found, index it
    * REMOVED - document was removed, remove it
    * SKIP - skip this document / update
    * RETRY - retry this document / update later
    * OTHER - unknown error
    """

    FOUND = 1
    REMOVED = -1
    SKIP = 0
    RETRY = 2
    OTHER = 3


class FetcherResult(BaseModel):
    """Result for a document fetcher

    This is also used by pre-processors
    who have the opportunity to discard an entry
    """

    status: FetcherStatus
    document: JSONType | None
