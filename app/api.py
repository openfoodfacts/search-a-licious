import json
from typing import Annotated

from elasticsearch_dsl import Q, Search
from fastapi import FastAPI, HTTPException, Query

from app.config import CONFIG
from app.models.request import AutocompleteRequest
from app.utils import (
    connection,
    constants,
    dict_utils,
    get_logger,
    query_utils,
    response,
)

logger = get_logger()

app = FastAPI()
connection.get_connection()


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


def validate_field(field, fields_to_types, valid_types, filter_type):
    try:
        field_value = dict_utils.get_nested_value(field, fields_to_types)
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Field {field} does not exist",
        )
    field_type = field_value["type"]
    if field_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Field {field} is not of type {filter_type}",
        )
    return field_type


@app.get("/search")
def search(
    q: str,
    langs: Annotated[list[str] | None, Query()] = None,
    num_results: int = 10,
    projection: Annotated[list[str] | None, Query()] = None,
):
    langs = set(langs or ["en"])
    query = query_utils.build_search_query(q, langs, num_results, CONFIG)
    logger.info("query:\n%s", json.dumps(query.to_dict(), indent=4))
    results = query.execute()
    return response.create_response(results, projection)
