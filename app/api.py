from pathlib import Path
from typing import Annotated

from elasticsearch_dsl import Search
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import CONFIG, settings
from app.postprocessing import load_result_processor
from app.query import build_search_query
from app.utils import connection, get_logger, init_sentry

logger = get_logger()

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
connection.get_connection()


result_processor = load_result_processor(CONFIG)


@app.get("/document/{identifier}")
def get_document(identifier: str):
    """Fetch a document from Elasticsearch with specific ID."""
    id_field_name = CONFIG.index.id_field_name
    results = (
        Search(index=CONFIG.index.name)
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
        str,
        Query(
            description="""The search query, it supports Lucene search query
syntax (https://lucene.apache.org/core/3_6_0/queryparsersyntax.html). Words
that are not recognized by the lucene query parser are searched as full text
search.

Example: `categories:"en:beverages" strawberry brands:"casino"` query use a
filter clause for categories and brands and look for "strawberry" in multiple
fields.

 The query is optional, but `sort_by` value must then be provided."""
        ),
    ] = None,
    langs: Annotated[
        list[str] | None,
        Query(
            description="""A list of languages we want to support during search. This
list should include the user expected language, and additional languages (such
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
):
    if q is None and sort_by is None:
        raise HTTPException(
            status_code=400, detail="`sort_by` must be provided when `q` is missing"
        )

    langs = set(langs or ["en"])
    query = build_search_query(
        q=q, langs=langs, size=page_size, page=page, config=CONFIG, sort_by=sort_by
    )
    results = query.execute()

    projection = set(fields.split(",")) if fields else None
    response = result_processor.process(results, projection)

    return {
        **response,
        "page": page,
        "page_size": page_size,
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
):
    logger.info("query: %s", q)
    if q:
        results = search(q, langs, page_size, page, sort_by)
        logger.info(results)
    else:
        return templates.TemplateResponse("search.html", {"request": request})

    return templates.TemplateResponse(
        "display_results.html", {"q": q or "", "request": request, "results": results}
    )
