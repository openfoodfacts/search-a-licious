"""
Script that allows manually querying the local search service
"""
import json
import time
import requests

from app.utils import connection


def manual_query():

    connection.get_connection()

    while True:
        search_term = input("Please enter search term:\n")
        start_time = time.perf_counter()

        payload = {
            'text': search_term,
            'num_results': 10,
            'response_fields': ['product_name', 'pnns_groups_1'],
        }
        response = requests.post("http://127.0.0.1:8000/autocomplete", json=payload)
        print(json.dumps(response.json(), indent=4, sort_keys=True))
        print("Number of results: {}".format(len(response.json())))
        end_time = time.perf_counter()
        print("Time: {} seconds".format(end_time - start_time))


if __name__ == "__main__":
    manual_query()