from __future__ import annotations

import logging as log
import os
import time

from redis import Redis

from app.import_queue.product_client import ProductClient
from app.utils import constants


class RedisClient:
    def __init__(self):
        self.redis = Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=6379,
            decode_responses=True,
        )
        self.queue_key_name = 'search_import_queue'

    def get_from_queue(self):
        # Blocks for N seconds
        pop_resp = self.redis.blpop(
            self.queue_key_name, constants.REDIS_READER_TIMEOUT,
        )
        if not pop_resp:
            return None
        _, item = pop_resp
        return item

    def write_processed(self, code):
        # Write a key that can be read for full imports
        # Format should be: SET product:<timestamp>:<barcode> <full_product_definition> EX 129600
        # 129600 is chosen as it's 36 hours, so enough time to cover between a nightly data dump
        self.redis.set(
            name=f'product:{int(time.time())}:{code}',
            ex=constants.REDIS_EXPIRATION,
            value='',
        )

    def get_processed_since(self, start_timestamp: int):
        product_client = ProductClient()
        fetched_codes = set()
        timestamp_processed_values = []
        for key in self.redis.scan_iter('product:*'):
            log.info(key)
            components = key.split(':')
            if len(components) != 3:
                log.info(f'Invalid key: {key}')
                continue

            timestamp = components[1]
            if int(timestamp) < start_timestamp:
                continue

            code = components[2]
            # Avoid fetching the same code repeatedly
            if code in fetched_codes:
                continue
            fetched_codes.add(code)
            product = product_client.get_product(code)
            if not product:
                log.info(f'Unable to retrieve product: {code}')
                continue

            timestamp_processed_values.append((timestamp, product))

        # Sort by timestamp
        timestamp_processed_values.sort(key=lambda x: x[0])
        return timestamp_processed_values
