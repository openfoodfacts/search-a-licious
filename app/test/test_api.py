from __future__ import annotations

import datetime
from unittest import mock
from unittest.mock import call

import pytest

from app import api
from app.models.request import AutocompleteRequest
from app.models.request import DateTimeFilter
from app.models.request import NumericFilter
from app.models.request import SearchRequest
from app.models.request import StringFilter
from app.utils import constants


class TestApi:
    def test_get_product(self):
        with mock.patch("elasticsearch.Elasticsearch.search") as mocked_search:
            # Should raise as we're not returning anything
            with pytest.raises(api.HTTPException):
                api.get_product("123456")

            expected_body = {
                "query": {
                    "term": {
                        "code": "123456",
                    },
                },
                "size": 1,
            }
            assert mocked_search.call_args_list == [
                call(index=["openfoodfacts"], body=expected_body),
            ]

    @pytest.mark.parametrize(
        "search_fields,num_results,expected",
        [
            ([], 10, constants.AUTOCOMPLETE_FIELDS),
            (["product_name"], 50, ["product_name"]),
        ],
    )
    def test_autocomplete_search_fields(self, search_fields, num_results, expected):
        with mock.patch("elasticsearch.Elasticsearch.search") as mocked_search:
            api.autocomplete(
                request=AutocompleteRequest(
                    text="test",
                    search_fields=search_fields,
                    num_results=num_results,
                ),
            )
            expected_body = {
                "query": {
                    "bool": {
                        "should": [
                            {
                                "match": {
                                    field_name + ".autocomplete": "test",
                                },
                            }
                            for field_name in expected
                        ],
                    },
                },
                "size": num_results,
            }
            assert mocked_search.call_args_list == [
                call(index=["openfoodfacts"], body=expected_body),
            ]

    def test_autocomplete_error(self):
        with pytest.raises(api.HTTPException):
            api.autocomplete(
                request=AutocompleteRequest(
                    text="test",
                    search_fields=["invalid_field"],
                ),
            )

    def test_search_error(self):
        with pytest.raises(api.HTTPException):
            api.search(request=SearchRequest())

    @pytest.mark.parametrize(
        "string_filters,numeric_filters,date_time_filters,num_results,expected_body",
        [
            (
                [
                    StringFilter(
                        field="product_name",
                        value="water",
                        operator="eq",
                    ),
                ],
                [],
                [],
                100,
                {
                    "query": {
                        "bool": {"must": [{"term": {"product_name.raw": "water"}}]},
                    },
                    "size": 100,
                },
            ),
            (
                [
                    StringFilter(
                        field="product_name",
                        value="water",
                        operator="eq",
                    ),
                    StringFilter(
                        field="product_name",
                        value="vitamins",
                        operator="ne",
                    ),
                ],
                [],
                [],
                10,
                {
                    "query": {
                        "bool": {
                            "must": [{"term": {"product_name.raw": "water"}}],
                            "must_not": [
                                {"term": {"product_name.raw": "vitamins"}},
                            ],
                        },
                    },
                    "size": 10,
                },
            ),
            (
                [
                    StringFilter(
                        field="product_name",
                        value="water",
                        operator="like",
                    ),
                ],
                [],
                [],
                10,
                {
                    "query": {
                        "bool": {"must": [{"match": {"product_name": "water"}}]},
                    },
                    "size": 10,
                },
            ),
            (
                [],
                [
                    NumericFilter(
                        field="nutriments.carbohydrates_100g",
                        value=10,
                        operator="eq",
                    ),
                ],
                [],
                10,
                {
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "nested": {
                                        "path": "nutriments",
                                        "query": {
                                            "term": {
                                                "nutriments.carbohydrates_100g": 10.0
                                            },
                                        },
                                    },
                                }
                            ],
                        },
                    },
                    "size": 10,
                },
            ),
            (
                [],
                [
                    NumericFilter(
                        field="nutriments.carbohydrates_100g",
                        value=10,
                        operator="ne",
                    ),
                ],
                [],
                10,
                {
                    "query": {
                        "bool": {
                            "must_not": [
                                {
                                    "nested": {
                                        "path": "nutriments",
                                        "query": {
                                            "term": {
                                                "nutriments.carbohydrates_100g": 10.0
                                            },
                                        },
                                    },
                                }
                            ],
                        },
                    },
                    "size": 10,
                },
            ),
            (
                [],
                [
                    NumericFilter(
                        field="nutriments.carbohydrates_100g",
                        value=10,
                        operator="lt",
                    ),
                ],
                [],
                10,
                {
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "nested": {
                                        "path": "nutriments",
                                        "query": {
                                            "range": {
                                                "nutriments.carbohydrates_100g": {
                                                    "lt": 10.0
                                                }
                                            },
                                        },
                                    },
                                }
                            ],
                        },
                    },
                    "size": 10,
                },
            ),
            (
                [],
                [
                    NumericFilter(
                        field="nutriments.carbohydrates_100g",
                        value=10,
                        operator="gt",
                    ),
                ],
                [],
                10,
                {
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "nested": {
                                        "path": "nutriments",
                                        "query": {
                                            "range": {
                                                "nutriments.carbohydrates_100g": {
                                                    "gt": 10.0
                                                }
                                            },
                                        },
                                    },
                                }
                            ],
                        },
                    },
                    "size": 10,
                },
            ),
            (
                [],
                [],
                [
                    DateTimeFilter(
                        field="created_datetime",
                        value=datetime.datetime(2022, 5, 5),
                        operator="lt",
                    ),
                ],
                10,
                {
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "range": {
                                        "created_datetime": {
                                            "lt": datetime.datetime(2022, 5, 5, 0, 0),
                                        },
                                    },
                                }
                            ],
                        },
                    },
                    "size": 10,
                },
            ),
            (
                [],
                [],
                [
                    DateTimeFilter(
                        field="created_datetime",
                        value=datetime.datetime(2022, 5, 5),
                        operator="gt",
                    ),
                ],
                10,
                {
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "range": {
                                        "created_datetime": {
                                            "gt": datetime.datetime(2022, 5, 5, 0, 0),
                                        },
                                    },
                                }
                            ],
                        },
                    },
                    "size": 10,
                },
            ),
        ],
    )
    def test_create_search_query(
        self,
        string_filters,
        numeric_filters,
        date_time_filters,
        num_results,
        expected_body,
    ):
        with mock.patch("elasticsearch.Elasticsearch.search") as mocked_search:
            api.search(
                request=SearchRequest(
                    string_filters=string_filters,
                    numeric_filters=numeric_filters,
                    date_time_filters=date_time_filters,
                    num_results=num_results,
                ),
            )
            assert mocked_search.call_args_list == [
                call(index=["openfoodfacts"], body=expected_body),
            ]
