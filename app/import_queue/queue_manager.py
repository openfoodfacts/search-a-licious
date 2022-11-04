from __future__ import annotations

import atexit

from app.import_queue.product_client import ProductClient
from app.import_queue.redis_client import RedisClient
from app.models.product import create_product_from_dict
from app.utils import constants


class QueueManager:
    def __init__(self):
        self.stop_received = False
        self.redis_client = RedisClient()
        self.product_client = ProductClient()

    def consume(self):
        while not self.stop_received:
            code = self.redis_client.get_from_queue()
            if not code:
                continue
            item = self.product_client.get_product(code)
            if not item:
                print(
                    'Unable to retrieve product with code {}'.format(
                        code,
                    ), flush=True,
                )
                continue
            # As the code is unique (set in the save method), this will handle updates as well as new documents
            product = create_product_from_dict(item)
            product.save()
            print(
                f'Received Redis update for product: {product.product_name}', flush=True,
            )

            # Now, write a key that can be read for full imports
            self.redis_client.write_processed(product.code)

    def stop(self):
        print(
            'Stopping redis reader, may take {} seconds'.format(
                constants.REDIS_READER_TIMEOUT,
            ),
            flush=True,
        )
        self.stop_received = True


def run_queue(queue_manager):
    queue_manager.consume()


def handle_stop(queues):
    queue = queues['current']
    if (queue):
        queue.stop()


def run_queue_safe():
    """Spawn and consume queues until a clean stop happens"""
    print('Starting redis consumer', flush=True)

    # we need a dict to have a reference
    queues = {'current': None}

    atexit.register(handle_stop, queues)

    alive = True
    while alive:
        try:
            queues['current'] = QueueManager()
            queues['current'].consume()
            alive = False
        except Exception as e:
            print(f'Received {e}, respawning a consumer', flush=True)


if __name__ == '__main__':
    # create elasticsearch connection
    from app.utils import connection
    connection.get_connection()
    # run queue
    run_queue_safe()
