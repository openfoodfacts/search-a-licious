from __future__ import annotations

from app.import_queue.product_client import ProductClient
from app.import_queue.redis_client import RedisClient
from app.models.product import create_product_from_dict
from app.utils import constants


class QueueManager:
    def __init__(self):
        self.redis_client = RedisClient()
        self.stop_received = False

    def consume(self):
        product_client = ProductClient()
        while not self.stop_received:
            code = self.redis_client.get_from_queue()
            if not code:
                continue
            item = product_client.get_product(code)
            if not item:
                print('Unable to retrieve product with code {}'.format(code))
                continue

            # As the code is unique (set in the save method), this will handle updates as well as new documents
            product = create_product_from_dict(item)
            product.save()
            print(f'Recieved Redis update for product: {product.product_name}')

            # Now, write a key that can be read for full imports
            self.redis_client.write_processed(product.code)

    def stop(self):
        print(
            'Stopping redis reader, may take {} seconds'.format(
                constants.REDIS_READER_TIMEOUT,
            ),
        )
        self.stop_received = True


def run_queue(queue_manager):
    queue_manager.consume()
