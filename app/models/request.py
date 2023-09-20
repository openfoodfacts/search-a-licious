from typing import List

from pydantic import BaseModel

from app.utils import constants


class SearchBase(BaseModel):
    response_fields: set[str] | None = None
    num_results: int = 10

    def get_num_results(self):
        return min(self.num_results, constants.MAX_RESULTS)


class AutocompleteRequest(SearchBase):
    text: str
    search_fields: List[str] = constants.AUTOCOMPLETE_FIELDS
