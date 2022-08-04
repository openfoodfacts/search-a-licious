import datetime
from typing import Optional, List, Set
from pydantic import BaseModel

from app.utils import constants


class SearchBase(BaseModel):
    response_fields: Optional[Set[str]]
    num_results: int = 10

    def get_num_results(self):
        return min(self.num_results, constants.MAX_RESULTS)


class AutocompleteRequest(SearchBase):
    text: str
    search_fields: List[str] = constants.AUTOCOMPLETE_FIELDS


class StringFilter(BaseModel):
    field: str
    value: str
    # One of eq, ne, like, without
    operator: str = 'eq'


class NumericFilter(BaseModel):
    field: str
    value: float
    # One of eq, ne, lt, gt, without
    operator: str = 'eq'


class DateTimeFilter(BaseModel):
    field: str
    value: datetime.datetime
    # One of lt, gt, without
    operator: str = 'eq'


class SearchRequest(SearchBase):
    # Works as an intersection/AND query
    string_filters: List[StringFilter] = []
    numeric_filters: List[NumericFilter] = []
    date_time_filters: List[DateTimeFilter] = []
