from __future__ import annotations

import json
import time

from redis import Redis


def write_to_redis():
    redis = Redis(
        host='localhost',
        port=6379,
        decode_responses=True,
    )
    key_name = 'search_import_queue'
    while True:
        product_name = input('Please enter a product name:\n')
        start_time = time.perf_counter()

        # Sample fields
        item = {
            'code': '0011110296375',
            'url': 'http://world-en.openfoodfacts.org/product/0011110296375/traditional-pork-sausage-linksz',
            'creator': 'test',
            'created_t': '1647895014',
            'product_name': product_name,
        }

        redis.rpush(key_name, json.dumps(item))
        # redis.wait(1, 10)
        print('wrote to redis')
        end_time = time.perf_counter()
        print(f'Time: {end_time - start_time} seconds')


if __name__ == '__main__':
    write_to_redis()
