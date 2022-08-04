"""
Script that allows manually querying ES
"""
import time

from app.models.product import Product
from app.utils import connection


def manual_query():
    connection.get_connection()

    while True:
        search_term = input("Please enter search term:\n")
        start_time = time.perf_counter()
        results = Product.search().query('match', product_name__autocomplete=search_term).execute()
        for result in results[:10]:
            print(result.meta.score, result.product_name)
        end_time = time.perf_counter()
        print("Time: {} seconds".format(end_time - start_time))


if __name__ == "__main__":
    manual_query()