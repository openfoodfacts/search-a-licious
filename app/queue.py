import atexit
import time

import requests

from app.config import Config, settings
from app.indexing import DocumentProcessor
from app.types import JSONType
from app.utils import get_logger
from app.utils.connection import get_redis_client

logger = get_logger(__name__)


class RedisClient:
    def __init__(self):
        self.redis = get_redis_client()
        self.queue_key_name = "search_import_queue"

    def get_from_queue(self):
        # Blocks for N seconds
        pop_resp = self.redis.blpop(
            self.queue_key_name,
            settings.redis_reader_timeout,
        )
        if not pop_resp:
            return None
        _, item = pop_resp
        return item

    def write_processed(self, code):
        # Write a key that can be read for full imports
        # Format should be:
        # SET product:<timestamp>:<barcode> <full_product_definition> EX 129600
        # 129600 is chosen as it's 36 hours, so enough time to cover between a
        # nightly data dump
        self.redis.set(
            name=f"product:{int(time.time())}:{code}",
            ex=settings.redis_expiration,
            value="",
        )

    def get_processed_since(self, start_timestamp: int) -> list[tuple[int, JSONType]]:
        product_client = ProductClient()
        fetched_codes = set()
        timestamp_processed_values = []
        for key in self.redis.scan_iter("product:*"):
            logger.info(key)
            components = key.split(":")
            if len(components) != 3:
                logger.info("Invalid key: %s", key)
                continue

            timestamp = int(components[1])
            if timestamp < start_timestamp:
                continue

            code = components[2]
            # Avoid fetching the same code repeatedly
            if code in fetched_codes:
                continue
            fetched_codes.add(code)
            product = product_client.get_product(code)
            if not product:
                logger.info("Unable to retrieve product: %s", code)
                continue

            timestamp_processed_values.append((timestamp, product))

        # Sort by timestamp
        timestamp_processed_values.sort(key=lambda x: x[0])
        return timestamp_processed_values


class ProductClient:
    def __init__(self):
        self.server_url = settings.openfoodfacts_base_url

    def get_product(self, code):
        url = f"{self.server_url}/api/v2/product/{code}"
        response = requests.get(url)
        json_response = response.json()
        if not json_response or not json_response.get("product"):
            return None
        return json_response["product"]


class QueueManager:
    def __init__(self, config: Config):
        self.stop_received = False
        self.redis_client = RedisClient()
        self.product_client = ProductClient()
        self.processor = DocumentProcessor(config)

    def consume(self):
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
            product = self.processor.from_dict(item)
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
