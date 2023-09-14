from __future__ import annotations

import time

from redis import Redis


def write_to_redis():
    redis = Redis(
        host="searchredis",
        port=6379,
        decode_responses=True,
    )
    key_name = "search_import_queue"
    while True:
        code = input("Please enter a product code:\n")
        start_time = time.perf_counter()

        redis.rpush(key_name, code)
        end_time = time.perf_counter()
        print(f"Time: {end_time - start_time} seconds")


if __name__ == "__main__":
    write_to_redis()
