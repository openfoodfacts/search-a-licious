"""
Script that allows manually querying the local search service
"""
from __future__ import annotations

import json
import time

import requests

from app.utils import connection


def manual_query():
    connection.get_connection()

    while True:
        search_term = input('Please enter search term:\n')
        start_time = time.perf_counter()

        payload = {
            'string_filters': [
                {
                    'field': 'product_name',
                    'value': search_term,
                    'operator': 'like',
                },
            ],
            # 'numeric_filters': [
            #     {
            #         'field': 'energy_kcal_100g',
            #         'value': float(200),
            #         'operator': 'gt',
            #     }
            # ],
            # 'date_time_filters': [
            #     {
            #         'field': 'created_datetime',
            #         'value': "2022-01-28T07:49:14Z",
            #         'operator': 'gt',
            #     }
            # ],
            'num_results': 10,
            # 'response_fields': ['product_name', 'states_tags'],
        }
        response = requests.post('http://127.0.0.1:8000/search', json=payload)
        print(
            json.dumps(
                response.json(), indent=4,
                sort_keys=True, ensure_ascii=False,
            ),
        )
        print(f'Number of results: {len(response.json())}')
        end_time = time.perf_counter()
        print(f'Time: {end_time - start_time} seconds')


if __name__ == '__main__':
    manual_query()
