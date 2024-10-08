import json
import os
from pathlib import Path
from typing import Annotated, Any, cast

import elasticsearch
import starlette.status as status
from elasticsearch_dsl import Search
from fastapi import Body, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

import app.search as app_search
from app import config
from app._types import (
    INDEX_ID_QUERY_PARAM,
    DistributionChartType,
    GetSearchParamsTypes,
    ScatterChartType,
    SearchParameters,
    SearchResponse,
    SuccessSearchResponse,
)
from app.config import check_config_is_defined, settings
from app.postprocessing import process_taxonomy_completion_response
from app.query import build_completion_query
from app.utils import connection, get_logger, init_sentry
from app.validations import check_index_id_is_defined

logger = get_logger()


API_DESCRIPTION = """
The Search-a-licious API helps you quickly build applications with search capabilities.

You can find the API documentation here.

See also the available [web-components](../static/web-components.html) to build your search interface.

See the [project](https://github.com/openfoodfacts/search-a-licious/) for more information.
"""


app = FastAPI(
    title="search-a-licious API",
    contact={
        "name": "The Open Food Facts team",
        "url": "https://world.openfoodfacts.org",
        "email": "contact@openfoodfacts.org",
    },
    license_info={
        "name": " AGPL-3.0",
        "url": "https://www.gnu.org/licenses/agpl-3.0.en.html",
    },
    description=API_DESCRIPTION,
)
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost,http://127.0.0.1"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
init_sentry(settings.sentry_dns)
connection.get_es_client()


def check_index_id_is_defined_or_400(index_id: str | None, config: config.Config):
    try:
        check_index_id_is_defined(index_id, config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/document/{identifier}")
def get_document(
    identifier: str, index_id: Annotated[str | None, INDEX_ID_QUERY_PARAM] = None
):
    """Fetch a document from Elasticsearch with specific ID."""
    check_config_is_defined()
    global_config = cast(config.Config, config.CONFIG)
    check_index_id_is_defined_or_400(index_id, global_config)
    index_id, index_config = global_config.get_index_config(index_id)

    id_field_name = index_config.index.id_field_name
    results = (
        Search(index=index_config.index.name)
        .query("term", **{id_field_name: identifier})
        .extra(size=1)
        .execute()
    )
    results_dict = [r.to_dict() for r in results]

    if not results_dict:
        raise HTTPException(status_code=404, detail="code not found")

    product = results_dict[0]
    return product


def status_for_response(result: SearchResponse):
    if isinstance(result, SuccessSearchResponse):
        return status.HTTP_200_OK
    else:
        # TODO: should we refine that ?
        return status.HTTP_500_INTERNAL_SERVER_ERROR


@app.post("/search")
def search(response: Response, search_parameters: Annotated[SearchParameters, Body()]):
    result = app_search.search(search_parameters)
    response.status_code = status_for_response(result)
    return result


def parse_charts_get(charts_params: str):
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


@app.get("/search")
def search_get(
    response: Response,
    q: GetSearchParamsTypes.q = None,
    boost_phrase: GetSearchParamsTypes.boost_phrase = False,
    langs: GetSearchParamsTypes.langs = None,
    page_size: GetSearchParamsTypes.page_size = 10,
    page: GetSearchParamsTypes.page = 1,
    fields: GetSearchParamsTypes.fields = None,
    sort_by: GetSearchParamsTypes.sort_by = None,
    facets: GetSearchParamsTypes.facets = None,
    charts: GetSearchParamsTypes.charts = None,
    index_id: GetSearchParamsTypes.index_id = None,
    debug_info: GetSearchParamsTypes.debug_info | str = None,
) -> SearchResponse:
    # str to lists
    langs_list = langs.split(",") if langs else ["en"]
    fields_list = fields.split(",") if fields else None
    facets_list = facets.split(",") if facets else None
    charts_list = parse_charts_get(charts) if charts else None
    # str to good type
    debug_info_list = SearchParameters.debug_info_list_from_str(debug_info)
    # create SearchParameters object
    try:
        search_parameters = SearchParameters(
            q=q,
            boost_phrase=boost_phrase,
            langs=langs_list,
            page_size=page_size,
            page=page,
            fields=fields_list,
            sort_by=sort_by,
            facets=facets_list,
            index_id=index_id,
            charts=charts_list,
            debug_info=debug_info_list,
        )
        result = app_search.search(search_parameters)
        response.status_code = status_for_response(result)
        return result
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/autocomplete")
def taxonomy_autocomplete(
    q: Annotated[str, Query(description="User autocomplete query.")],
    # We can't yet use list[str] as there an error is raised when passing an
    # empty list:
    # https://github.com/tiangolo/fastapi/issues/9920
    taxonomy_names: Annotated[
        str,
        Query(
            description="Name(s) of the taxonomy to search in, as a comma-separated value."
        ),
    ],
    lang: Annotated[
        str, Query(description="Language to search in, defaults to 'en'.")
    ] = "en",
    size: Annotated[int, Query(description="Number of results to return.")] = 10,
    fuzziness: Annotated[
        int | None,
        Query(description="Fuzziness level to use, default to no fuzziness."),
    ] = None,
    index_id: Annotated[str | None, INDEX_ID_QUERY_PARAM] = None,
):
    check_config_is_defined()
    global_config = cast(config.Config, config.CONFIG)
    check_index_id_is_defined_or_400(index_id, global_config)
    index_id, index_config = global_config.get_index_config(index_id)
    taxonomy_names_list = taxonomy_names.split(",")
    query = build_completion_query(
        q=q,
        taxonomy_names=taxonomy_names_list,
        lang=lang,
        size=size,
        config=index_config,
        fuzziness=fuzziness,
    )
    try:
        es_response = query.execute()
    except elasticsearch.NotFoundError:
        raise HTTPException(
            status_code=500,
            detail="taxonomy index not found, taxonomies need to be imported first",
        )

    response = process_taxonomy_completion_response(es_response)

    return {
        **response,
        "debug": {
            "query": query.to_dict(),
        },
    }


@app.get("/", response_class=HTMLResponse)
def off_demo():
    return RedirectResponse(url="/static/off.html", status_code=status.HTTP_302_FOUND)


@app.get("/off-test", response_class=HTMLResponse)
def html_search(
    request: Request,
    q: str | None = None,
    page: int = 1,
    page_size: int = 24,
    langs: str = "fr,en",
    sort_by: str | None = None,
    index_id: Annotated[str | None, INDEX_ID_QUERY_PARAM] = None,
    # Display debug information in the HTML response
    display_debug: bool = False,
):
    if not q:
        return templates.TemplateResponse("search.html", {"request": request})

    results = search_get(
        q=q,
        langs=langs,
        page_size=page_size,
        page=page,
        sort_by=sort_by,
        index_id=index_id,
    )
    template_data: dict[str, Any] = {
        "q": q or "",
        "request": request,
        "sort_by": sort_by,
        "results": results,
        "es_query": json.dumps(results.debug.query, indent=4),
        "display_debug": display_debug,
    }
    if results.is_success():
        results = cast(SuccessSearchResponse, results)
        template_data["aggregations"] = results.aggregations
        page_count = results.page_count
        pagination: list[dict[str, Any]] = [
            {"name": p, "selected": p == page, "page_id": p}
            for p in range(1, page_count + 1)
            # Allow to scroll over a window of 10 pages
            if min(page - 5, page_count - 10) <= p <= max(page + 5, 10)
        ]
        if page > 1:
            pagination.insert(
                0, {"name": "Previous", "selected": False, "page_id": page - 1}
            )
        if page < page_count:
            pagination.append({"name": "Next", "selected": False, "page_id": page + 1})

        template_data["pagination"] = pagination

    return templates.TemplateResponse(
        "display_results.html",
        template_data,
    )


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return """User-agent: *\nDisallow: /"""


@app.get("/health")
def healthcheck():
    from app.health import health

    message, status, _ = health.run()
    logger.warning("HEALTH:", message, status)
    return Response(content=message, status_code=status, media_type="application/json")
