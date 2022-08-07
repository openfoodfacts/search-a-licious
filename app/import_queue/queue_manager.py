from __future__ import annotations

import json

from app.import_queue.redis_client import RedisClient
from app.models.product import Product
from app.utils import constants


class QueueManager:
    def __init__(self):
        self.redis_client = RedisClient()
        self.stop_received = False

    def consume(self):
        while not self.stop_received:
            json_item = self.redis_client.get_from_queue()
            if not json_item:
                continue
            item = json.loads(json_item)

            # As the code is unique (set in the save method), this will handle updates as well as new documents
            product = Product(**item)
            product.save()
            print(f'Recieved Redis update for product: {product.product_name}')

            # Now, write a key that can be read for full imports
            self.redis_client.write_processed(product.code, json_item)

    def stop(self):
        print(
            'Stopping redis reader, may take {} seconds'.format(
                constants.REDIS_READER_TIMEOUT,
            ),
        )
        self.stop_received = True


def run_queue(queue_manager):
    queue_manager.consume()
