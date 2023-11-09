from typing import Any

from pydantic import BaseModel

#: A precise expectation of what mappings looks like in json.
#: (dict where keys are always of type `str`).
JSONType = dict[str, Any]


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
    aggregations: JSONType
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
