import atexit
import time

from app.config import Config, settings
from app.indexing import DocumentProcessor
from app.types import JSONType
from app.utils import get_logger
from app.utils.connection import get_es_client, get_redis_client
from app.utils.download import http_session

logger = get_logger(__name__)


class RedisClient:
    def __init__(self):
        self.redis = get_redis_client()
        self.queue_key_name = settings.redis_import_queue

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

    def write_processed(self, id):
        # Write a key that can be read for full imports
        # Format should be:
        # SET {document_prefix}:<timestamp>:<barcode> <full_definition>
        # EX 129600
        # 129600 is chosen as it's 36 hours, so enough time to cover between a
        # nightly data dump
        self.redis.set(
            name=f"{settings.redis_document_prefix}:{int(time.time())}:{id}",
            ex=settings.redis_expiration,
            value="",
        )

    def get_processed_since(self, start_timestamp: int) -> list[tuple[int, JSONType]]:
        document_fetcher = DocumentFetcher()
        fetched_ids = set()
        timestamp_processed_values = []
        for key in self.redis.scan_iter(f"{settings.redis_document_prefix}:*"):
            logger.debug("Fetched key: %s", key)
            components = key.split(":")
            if len(components) != 3:
                logger.info("Invalid key: %s", key)
                continue

            timestamp = int(components[1])
            if timestamp < start_timestamp:
                continue

            _id = components[2]
            # Avoid fetching the same ID repeatedly
            if _id in fetched_ids:
                continue
            fetched_ids.add(_id)
            document = document_fetcher.get(_id)
            if not document:
                logger.info("Unable to retrieve document: %s", _id)
                continue

            timestamp_processed_values.append((timestamp, document))

        # Sort by timestamp
        timestamp_processed_values.sort(key=lambda x: x[0])
        return timestamp_processed_values


class DocumentFetcher:
    def __init__(self):
        self.server_url = settings.openfoodfacts_base_url

    def get(self, code):
        url = f"{self.server_url}/api/v2/product/{code}"
        response = http_session.get(url)
        json_response = response.json()
        if not json_response or not json_response.get("product"):
            return None
        return json_response["product"]


class QueueManager:
    def __init__(self, config: Config):
        self.stop_received = False
        self.redis_client = RedisClient()
        self.document_fetcher = DocumentFetcher()
        self.es_client = get_es_client()
        self.processor = DocumentProcessor(config)

        self.index_name = config.index.name

    def consume(self):
        while not self.stop_received:
            _id = self.redis_client.get_from_queue()
            if not _id:
                continue
            item = self.document_fetcher.get(_id)
            if not item:
                logger.info("Unable to retrieve document with ID %s", _id)
                continue
            # As the _id is unique, this will handle updates as well as new
            # documents
            document = self.processor.from_dict(item)
            _id = document.pop("_id")
            logger.info(document)
            logger.info(self.index_name)
            result = self.es_client.index(
                index=self.index_name, document=document, id=_id
            )
            logger.info(
                "Received Redis update for document: %s, indexation result: %s",
                _id,
                result,
            )
            # Now, write a key that can be read for full imports
            self.redis_client.write_processed(_id)

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
