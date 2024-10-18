import abc
import math
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path
from typing import Iterator, cast

import tqdm
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, parallel_bulk
from elasticsearch_dsl import Index, Search
from redis import Redis

from app._types import FetcherResult, FetcherStatus, JSONType
from app.config import Config, IndexConfig, TaxonomyConfig, settings
from app.indexing import (
    DocumentProcessor,
    generate_index_object,
    generate_taxonomy_index_object,
)
from app.taxonomy import iter_taxonomies
from app.taxonomy_es import refresh_synonyms
from app.utils import connection, get_logger, load_class_object_from_string
from app.utils.io import jsonl_iter

logger = get_logger(__name__)


class BaseDocumentFetcher(abc.ABC):
    def __init__(self, config: IndexConfig) -> None:
        self.config = config

    @abc.abstractmethod
    def fetch_document(self, stream_name: str, item: JSONType) -> FetcherResult:
        """Fetch a document using elements coming from a Redis stream.

        The Redis stream contains information about documents that were
        updated. This method must be overridden to fetch the full document
        using the information from the stream, and return it.

        :param stream_name: the name of the Redis stream
        :param item: the item from the Redis stream
        :return: the fetched document and a status that will pilot the action to be done
        """
        pass


def load_document_fetcher(config: IndexConfig) -> BaseDocumentFetcher:
    """Load the document fetcher class from the config.

    :param config: the index configuration to use
    :return: the initialized document fetcher
    """
    fetcher_cls = load_class_object_from_string(config.document_fetcher)
    return fetcher_cls(config)


def get_processed_since(
    redis_client: Redis,
    redis_stream_name: str,
    start_timestamp_ms: int,
    id_field_name: str,
    document_fetcher: BaseDocumentFetcher,
    batch_size: int = 100,
) -> Iterator[tuple[int, FetcherResult]]:
    """Fetches all the documents that have been processed since the given
    timestamp (using redis event stream).

    :param redis_client: the Redis client
    :param redis_stream_name: the name of the Redis stream to read from
    :param start_timestamp_ms: the timestamp to start from, in milliseconds
    :param id_field_name: the name of the field containing the ID
    :param document_fetcher: the document fetcher
    :param batch_size: the size of the batch to fetch, defaults to 100
    :yield: a tuple containing the timestamp (in milliseconds) and the document
    """
    # store fetched ids with a timestamp
    fetched_ids: dict[str, int] = {}
    # We start from the given timestamp
    min_id = f"{start_timestamp_ms}-0"

    while True:
        logger.debug(
            "Fetching batch from Redis, stream %s, min_id %s, count %d",
            redis_stream_name,
            min_id,
            batch_size,
        )
        batch = redis_client.xrange(redis_stream_name, min=min_id, count=batch_size)
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
            if id_ in fetched_ids and fetched_ids[id_] > timestamp:
                logger.debug(f"Skipping ID {id_} because it was already fetched")
                continue
            # use current timestamp
            # as a pessimistic timestamp of last index update
            # *1000 because python timestamp are in seconds,
            # redis in milliseconds
            fetched_ids[id_] = math.floor(datetime.now().timestamp() * 1000)
            result = document_fetcher.fetch_document(redis_stream_name, item)
            if result.status == FetcherStatus.SKIP:
                logger.debug(f"Skipping ID {id_} because fetches stated to do so")
            elif result.status == FetcherStatus.RETRY:
                logger.warn(
                    f"Should retry ID {id_} due to status RETRY, but it's not yet implemented !"
                )
            elif result.status == FetcherStatus.REMOVED:
                yield timestamp, result
            elif result.status == FetcherStatus.FOUND:
                if result.document is None:
                    logger.error(
                        f"Document is None for ID {id_}, while status is FOUND !"
                    )
                else:
                    yield timestamp, result
            else:
                logger.debug(f"Skipping ID {id_} due to status {result.status.name}")


def get_new_updates(
    redis_client: Redis,
    stream_names: list[str],
    id_field_names: dict[str, str],
    document_fetchers: dict[str, BaseDocumentFetcher],
    batch_size: int = 100,
) -> Iterator[tuple[str, int, FetcherResult]]:
    """Reads new updates from Redis Stream, starting from the moment this
    function is called.

    The function will block until new updates are available.

    :param redis_client: the Redis client
    :param stream_names: the names of the Redis streams to read from
    :param id_field_names: the name of the field containing the ID for each
        stream
    :param document_fetchers: the document fetcher for each stream
    :param batch_size: the size of the batch to fetch, defaults to 100.
    :yield: a tuple containing the stream name, the timestamp (in
        milliseconds) and the document
    """
    # We start from the last ID
    min_ids: dict[bytes | str | memoryview, int | bytes | str | memoryview] = {
        stream_name: "$" for stream_name in stream_names
    }
    while True:
        logger.debug(
            "Listening to new updates from streams %s (ID: %s)", stream_names, min_ids
        )
        # We use block=0 to wait indefinitely for new updates
        response = redis_client.xread(streams=min_ids, block=0, count=batch_size)
        response = cast(list[tuple[str, list[tuple[str, dict]]]], response)
        # The response is a list of tuples (stream_name, batch)

        for stream_name, batch in response:
            # We update the min_id to the last ID of the batch
            min_id = batch[-1][0]
            min_ids[stream_name] = min_id
            id_field_name = id_field_names[stream_name]
            document_fetcher = document_fetchers[stream_name]
            for timestamp_id, item in batch:
                id_ = item[id_field_name]
                logger.debug("Fetched ID: %s", id_)
                # Get the timestamp from the ID
                timestamp = int(timestamp_id.split("-")[0])
                result = document_fetcher.fetch_document(stream_name, item)
                if result.status == FetcherStatus.SKIP:
                    logger.debug(
                        f"Skipping ID {id_}  in {stream_name} because fetches stated to do so"
                    )
                elif result.status == FetcherStatus.RETRY:
                    logger.warn(
                        f"Should retry ID {id_}  in {stream_name} due to status RETRY, "
                        "but it's not yet implemented !"
                    )
                elif result.status == FetcherStatus.REMOVED:
                    yield stream_name, timestamp, result
                elif result.status == FetcherStatus.FOUND:
                    if result.document is None:
                        logger.error(
                            f"Document is None for ID {id_} in {stream_name}, while status is FOUND !"
                        )
                    else:
                        yield stream_name, timestamp, result
                else:
                    logger.debug(
                        f"Skipping ID {id_} in {stream_name} due to status {result.status.name}"
                    )


def get_document_dict(
    processor: DocumentProcessor, result: FetcherResult, index_name: str
) -> JSONType | None:
    """Return the document dict suitable for a bulk insert operation."""
    if result.document is None:
        return None
    result = processor.from_result(result)
    document = result.document
    if not document:
        return None
    elif result.status == FetcherStatus.FOUND:
        _id = document.pop("_id")
        return {"_source": document, "_index": index_name, "_id": _id}
    elif result.status == FetcherStatus.REMOVED:
        return {
            "_op_type": "delete",
            "_index": index_name,
            "_id": document["_id"],
        }
    else:
        return None


def gen_documents(
    processor: DocumentProcessor,
    file_path: Path,
    next_index: str,
    num_items: int | None,
    num_processes: int,
    process_num: int,
):
    """Generate documents to index for process number process_num

    We chunk documents based on document num % process_num
    """
    for i, row in enumerate(tqdm.tqdm(jsonl_iter(file_path))):
        if num_items is not None and i >= num_items:
            break
        # Only get the relevant
        if i % num_processes != process_num:
            continue

        document_dict = get_document_dict(
            processor,
            FetcherResult(status=FetcherStatus.FOUND, document=row),
            next_index,
        )
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
    for taxonomy_name, taxonomy in tqdm.tqdm(iter_taxonomies(taxonomy_config)):
        for node in taxonomy.iter_nodes():
            names = {
                lang: lang_names
                for lang, lang_names in node.names.items()
                if lang in supported_langs
            }
            synonyms = {
                lang: lang_names
                for lang, lang_names in node.synonyms.items()
                if lang in supported_langs
            }

            yield {
                "_index": next_index,
                "_source": {
                    "id": node.id,
                    "taxonomy_name": taxonomy_name,
                    "name": names,
                    "synonyms": synonyms,
                },
            }


def update_alias(es_client: Elasticsearch, next_index: str, index_alias: str):
    """Point the alias to the newly created index.

    :param es_client: the Elasticsearch client
    :param next_index: the index to point to
    :param index_alias: the alias to update
    """
    es_client.indices.update_aliases(
        actions=[
            {
                "remove": {
                    "alias": index_alias,
                    "index": f"{index_alias}-*",
                }
            },
            {"add": {"alias": index_alias, "index": next_index}},
        ]
    )


def get_alias(es_client: Elasticsearch, index_name: str):
    """Get the current index pointed by the alias."""
    resp = es_client.indices.get_alias(name=index_name)
    resp = list(resp.keys())
    if len(resp) == 0:
        return None
    return resp[0]


def import_parallel(
    config: IndexConfig,
    file_path: Path,
    next_index: str,
    num_items: int | None,
    num_processes: int,
    process_num: int,
):
    """One task of import.

    :param Path file_path: the JSONL file to read
    :param str next_index: the index to write to
    :param int num_items: max number of items to import, default to no limit
    :param int num_processes: total number of processes
    :param int process_num: the index of the process
        (from 0 to num_processes - 1)
    """
    processor = DocumentProcessor(config)
    # open a connection for this process
    es = connection.get_es_client(request_timeout=120, retry_on_timeout=True)
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
            process_num,
        ),
        raise_on_error=False,
    )
    return process_num, success, errors


def import_taxonomies(config: IndexConfig, next_index: str):
    """Import taxonomies into Elasticsearch.

    A single taxonomy index is used to store all taxonomy items.

    :param config: the index configuration to use
    :param next_index: the index to write to
    """
    es = connection.current_es_client()
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
    stream_name: str,
    processor: DocumentProcessor,
    fetcher: BaseDocumentFetcher,
    index: str,
    id_field_name: str,
    last_updated_timestamp_ms: int,
):
    """Fetch IDs of documents to update from Redis.

    :param stream_name: the name of the Redis stream to read from
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
    for _, result in get_processed_since(
        redis_client,
        stream_name,
        last_updated_timestamp_ms,
        id_field_name,
        document_fetcher=fetcher,
    ):
        document_dict = get_document_dict(processor, result, index)
        if document_dict:
            yield document_dict
        processed += 1
    logger.info("Processed %d updates from Redis", processed)


def get_redis_updates(es_client: Elasticsearch, index: str, config: IndexConfig) -> int:
    """Fetch updates from Redis and index them.

    :param index: the index to write to
    :param config: the index configuration to use
    :return: the number of errors encountered
    """
    if config.redis_stream_name is None:
        logger.info(f"Redis updates are disabled for index {index}")
        return 0

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
    num_errors = 0
    for success, info in parallel_bulk(
        es_client,
        get_redis_products(
            config.redis_stream_name,
            processor,
            fetcher,
            index,
            id_field_name,
            last_updated_timestamp_ms,
        ),
    ):
        if not success:
            logger.warning("A document failed: %s", info)
            num_errors += 1
    return num_errors


def run_items_import(
    file_path: Path,
    num_processes: int,
    config: IndexConfig,
    num_items: int | None = None,
    skip_updates: bool = False,
    partial: bool = False,
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
    :param config: the index configuration to use
    :param num_items: the number of items to import, defaults to None (all)
    :param skip_updates: if True, skip the updates from Redis
    :param partial: (exclusive with `skip_updates`),
      if True consider we don't have a full import,
      and directly updates items in current index.
    """
    # we need a large timeout as index creation can take a while because of synonyms
    es_client = connection.get_es_client(request_timeout=600)
    if not partial:
        # we create a temporary index to import to
        # at the end we will change alias to point to it
        index_date = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
        next_index = f"{config.index.name}-{index_date}"
        index = generate_index_object(next_index, config)
        # create the index
        index.save(using=es_client)
    else:
        # use current index
        next_index = config.index.name

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
    num_errors = 0
    with Pool(num_processes) as pool:
        for i, success, errors in pool.starmap(import_parallel, args):
            # Note: we log here instead of in sub-process because
            # it's easier to avoid mixing logs, and it works better for pytest
            logger.info("[%d] Indexed %d documents", i, success)
            if errors:
                logger.error("[%d] Encountered %d errors: %s", i, len(errors), errors)
                num_errors += len(errors)
    # update with last index updates (hopefully since the jsonl)
    if not skip_updates:
        num_errors += get_redis_updates(es_client, next_index, config)
    # wait for index refresh
    es_client.indices.refresh(index=next_index)
    if not partial:
        # make alias point to new index
        update_alias(es_client, next_index, config.index.name)
    return num_errors


def perform_taxonomy_import(config: IndexConfig) -> None:
    """Create a new index for taxonomies and import them.

    :param config: the index configuration to use
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
    # wait for index refresh
    es_client.indices.refresh(index=next_index)

    # make alias point to new index
    update_alias(es_client, next_index, config.taxonomy.index.name)


def perform_cleanup_indexes(config: IndexConfig) -> int:
    """Delete old indexes (that have no active alias on them)."""
    removed = 0
    # some timeout for it can be long
    es_client = connection.get_es_client(request_timeout=600)
    prefixes = [config.index.name, config.taxonomy.index.name]
    for prefix in prefixes:
        # get all indexes
        indexes = es_client.indices.get_alias(index=f"{prefix}-*")
        # remove all index without alias
        to_remove = [
            index for index, data in indexes.items() if not data.get("aliases")
        ]
        for index in to_remove:
            logger.info("Deleting index %s", index)
            es_client.indices.delete(index=index)
            removed += 1
    return removed


def perform_refresh_synonyms(index_id: str, config: IndexConfig) -> None:
    """Refresh synonyms files generated by taxonomies."""
    refresh_synonyms(index_id, config, settings.synonyms_path)


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

    if redis_client.ping():
        logger.info("Connected to Redis")
    else:
        logger.error("Could not connect to Redis")
        return

    if len(list(config.indices)) != 1:
        raise ValueError("Only one index is supported")

    processors: dict[str, DocumentProcessor] = {}
    document_fetchers: dict[str, BaseDocumentFetcher] = {}
    id_field_names: dict[str, str] = {}
    stream_name_to_index_id: dict[str, str] = {}

    for index_id, index_config in config.indices.items():
        stream_name = index_config.redis_stream_name
        if stream_name is not None:
            processors[stream_name] = DocumentProcessor(index_config)
            document_fetchers[stream_name] = load_document_fetcher(index_config)
            id_field_names[stream_name] = index_config.index.id_field_name
            stream_name_to_index_id[stream_name] = index_id

    for stream_name, _, result in get_new_updates(
        redis_client,
        list(id_field_names.keys()),
        id_field_names=id_field_names,
        document_fetchers=document_fetchers,
    ):
        processed_result = processors[stream_name].from_result(result)
        processed_document = processed_result.document
        if (
            processed_result.status not in (FetcherStatus.FOUND, FetcherStatus.REMOVED)
            or processed_document is None
        ):
            continue
        _id = processed_document.pop("_id")
        index_id = stream_name_to_index_id[stream_name]
        logger.debug("Document:\n%s", processed_document)
        if processed_result.status == FetcherStatus.REMOVED:
            es_client.delete(
                index=config.indices[index_id].index.name,
                id=_id,
            )
        else:
            es_client.index(
                index=config.indices[index_id].index.name,
                body=processed_document,
                id=_id,
            )
