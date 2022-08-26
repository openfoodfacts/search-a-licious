"""
Script that allows manually querying the local search service
"""
from __future__ import annotations

import argparse
import json
import time

import requests

from app.utils import connection


def manual_query(hostname, port, field):
    connection.get_connection()

    while True:
        search_term = input('Please enter search term:\n')
        start_time = time.perf_counter()

        payload = {
            'string_filters': [
                {
                    'field': field,
                    'value': search_term,
                    'operator': 'eq',
                },
            ],
            # To test more advanced features, uncomment the below
            # 'numeric_filters': [
            #     {
            #         'field': 'nutriments.sodium_value',
            #         'value': 5,
            #         'operator': 'gt',
            #     },
            #     {
            #         'field': 'nutriments.sodium_value',
            #         'value': 50,
            #         'operator': 'lt',
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
        response = requests.post(
            '{}:{}/search'.format(hostname, port), json=payload,
        )
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
    parser = argparse.ArgumentParser('http_search_query')
    parser.add_argument(
        '--hostname', type=str, default='http://127.0.0.1',
    )
    parser.add_argument(
        '--port', type=int, default=8000,
    )
    parser.add_argument(
        '--field', help='Field to search', type=str, default='code',
    )
    args = parser.parse_args()
    manual_query(args.hostname, args.port, args.field)
