import pytest
from unittest import mock
from unittest.mock import call

from app import api
from app.models.request import AutocompleteRequest
from app.utils import constants


class TestApi:
    @pytest.mark.parametrize(
        "search_fields,num_results,expected",
        [
            ([], 10, constants.AUTOCOMPLETE_FIELDS),
            (['product_name'], 50, ['product_name']),
        ]
    )
    def test_autocomplete_search_fields(self, search_fields, num_results, expected):
        with mock.patch("elasticsearch.Elasticsearch.search") as mocked_search:
            api.autocomplete(request=AutocompleteRequest(text='test', search_fields=search_fields, num_results=num_results))
            expected_body = {
               "query":{
                  "bool":{
                     "should":[
                        {
                           "match": {
                              field_name: "test"
                           }
                        } for field_name in expected
                     ]
                  }
               },
               "size": num_results
            }
            assert mocked_search.call_args_list == [call(index=['openfoodfacts'], body=expected_body)]


    def test_autocomplete_error(self):
        with pytest.raises(api.HTTPException):
            api.autocomplete(request=AutocompleteRequest(text='test', search_fields=["invalid_field"]))

