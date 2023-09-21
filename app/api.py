import json
from typing import Annotated

from elasticsearch_dsl import Q, Search
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from app.config import CONFIG
from app.query import build_search_query
from app.utils import connection, constants, get_logger, response

logger = get_logger()

app = FastAPI()
connection.get_connection()


from app.utils import constants


class SearchBase(BaseModel):
    response_fields: set[str] | None = None
    num_results: int = 10

    def get_num_results(self):
        return min(self.num_results, constants.MAX_RESULTS)


class AutocompleteRequest(SearchBase):
    text: str
    search_fields: list[str] = constants.AUTOCOMPLETE_FIELDS


@app.get("/product/{barcode}")
def get_product(barcode: str):
    results = (
        Search(index=CONFIG.index.name)
        .query("term", code=barcode)
        .extra(size=1)
        .execute()
    )
    results_dict = [r.to_dict() for r in results]

    if not results_dict:
        raise HTTPException(status_code=404, detail="Barcode not found")

    product = results_dict[0]
    return product


@app.post("/autocomplete")
def autocomplete(request: AutocompleteRequest):
    if not request.search_fields:
        request.search_fields = constants.AUTOCOMPLETE_FIELDS
    for field in request.search_fields:
        if field not in constants.AUTOCOMPLETE_FIELDS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid field: {field}",
            )

    match_queries = []
    for field in request.search_fields:
        autocomplete_field_name = f"{field}__autocomplete"
        match_queries.append(
            Q("match", **{autocomplete_field_name: request.text}),
        )

    results = (
        Search(index=CONFIG.index.name)
        .query("bool", should=match_queries)
        .extra(
            size=request.get_num_results(),
        )
        .execute()
    )
    resp = response.create_response(results, request.response_fields)
    return resp


@app.get("/search")
def search(
    q: str,
    langs: Annotated[list[str] | None, Query()] = None,
    num_results: int = 10,
    projection: Annotated[list[str] | None, Query()] = None,
):
    langs = set(langs or ["en"])
    query = build_search_query(q, langs, num_results, CONFIG)
    logger.info("query:\n%s", json.dumps(query.to_dict(), indent=4))
    results = query.execute()
    return response.create_response(results, projection)
