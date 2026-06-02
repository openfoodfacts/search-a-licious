import logging
from typing import Mapping, cast

import starlette.status as status

import app.search as app_search
from app import config
from app._types import (
    CommonParametersQuery,
    ErrorSearchResponse,
    GetSearchParameters,
    PostSearchParameters,
    SearchResponse,
    SuccessSearchResponse,
)
from app.exceptions import get_es_query_builder
from fastapi import APIRouter
from fastapi.responses import ORJSONResponse

logger = logging.getLogger(__name__)

app = APIRouter()


def extract_str_list(comma_separated_strings: str) -> list[str]:
    strings = comma_separated_strings.split(",")
    return [s.strip() for s in strings if s.strip()]


@app.get(
    "/search",
    responses={
        400: {"model": ErrorSearchResponse},
        500: {"model": ErrorSearchResponse},
    },
)
def get_document(
    params: GetSearchParameters,
) -> SearchResponse:
    """Fetch a document from Elasticsearch with specific ID."""

    res = app_search.search(params)
    return ORJSONResponse(content=res.model_dump(), status_code=status_for_response(res))


def status_for_response(result: SearchResponse):
    if isinstance(result, SuccessSearchResponse):
        return status.HTTP_200_OK

    if isinstance(result, ErrorSearchResponse) and result.errors:
        first_error = result.errors[0]
        if getattr(first_error, "status", None):
            return first_error.status

        titles = {error.title for error in result.errors}

        if titles & {
            "QueryCheckError",
            "InvalidLuceneQueryError",
            "FreeWildCardError",
            "UnknownFieldError",
            "UnknownScriptError",
            "ValueError",
        }:
            return status.HTTP_400_BAD_REQUEST

        if titles & {"es_connection_error", "es_api_error"}:
            return status.HTTP_503_SERVICE_UNAVAILABLE

    return status.HTTP_500_INTERNAL_SERVER_ERROR


@app.post("/search", responses={400: {"model": ErrorSearchResponse}, 500: {"model": ErrorSearchResponse}})
def search(
    params: PostSearchParameters,
) -> SearchResponse:
    """Fetch search results from Open Food Facts."""

    res = app_search.search(params)
    return ORJSONResponse(content=res.model_dump(), status_code=status_for_response(res))


@app.get("/config")
def get_config() -> Mapping:
    return config.get_config().model_dump()
