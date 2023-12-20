import abc
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path
from typing import Iterator, cast

import tqdm
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, parallel_bulk
from elasticsearch_dsl import Index, Search
from redis import Redis

from app._types import JSONType
from app.config import Config, TaxonomyConfig, settings
from app.indexing import (
    DocumentProcessor,
    generate_index_object,
    generate_taxonomy_index_object,
)
from app.taxonomy import get_taxonomy
from app.utils import connection, get_logger, load_class_object_from_string
from app.utils.io import jsonl_iter

logger = get_logger(__name__)


class BaseDocumentFetcher(abc.ABC):
    def __init__(self, config: Config) -> None:
        self.config = config

    @abc.abstractmethod
    def fetch_document(self, stream_name: str, item: JSONType) -> JSONType | None:
        """Fetch a document using elements coming from a Redis stream.

        The Redis stream contains information about documents that were
        updated. This method must be overridden to fetch the full document
        using the information from the stream, and return it.

        :param stream_name: the name of the Redis stream
        :param item: the item from the Redis stream
        """
        pass


def load_document_fetcher(config: Config) -> BaseDocumentFetcher:
    """Load the document fetcher class from the config.

    :param config: the config object
    :return: the initialized document fetcher
    """
    fetcher_cls = load_class_object_from_string(config.document_fetcher)
    return fetcher_cls(config)


def get_processed_since(
    redis_client: Redis,
    start_timestamp_ms: int,
    id_field_name: str,
    document_fetcher: BaseDocumentFetcher,
    batch_size: int = 100,
) -> Iterator[tuple[int, JSONType]]:
    """Fetches all the documents that have been processed since the given
    timestamp.

    :param redis_client: the Redis client
    :param start_timestamp_ms: the timestamp to start from, in milliseconds
    :param id_field_name: the name of the field containing the ID
    :param document_fetcher: the document fetcher
    :param batch_size: the size of the batch to fetch, defaults to 100
    :yield: a tuple containing the timestamp (in milliseconds) and the document
    """
    stream_name = settings.redis_import_stream_name
    fetched_ids = set()
    # We start from the given timestamp
    min_id = f"{start_timestamp_ms}-0"

    while True:
        batch = redis_client.xrange(stream_name, min=min_id, count=batch_size)
        if not batch:
            # We reached the end of the stream
            break

        batch = cast(list[tuple[str, dict]], batch)
        # We update the min_id to the last ID of the batch
        min_id = f"({batch[-1][0]}"
        for timestamp_id, item in batch:
            id_ = item[id_field_name]
            logger.debug("Fetched ID: %s", id_)
            # Get the timestamp from the ID
            timestamp = int(timestamp_id.split("-")[0])
            # Avoid fetching the same ID repeatedly
            if id_ in fetched_ids:
                continue
            fetched_ids.add(id_)
            document = document_fetcher.fetch_document(stream_name, item)
            if document is None:
                continue
            yield timestamp, document


def get_new_updates(
    redis_client: Redis,
    id_field_name: str,
    document_fetcher: BaseDocumentFetcher,
    batch_size: int = 100,
):
    """Reads new updates from Redis Stream, starting from the moment this
    function is called.

    The function will block until new updates are available.

    :param redis_client: the Redis client
    :param id_field_name: the name of the field containing the ID
    :param document_fetcher: the document fetcher
    :param batch_size: the size of the batch to fetch, defaults to 100.
    :yield: a tuple containing the timestamp (in milliseconds) and the document
    """
    stream_name = settings.redis_import_stream_name
    # We start from the last ID
    min_id = "$"
    while True:
        logger.debug(
            "Listening to new updates from stream %s (ID: %s)", stream_name, min_id
        )
        # We use block=0 to wait indefinitely for new updates
        response = redis_client.xread({stream_name: min_id}, block=0, count=batch_size)
        response = cast(list[tuple[str, list[tuple[str, dict]]]], response)
        # We only have one stream, so we only have one response
        # The response is a list of tuples (stream_name, batch)
        _, batch = response[0]
        # We update the min_id to the last ID of the batch
        min_id = batch[-1][0]
        for timestamp_id, item in batch:
            id_ = item[id_field_name]
            logger.debug("Fetched ID: %s", id_)
            # Get the timestamp from the ID
            timestamp = int(timestamp_id.split("-")[0])
            document = document_fetcher.fetch_document(stream_name, item)
            if document is None:
                continue
            yield timestamp, document


def get_document_dict(
    processor: DocumentProcessor, row: JSONType, next_index: str
) -> JSONType | None:
    """Return the document dict suitable for a bulk insert operation."""
    document = processor.from_dict(row)
    if not document:
        return None

    _id = document.pop("_id")
    return {"_source": document, "_index": next_index, "_id": _id}


def gen_documents(
    processor: DocumentProcessor,
    file_path: Path,
    next_index: str,
    num_items: int | None,
    num_processes: int,
    process_id: int,
):
    """Generate documents to index for process number process_id

    We chunk documents based on document num % process_id
    """
    for i, row in enumerate(tqdm.tqdm(jsonl_iter(file_path))):
        if num_items is not None and i >= num_items:
            break
        # Only get the relevant
        if i % num_processes != process_id:
            continue

        document_dict = get_document_dict(processor, row, next_index)
        if not document_dict:
            continue

        yield document_dict


def gen_taxonomy_documents(
    taxonomy_config: TaxonomyConfig, next_index: str, supported_langs: set[str]
):
    """Generator for taxonomy documents in Elasticsearch.

    :param taxonomy_config: the taxonomy configuration
    :param next_index: the index to write to
    :param supported_langs: a set of supported languages
    :yield: a dict with the document to index, compatible with ES bulk API
    """
    for taxonomy_source_config in tqdm.tqdm(taxonomy_config.sources):
        taxonomy = get_taxonomy(
            taxonomy_source_config.name, str(taxonomy_source_config.url)
        )
        for node in taxonomy.iter_nodes():
            names = {}
            for lang in supported_langs:
                lang_names = set()
                if lang in node.names:
                    lang_names.add(node.names[lang])
                if lang in node.synonyms:
                    lang_names |= set(node.synonyms[lang])
                names[lang] = list(lang_names)

            yield {
                "_index": next_index,
                "_source": {
                    "id": node.id,
                    "taxonomy_name": taxonomy_source_config.name,
                    "names": names,
                },
            }


def update_alias(es_client: Elasticsearch, next_index: str, index_alias: str):
    """Point the alias to the newly created index.

    :param es_client: the Elasticsearch client
    :param next_index: the index to point to
    :param index_alias: the alias to update
    """
    es_client.indices.update_aliases(
        body={
            "actions": [
                {
                    "remove": {
                        "alias": index_alias,
                        "index": f"{index_alias}-*",
                    },
                },
                {"add": {"alias": index_alias, "index": next_index}},
            ],
        },
    )


def import_parallel(
    config: Config,
    file_path: Path,
    next_index: str,
    num_items: int | None,
    num_processes: int,
    process_id: int,
):
    """One task of import.

    :param Path file_path: the JSONL file to read
    :param str next_index: the index to write to
    :param int num_items: max number of items to import, default to no limit
    :param int num_processes: total number of processes
    :param int process_id: the index of the process
        (from 0 to num_processes - 1)
    """
    processor = DocumentProcessor(config)
    # open a connection for this process
    es = connection.get_es_client(timeout=120, retry_on_timeout=True)
    # Note that bulk works better than parallel bulk for our usecase.
    # The preprocessing in this file is non-trivial, so it's better to
    # parallelize that. If we then do parallel_bulk here, this causes queueing
    # and a lot of memory usage in the importer process.
    success, errors = bulk(
        es,
        gen_documents(
            processor,
            file_path,
            next_index,
            num_items,
            num_processes,
            process_id,
        ),
        raise_on_error=False,
    )
    if not success:
        logger.error("Encountered errors: %s", errors)


def import_taxonomies(config: Config, next_index: str):
    """Import taxonomies into Elasticsearch.

    A single taxonomy index is used to store all taxonomy items.

    :param config: the configuration to use
    :param next_index: the index to write to
    """
    # open a connection for this process
    es = connection.get_es_client(timeout=120, retry_on_timeout=True)
    # Note that bulk works better than parallel bulk for our usecase.
    # The preprocessing in this file is non-trivial, so it's better to
    # parallelize that. If we then do parallel_bulk
    # here, this causes queueing and a lot of memory usage in the importer
    # process.
    success, errors = bulk(
        es,
        gen_taxonomy_documents(
            config.taxonomy, next_index, supported_langs=set(config.supported_langs)
        ),
        raise_on_error=False,
    )
    if not success:
        logger.error("Encountered errors: %s", errors)


def get_redis_products(
    processor: DocumentProcessor,
    fetcher: BaseDocumentFetcher,
    index: str,
    id_field_name: str,
    last_updated_timestamp_ms: int,
):
    """Fetch IDs of documents to update from Redis.

    :param processor: the document processor to use to process the documents
    :param fetcher: the document fetcher to use to fetch the documents from
        the document ID
    :param index: the index to write to
    :param id_field_name: the name of the ID field in the document
    :param last_updated_timestamp_ms: the timestamp of the last update in ms
    """
    logger.info("Processing redis updates since %s", last_updated_timestamp_ms)
    redis_client = connection.get_redis_client()
    processed = 0
    for _, row in get_processed_since(
        redis_client,
        last_updated_timestamp_ms,
        id_field_name,
        document_fetcher=fetcher,
    ):
        yield get_document_dict(processor, row, index)
        processed += 1
    logger.info("Processed %d updates from Redis", processed)


def get_redis_updates(es_client: Elasticsearch, index: str, config: Config):
    """Fetch updates from Redis and index them.

    :param index: the index to write to
    :param config: the configuration to use
    """
    processor = DocumentProcessor(config)
    fetcher = load_document_fetcher(config)
    # Ensure all documents are searchable after the import
    Index(index, using=es_client).refresh()
    last_modified_field_name = config.index.last_modified_field_name
    query = (
        Search(index=index, using=es_client)
        .sort(f"-{last_modified_field_name}")
        .extra(size=1)
    )
    # Note that we can't use index() because we don't want to also query the
    # main alias
    query._index = [index]
    results = query.execute()
    results_dict = [r.to_dict() for r in results]
    last_updated_timestamp: int | float = results_dict[0][last_modified_field_name]
    last_updated_timestamp_ms = int(last_updated_timestamp * 1000)
    id_field_name = config.index.id_field_name
    # Since this is only done by a single process, we can use parallel_bulk
    for success, info in parallel_bulk(
        es_client,
        get_redis_products(
            processor, fetcher, index, id_field_name, last_updated_timestamp_ms
        ),
    ):
        if not success:
            logger.warning("A document failed: %s", info)


def run_full_import(
    file_path: Path,
    num_processes: int,
    config: Config,
    num_items: int | None = None,
):
    """Run a full data import from a JSONL.

    A temporary index is created, and documents are imported into it.
    We then read from the Redis stream containing information about updated
    documents, fetch the full document and index it in Elasticsearch. The
    import is done in parallel using multiple processes. Once the import is
    finished, the alias is updated to point to the new index.

    :param file_path: the path of the JSONL file to import
    :param num_processes: the number of processes to use to perform parallel
        import
    :param config: the configuration to use
    :param num_items: the number of items to import, defaults to None (all)
    """
    es_client = connection.get_es_client()
    # we create a temporary index to import to
    # at the end we will change alias to point to it
    index_date = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
    next_index = f"{config.index.name}-{index_date}"

    index = generate_index_object(next_index, config)
    # create the index
    index.save()

    # split the work between processes
    args = []
    for i in range(num_processes):
        args.append(
            (
                config,
                file_path,
                next_index,
                num_items,
                num_processes,
                i,
            )
        )
    # run in parallel
    with Pool(num_processes) as pool:
        pool.starmap(import_parallel, args)
    # update with last index updates (hopefully since the jsonl)
    get_redis_updates(es_client, next_index, config)
    # make alias point to new index
    update_alias(es_client, next_index, config.index.name)


def perform_taxonomy_import(config: Config) -> None:
    """Create a new index for taxonomies and import them.

    :param config: the configuration to use
    """
    es_client = connection.get_es_client()
    # we create a temporary index to import to
    # at the end we will change alias to point to it
    index_date = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
    next_index = f"{config.taxonomy.index.name}-{index_date}"

    index = generate_taxonomy_index_object(next_index, config)
    # create the index
    index.save()

    import_taxonomies(config, next_index)

    # make alias point to new index
    update_alias(es_client, next_index, config.taxonomy.index.name)


def run_update_daemon(config: Config) -> None:
    """Run the update import daemon.

    This daemon listens to the Redis stream containing information about
    updated documents, fetches the full document and indexes it in
    Elasticsearch.

    :param config: the configuration to use
    """
    logger.info("Starting update import daemon")
    es_client = connection.get_es_client()
    redis_client = connection.get_redis_client()
    document_fetcher = load_document_fetcher(config)
    processor = DocumentProcessor(config)

    for _, document in get_new_updates(
        redis_client,
        config.index.id_field_name,
        document_fetcher,
    ):
        document = processor.from_dict(document)
        if not document:
            continue
        _id = document.pop("_id")
        es_client.index(
            index=config.index.name,
            body=document,
            id=_id,
        )
