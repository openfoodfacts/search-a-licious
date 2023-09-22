import atexit

from app.config import CONFIG, Config, settings
from app.import_queue.product_client import ProductClient
from app.import_queue.redis_client import RedisClient
from app.indexing import DocumentProcessor
from app.utils import get_logger

logger = get_logger(__name__)


class QueueManager:
    def __init__(self, config: Config):
        self.stop_received = False
        self.redis_client = RedisClient()
        self.product_client = ProductClient()
        self.config = config

    def consume(self):
        processor = DocumentProcessor(self.config)
        while not self.stop_received:
            code = self.redis_client.get_from_queue()
            if not code:
                continue
            item = self.product_client.get_product(code)
            if not item:
                logger.info("Unable to retrieve product with code %s", code)
                continue
            # As the code is unique (set in the save method), this will handle
            # updates as well as new documents
            product = processor.from_dict(item)
            product.save()
            logger.info(
                "Received Redis update for product: %s - %s", code, product.product_name
            )

            # Now, write a key that can be read for full imports
            self.redis_client.write_processed(product.code)

    def stop(self):
        logger.info(
            "Stopping redis reader, may take %s seconds", settings.redis_reader_timeout
        )
        self.stop_received = True


def run_queue(queue_manager):
    queue_manager.consume()


def handle_stop(queues):
    queue = queues["current"]
    if queue:
        queue.stop()


def run_queue_safe(config: Config):
    """Spawn and consume queues until a clean stop happens"""
    logger.info("Starting redis consumer")

    # we need a dict to have a reference
    queues = {"current": None}

    atexit.register(handle_stop, queues)

    alive = True
    while alive:
        try:
            queues["current"] = QueueManager(config)
            queues["current"].consume()
            alive = False
        except Exception as e:
            logger.info("Received %s, respawning a consumer", e)


if __name__ == "__main__":
    # Create root logger
    get_logger()

    # create elasticsearch connection
    from app.utils import connection

    connection.get_connection()
    # run queue
    run_queue_safe(CONFIG)
