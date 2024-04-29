import json
from pathlib import Path
from typing import Annotated, Any, cast

import elasticsearch
from elasticsearch_dsl import Search
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from app import config
from app._types import SearchResponse, SuccessSearchResponse
from app.config import check_config_is_defined, settings
from app.postprocessing import (
    BaseResultProcessor,
    load_result_processor,
    process_taxonomy_completion_response,
)
from app.query import (
    build_completion_query,
    build_elasticsearch_query_builder,
    build_search_query,
    execute_query,
)
from app.utils import connection, get_logger, init_sentry

logger = get_logger()


if config.CONFIG is None:
    # We want to be able to import api.py (for tests for example) without
    # failure, but we add a warning message as it's not expected in a
    # production settings
    logger.warning("Main configuration is not set, use CONFIG_PATH envvar")
    FILTER_QUERY_BUILDERS = {}
    RESULT_PROCESSORS = {}
else:
    # we cache query builder and result processor here for faster processing
    FILTER_QUERY_BUILDERS = {
        index_id: build_elasticsearch_query_builder(index_config)
        for index_id, index_config in config.CONFIG.indices.items()
    }
    RESULT_PROCESSORS = {
        index_id: load_result_processor(index_config)
        for index_id, index_config in config.CONFIG.indices.items()
    }


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
)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
init_sentry(settings.sentry_dns)
connection.get_es_client()


INDEX_ID_QUERY_PARAM = Query(
    description="""Index ID to use for the search, if not provided, the default index is used.
    If there is only one index, this parameter is not needed."""
)


def check_index_id_is_defined(index_id: str | None, config: config.Config) -> None:
    """Check that the index ID is defined in the configuration.

    Raise an HTTPException if it's not the case.

    :param index_id: index ID to check
    :param config: configuration to check against
    """
    if index_id is None:
        if len(config.indices) > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Index ID must be provided when there is more than one index, available indices: {list(config.indices.keys())}",
            )
    elif index_id not in config.indices:
        raise HTTPException(
            status_code=404,
            detail=f"Index ID '{index_id}' not found, available indices: {list(config.indices.keys())}",
        )


@app.get("/document/{identifier}")
def get_document(
    identifier: str, index_id: Annotated[str | None, INDEX_ID_QUERY_PARAM] = None
):
    """Fetch a document from Elasticsearch with specific ID."""
    check_config_is_defined()
    global_config = cast(config.Config, config.CONFIG)
    check_index_id_is_defined(index_id, global_config)
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


@app.get("/search")
def search(
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
    ] = None,
    langs: Annotated[
        str | None,
        Query(
            description="""A comma-separated list of languages we want to support during search.
This list should include the user expected language, and additional languages (such
as english for example).

This is currently used for language-specific subfields to choose in which
subfields we're searching in.

If not provided, `['en']` is used."""
        ),
    ] = None,
    page_size: Annotated[
        int, Query(description="Number of results to return per page.")
    ] = 10,
    page: Annotated[int, Query(ge=1, description="Page to request, starts at 1.")] = 1,
    fields: Annotated[
        str | None,
        Query(
            description="Fields to include in the response, as a comma-separated value. All other fields will be ignored."
        ),
    ] = None,
    sort_by: Annotated[
        str | None,
        Query(
            description="""Field name to use to sort results, the field should exist
            and be sortable. If it is not provided, results are sorted by descending relevance score."""
        ),
    ] = None,
    index_id: Annotated[
        str | None,
        INDEX_ID_QUERY_PARAM,
    ] = None,
) -> SearchResponse:
    check_config_is_defined()
    global_config = cast(config.Config, config.CONFIG)
    check_index_id_is_defined(index_id, global_config)
    index_id, index_config = global_config.get_index_config(index_id)
    result_processor = cast(BaseResultProcessor, RESULT_PROCESSORS[index_id])
    if q is None and sort_by is None:
        raise HTTPException(
            status_code=400, detail="`sort_by` must be provided when `q` is missing"
        )

    langs_set = set(langs.split(",") if langs else ["en"])
    logger.debug(
        "Received search query: q='%s', langs='%s', page=%d, "
        "page_size=%d, fields='%s', sort_by='%s'",
        q,
        langs_set,
        page,
        page_size,
        fields,
        sort_by,
    )

    if page * page_size > 10_000:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum number of returned results is 10 000 (here: page * page_size = {page * page_size})",
        )

    query = build_search_query(
        q=q,
        langs=langs_set,
        size=page_size,
        page=page,
        config=index_config,
        sort_by=sort_by,
        # filter query builder is generated from elasticsearch mapping and
        # takes ~40ms to generate, build-it before hand to avoid this delay
        filter_query_builder=FILTER_QUERY_BUILDERS[index_id],
    )
    logger.debug("Elasticsearch query: %s", query.to_dict())

    projection = set(fields.split(",")) if fields else None
    return execute_query(
        query,
        result_processor,
        page=page,
        page_size=page_size,
        projection=projection,
    )


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
    check_index_id_is_defined(index_id, global_config)
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

    results = search(
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
