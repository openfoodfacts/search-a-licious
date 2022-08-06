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
            'text': search_term,
            'search_fields': ['product_name'],
            'num_results': 10,
            'response_fields': ['product_name'],
        }
        response = requests.post(
            'http://127.0.0.1:8001/autocomplete', json=payload,
        )
        print(json.dumps(response.json(), indent=4, sort_keys=True))
        print(f'Number of results: {len(response.json())}')
        end_time = time.perf_counter()
        print(f'Time: {end_time - start_time} seconds')


if __name__ == '__main__':
    manual_query()
