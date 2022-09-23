"""
Script that allows manually querying the local search service
"""
from __future__ import annotations

import argparse
import json
import time

import requests


def manual_query(hostname, port):

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
            '{}:{}/autocomplete'.format(hostname, port), json=payload,
        )
        print(json.dumps(response.json(), indent=4, sort_keys=True))
        print(f'Number of results: {len(response.json())}')
        end_time = time.perf_counter()
        print(f'Time: {end_time - start_time} seconds')


if __name__ == '__main__':
    parser = argparse.ArgumentParser('http_autocomplete_query')
    parser.add_argument(
        '--hostname', type=str, default='http://127.0.0.1',
    )
    parser.add_argument(
        '--port', type=int, default=8000,
    )
    args = parser.parse_args()
    manual_query(args.hostname, args.port)
