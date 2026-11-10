import abc
import math
import random
import signal
import threading
from datetime import datetime
from inspect import cleandoc as cd_
from multiprocessing import Pool
from pathlib import Path
from typing import Callable, Iterator, List, Tuple, cast

import tqdm
from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.exceptions import ApiError, ConflictError
from elasticsearch.exceptions import ConnectionError as ESConnectionError
from elasticsearch.exceptions import TransportError
from elasticsearch.helpers import bulk, parallel_bulk
from elasticsearch_dsl import Index
from redis import Redis
from redis.exceptions import BusyLoadingError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app._types import FetcherResult, FetcherStatus, JSONType
from app.checkpoints import (
    get_checkpoint,
    get_last_indexed_timestamp_ms,
    set_checkpoint,
    stream_id_from_timestamp_ms,
)
from app.config import Config, IndexConfig, settings
from app.exceptions import TooManySynonymsSetsException
from app.indexing import (
    BaseTaxonomyPreprocessor,
    DocumentProcessor,
    generate_index_object,
    generate_taxonomy_index_object,
    wait_index_health,
)
from app.taxonomy import iter_taxonomies
from app.taxonomy_es import check_synonyms_sets_size, refresh_synonyms
from app.utils import connection, get_logger, load_class_object_from_string
from app.utils.io import jsonl_iter

logger = get_logger(__name__)

# Retry policy for transient errors in the update daemon.
# The delay starts at RETRY_INITIAL_DELAY seconds, doubles after each attempt
# and is capped at RETRY_MAX_DELAY seconds, with a +-RETRY_JITTER relative
# random variation to avoid synchronized retries.
RETRY_INITIAL_DELAY = 1.0
RETRY_MAX_DELAY = 60.0
RETRY_JITTER = 0.2

# HTTP statuses that mean "the cluster is temporarily unable to serve this
# request" (rate limiting, shard/node unavailable, gateway timeouts).
RETRYABLE_HTTP_STATUSES = frozenset({429, 502, 503, 504})


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
                logger.warning(
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
    min_ids: dict[str, str] | None = None,
    batch_size: int = 100,
    stop_event: threading.Event | None = None,
) -> Iterator[tuple[str, int, str, FetcherResult]]:
    """Reads new updates from Redis Stream, starting from the given positions.

    The function reads the stream in batches, and returns whenever there are
    no new updates for a while (see ``settings.redis_reader_timeout``), so that
    the caller can check its ``stop_event``.

    The stream cursor is only advanced in memory here: it is the caller's
    responsibility to persist the ID of the last *handled* event (see
    :func:`app.checkpoints.set_checkpoint`), so that a crash does not lose the
    events that were read but not processed yet. The in-memory cursor is what
    makes the generator move forward within a session.

    :param redis_client: the Redis client
    :param stream_names: the names of the Redis streams to read from
    :param id_field_names: the name of the field containing the ID for each
        stream
    :param document_fetchers: the document fetcher for each stream
    :param min_ids: the stream ID to start reading from, for each stream.
        Defaults to ``"$"`` (only new events) for streams not specified.
    :param batch_size: the size of the batch to fetch, defaults to 100.
    :param stop_event: if provided, the generator returns when this event is
        set (checked after each batch and each read timeout).
    :yield: a tuple containing the stream name, the timestamp (in
        milliseconds), the stream ID and the document
    """
    # We start from the last ID, or from "$" (only new events) if unknown.
    min_ids = {
        stream_name: (min_ids or {}).get(stream_name, "$")
        for stream_name in stream_names
    }
    # redis-py expects the block timeout in milliseconds,
    # settings.redis_reader_timeout is in seconds.
    block_ms = int(settings.redis_reader_timeout * 1000)
    while not (stop_event is not None and stop_event.is_set()):
        logger.debug(
            "Listening to new updates from streams %s (ID: %s)", stream_names, min_ids
        )
        raw_response = redis_client.xread(
            streams=cast(dict, min_ids), block=block_ms, count=batch_size
        )
        # The response is a list of tuples (stream_name, batch).
        # It is empty when the block timeout expired without any new event.
        response = cast(List[Tuple[str, List[Tuple[str, dict]]]], raw_response)

        for stream_name, batch in response:
            id_field_name = id_field_names[stream_name]
            document_fetcher = document_fetchers[stream_name]
            # Note: the in-memory cursor is advanced *before* yielding an entry,
            # because the caller may rebuild the generator after an error. The
            # caller resets the cursor to the last persisted checkpoint when it
            # does so, which is what guarantees that no entry is skipped.
            for timestamp_id, item in batch:
                min_ids[stream_name] = f"({timestamp_id}"
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
                    logger.warning(
                        f"Should retry ID {id_}  in {stream_name} due to status RETRY, "
                        "but it's not yet implemented !"
                    )
                elif result.status == FetcherStatus.REMOVED:
                    yield stream_name, timestamp, timestamp_id, result
                elif result.status == FetcherStatus.FOUND:
                    if result.document is None:
                        logger.error(
                            f"Document is None for ID {id_} in {stream_name}, while status is FOUND !"
                        )
                    else:
                        yield stream_name, timestamp, timestamp_id, result
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
    gen_document_errors: list[Exception] | None = None,
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

        try:
            document_dict = get_document_dict(
                processor,
                FetcherResult(status=FetcherStatus.FOUND, document=row),
                next_index,
            )
        except Exception as e:
            if gen_document_errors is not None:
                gen_document_errors.append(e)
            continue
        if not document_dict:
            continue
        yield document_dict


def gen_taxonomy_documents(
    config: IndexConfig, next_index: str, supported_langs: set[str]
):
    """Generator for taxonomy documents in Elasticsearch.

    :param taxonomy_config: the taxonomy configuration
    :param next_index: the index to write to
    :param supported_langs: a set of supported languages
    :yield: a dict with the document to index, compatible with ES bulk API
    """
    taxonomy_config = config.taxonomy
    preprocessor: BaseTaxonomyPreprocessor | None = None
    if taxonomy_config.preprocessor:
        preprocessor_cls = load_class_object_from_string(taxonomy_config.preprocessor)
        preprocessor = preprocessor_cls(config)
    for taxonomy in tqdm.tqdm(iter_taxonomies(taxonomy_config)):
        for node in taxonomy.iter_nodes():
            if preprocessor:
                result = preprocessor.preprocess(taxonomy, node)
                if result.status != FetcherStatus.FOUND or result.node is None:
                    continue  # skip this entry
                node = result.node
            names = {
                lang: lang_name
                for lang, lang_name in node.names.items()
                if lang in supported_langs and lang_name
            }
            synonyms: dict[str, set[str]] = {
                lang: set(node.synonyms.get(lang) or [])
                for lang in node.synonyms
                if lang in supported_langs
            }
            for lang, lang_name in names.items():
                if lang_name:
                    synonyms.setdefault(lang, set()).add(lang_name)
            # put the name as first synonym and order  by length
            synonyms_list: dict[str, list[str]] = {}
            for lang, lang_synonyms in synonyms.items():
                filtered_synonyms = filter(lambda s: s, lang_synonyms)
                synonyms_list[lang] = sorted(
                    filtered_synonyms,
                    key=lambda s: 0 if s == names.get(lang) else len(s),
                )
            yield {
                "_index": next_index,
                "_source": {
                    "id": node.id,
                    "taxonomy_name": taxonomy.name,
                    "name": names,
                    "synonyms": {
                        lang: {
                            "input": lang_synonyms,
                            "weight": max(100 - len(node.id), 0),
                        }
                        for lang, lang_synonyms in synonyms_list.items()
                    },
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
    # a list of errors that occurs during document generation
    gen_document_errors: list[Exception] = []
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
            gen_document_errors,
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
            config, next_index, supported_langs=set(config.supported_langs)
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
    errors: list[Exception] | None = None,
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
        try:
            document_dict = get_document_dict(processor, result, index)
            if document_dict:
                yield document_dict
        except Exception as e:
            if errors is not None:
                errors.append(e)
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
    last_updated_timestamp_ms = get_last_indexed_timestamp_ms(
        es_client, index, config.index.last_modified_field_name
    )
    if last_updated_timestamp_ms is None:
        # Nothing says from where to catch up. Skipping would silently lose the
        # updates since the dump, and the alias would then point to this index.
        raise RuntimeError(
            f"Cannot catch up on Redis updates: no document with a "
            f"{config.index.last_modified_field_name} in index {index} "
            "(is the import empty?). "
            "Use --skip-updates to import without them."
        )
    id_field_name = config.index.id_field_name
    # Since this is only done by a single process, we can use parallel_bulk
    num_errors = 0
    document_gen_errors: list[Exception] = []
    for success, info in parallel_bulk(
        es_client,
        get_redis_products(
            config.redis_stream_name,
            processor,
            fetcher,
            index,
            id_field_name,
            last_updated_timestamp_ms,
            document_gen_errors,
        ),
        # a product created then deleted after the dump is absent from the index
        ignore_status=404,
    ):
        if not success:
            if "delete" in info and info["delete"].get("status") == 404:
                # nothing to remove, not an error
                continue
            logger.warning("A document failed: %s", info)
            num_errors += 1
    for error in document_gen_errors:
        logger.error("A document failed: %s", error)
    num_errors += len(document_gen_errors)
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
        # create the index, use create method instead of save
        # because it supports additional parameters
        # it can be very long if we have a lot of synonyms to handle
        index.create(using=es_client, timeout="3600s", request_timeout=3600)
        # wait for it to be really available,
        # this can take a lot of time
        # if we have a lot of synonyms
        wait_index_health(es_client, next_index)
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
        if num_processes > 1:
            logger.info("Running in parallel with %d processes", num_processes)
            result_iter = iter(pool.starmap(import_parallel, args))
        else:
            # run sequentially, it's easier to debug if we need it
            # we won't use the pool in this case
            logger.info("Running in a single processes")
            result_iter = iter(map(lambda a: import_parallel(*a), args))
        for i, success, errors in result_iter:
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
    if not skip_updates:
        reset_checkpoint_after_import(es_client, config)
    return num_errors


def reset_checkpoint_after_import(
    es_client: Elasticsearch, config: IndexConfig
) -> None:
    """Move the update daemon checkpoint to the end of the imported data.

    The import already took into account the stream events up to the most
    recent document (see :func:`get_redis_updates`), and the alias now points
    to the new index. Keeping the previous checkpoint would only cause a
    (harmless but wasteful) replay of old events by the daemon.

    This is best effort: a failure here is logged and does not fail the
    import, since a stale checkpoint only leads to a replay.

    :param es_client: the Elasticsearch client
    :param config: the index configuration used for the import
    """
    if config.redis_stream_name is None:
        logger.info("Redis updates are disabled for index %s", config.index.name)
        return
    try:
        last_indexed_ms = get_last_indexed_timestamp_ms(
            es_client, config.index.name, config.index.last_modified_field_name
        )
        if last_indexed_ms is None:
            logger.warning(
                "Index %s is empty, leaving the update checkpoint untouched",
                config.index.name,
            )
            return
        stream_id = stream_id_from_timestamp_ms(last_indexed_ms)
        redis_client = connection.get_redis_client()
        set_checkpoint(
            redis_client, config.redis_stream_name, config.index.name, stream_id
        )
        logger.info(
            "Update checkpoint for stream %s and index %s set to %s",
            config.redis_stream_name,
            config.index.name,
            stream_id,
        )
    except Exception as exc:
        logger.warning("Could not reset the update checkpoint: %s", exc)


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
    refresh_synonyms(index_id, config)
    try:
        check_synonyms_sets_size(config)
    except TooManySynonymsSetsException as e:
        logger.warning(
            cd_(
                """Too many synonyms in some taxonomies: %s
                Consider raising max_synonyms_entries for those taxonomies
                (will require a complete re-index of your data).
                """
            ),
            e,
        )


def is_retryable_error(exc: Exception) -> bool:
    """Tell whether an error is transient and the operation should be retried.

    The check order matters: in elasticsearch-py 8.x, ``NotFoundError`` and
    ``ConflictError`` are subclasses of ``ApiError``, which is itself a
    subclass of ``TransportError``. Subclasses must therefore be tested before
    their parents.

    :param exc: the exception raised
    :return: True if waiting and retrying may succeed
    """
    if isinstance(exc, (NotFoundError, ConflictError)):
        # Document-level errors: retrying the same request will not help.
        return False
    if isinstance(exc, ApiError):
        status = getattr(exc, "status_code", None)
        return status in RETRYABLE_HTTP_STATUSES
    if isinstance(exc, ESConnectionError):
        # Covers TimeoutError and SSLError, which are subclasses
        return True
    if isinstance(exc, TransportError):
        # Status-less transport error (e.g. malformed/unexpected response):
        # usually the cluster is in a bad state, give it a chance to recover.
        return True
    if isinstance(exc, (RedisConnectionError, RedisTimeoutError, BusyLoadingError)):
        return True
    if isinstance(exc, RedisError):
        # Other Redis errors (wrong type, data error...) will not heal by
        # themselves.
        return False
    return False


def retry_delay(attempt: int) -> float:
    """Return the delay to wait before the n-th retry of a transient error.

    The delay is ``RETRY_INITIAL_DELAY`` doubled on each attempt, capped at
    ``RETRY_MAX_DELAY``, with a random jitter of +-``RETRY_JITTER`` (relative)
    so that several processes don't retry at the exact same time.

    :param attempt: the number of retries already performed (0 for the first)
    :return: the delay in seconds
    """
    delay = min(RETRY_INITIAL_DELAY * (2**attempt), RETRY_MAX_DELAY)
    jitter = delay * RETRY_JITTER
    return max(0.0, delay + random.uniform(-jitter, jitter))


def process_event(
    stream_name: str,
    result: FetcherResult,
    processor: DocumentProcessor,
    es_client: Elasticsearch,
    index_name: str,
) -> None:
    """Index (or remove) a single document in Elasticsearch.

    This is idempotent: indexing the same document twice only refreshes its
    ``last_indexed_datetime``, so it is safe to retry the whole event.

    :param stream_name: the name of the Redis stream (for logging)
    :param result: the document fetched from the stream
    :param processor: the document processor of the target index
    :param es_client: the Elasticsearch client
    :param index_name: the index (alias) to write to
    """
    processed_result = processor.from_result(result)
    processed_document = processed_result.document
    if (
        processed_result.status not in (FetcherStatus.FOUND, FetcherStatus.REMOVED)
        or processed_document is None
    ):
        return
    _id = processed_document.pop("_id")
    logger.debug("Document:\n%s", processed_document)
    if processed_result.status == FetcherStatus.REMOVED:
        try:
            es_client.delete(index=index_name, id=_id)
        except NotFoundError:
            # already absent from the index, nothing to do
            logger.info("Document %s to remove is not in the index", _id)
    else:
        es_client.index(index=index_name, body=processed_document, id=_id)


def handle_event_until_done(
    stream_name: str,
    result: FetcherResult,
    process: Callable[[], None],
    stop_event: threading.Event,
    skip_non_retryable: bool = True,
) -> None:
    """Process an event, retrying on transient errors until it is handled.

    Transient errors (see :func:`is_retryable_error`) are retried with an
    exponential backoff, forever: no event is ever skipped because of a
    temporary Elasticsearch or Redis outage. Non-retryable errors are logged
    and the event is skipped, so that a single invalid document cannot block
    the whole stream forever (the checkpoint is still advanced by the caller,
    which means the document is only re-indexed if it changes again).

    :param stream_name: the name of the Redis stream (for logging)
    :param result: the document to process (for logging)
    :param process: the (idempotent) function performing the indexing
    :param stop_event: if set while waiting, give up retrying and return
    :param skip_non_retryable: if True (the default), a non-retryable error is
        logged and the event is skipped. If False, it is re-raised to the
        caller (used for operations that must not be silently dropped).
    """
    attempt = 0
    while True:
        try:
            process()
            return
        except Exception as exc:
            if not is_retryable_error(exc):
                if not skip_non_retryable:
                    raise
                logger.exception(
                    "Non-retryable error while processing an event from %s "
                    "(%s), skipping it",
                    stream_name,
                    result.status.name,
                )
                return
            delay = retry_delay(attempt)
            attempt += 1
            logger.warning(
                "Transient error while processing an event from %s (%s), "
                "retrying in %.1fs (attempt %d): %s",
                stream_name,
                result.status.name,
                delay,
                attempt,
                exc,
            )
            # `wait` returns as soon as the event is set, so a stop request
            # does not have to wait for the whole backoff delay.
            if stop_event.wait(delay):
                logger.info("Stop requested, giving up retries")
                return


def get_start_position(
    redis_client: Redis,
    es_client: Elasticsearch,
    stream_name: str,
    index_name: str,
    last_modified_field_name: str,
) -> str:
    """Return the stream ID the daemon must start reading from.

    The position is read from the persisted checkpoint. If there is none (first
    run, or checkpoint deleted), it is derived from the most recent document of
    the index, so that events published while the daemon was not running are
    not lost. If the index is empty, there is nothing to be consistent with and
    we start from ``"$"``: only new events will be processed.

    :param redis_client: the Redis client
    :param es_client: the Elasticsearch client
    :param stream_name: the name of the Redis stream
    :param index_name: the name of the index alias the events are written to
    :param last_modified_field_name: the field holding the last modification
        timestamp of the documents
    :return: the stream ID to start from
    """
    checkpoint = get_checkpoint(redis_client, stream_name, index_name)
    if checkpoint is not None:
        logger.info(
            "Resuming stream %s for index %s from checkpoint %s",
            stream_name,
            index_name,
            checkpoint,
        )
        return checkpoint

    last_indexed_ms = get_last_indexed_timestamp_ms(
        es_client, index_name, last_modified_field_name
    )
    if last_indexed_ms is None:
        logger.error(
            "No checkpoint and no indexed document for stream %s and index %s: "
            "starting from the end of the stream, events published until now "
            "will not be indexed",
            stream_name,
            index_name,
        )
        return "$"

    start_id = stream_id_from_timestamp_ms(last_indexed_ms)
    # Persist immediately: the derived position is meaningful, and this avoids
    # querying Elasticsearch again on every restart.
    set_checkpoint(redis_client, stream_name, index_name, start_id)
    logger.info(
        "No checkpoint for stream %s and index %s, starting from the last "
        "indexed document (%s)",
        stream_name,
        index_name,
        start_id,
    )
    return start_id


def _install_signal_handlers(stop_event: threading.Event) -> None:
    """Make SIGTERM/SIGINT request a clean stop of the daemon.

    The handler only sets the event: the main loop notices it when it comes
    back from its read timeout and exits normally.

    :param stop_event: the event to set when a signal is received
    """

    def _handler(signum, _frame):
        logger.info("Received signal %s, requesting a clean stop", signum)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _handler)


def run_update_daemon(config: Config) -> None:
    """Run the update import daemon.

    This daemon listens to the Redis stream containing information about
    updated documents, fetches the full document and indexes it in
    Elasticsearch.

    Its position in the stream is persisted in Redis (see
    :mod:`app.checkpoints`) after each handled event, so that a restart resumes
    where it stopped instead of skipping the events published meanwhile.
    Transient Elasticsearch/Redis errors are retried with a backoff instead of
    crashing the process.

    :param config: the configuration to use
    """
    logger.info("Starting update import daemon")
    es_client = connection.get_es_client()
    # redis-py defaults to a read timeout of 5s, which would make a blocking
    # xread raise. We use a finite block timeout instead (see
    # settings.redis_reader_timeout), so that the daemon can react to a stop
    # request even when the stream is idle.
    redis_client = connection.get_redis_client(socket_timeout=None)

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

    if not id_field_names:
        logger.info("No Redis stream configured, nothing to listen to")
        return

    stop_event = threading.Event()
    _install_signal_handlers(stop_event)

    # Checkpoints are read once at startup. After that, the daemon keeps track
    # of its position itself and persists it after each handled event.
    min_ids = {
        stream_name: get_start_position(
            redis_client,
            es_client,
            stream_name,
            config.indices[stream_name_to_index_id[stream_name]].index.name,
            config.indices[
                stream_name_to_index_id[stream_name]
            ].index.last_modified_field_name,
        )
        for stream_name in id_field_names
    }

    # If the generator fails (e.g. a Redis error during xread), it is rebuilt
    # from the persisted checkpoints: the events of the in-flight batch that
    # were not handled yet are then read again.
    attempt = 0
    while not stop_event.is_set():
        try:
            for stream_name, _, stream_id, result in get_new_updates(
                redis_client,
                list(id_field_names.keys()),
                id_field_names=id_field_names,
                document_fetchers=document_fetchers,
                min_ids=min_ids,
                stop_event=stop_event,
            ):
                index_id = stream_name_to_index_id[stream_name]
                index_config = config.indices[index_id]
                min_ids[stream_name] = track_event(
                    redis_client,
                    es_client,
                    stream_name=stream_name,
                    stream_id=stream_id,
                    result=result,
                    processor=processors[stream_name],
                    index_name=index_config.index.name,
                    stop_event=stop_event,
                )
                # A retry may have been successful after several failures:
                # reset the backoff.
                attempt = 0
        except Exception as exc:
            if not is_retryable_error(exc):
                raise
            delay = retry_delay(attempt)
            attempt += 1
            logger.warning(
                "Transient error while reading updates, restarting from the "
                "checkpoint in %.1fs (attempt %d): %s",
                delay,
                attempt,
                exc,
            )
            if stop_event.wait(delay):
                break
            # The connection may be dead after an outage: open a new one.
            es_client = connection.get_es_client()
            min_ids = {
                stream_name: get_checkpoint(
                    redis_client,
                    stream_name,
                    config.indices[stream_name_to_index_id[stream_name]].index.name,
                )
                or min_ids[stream_name]
                for stream_name in id_field_names
            }

    logger.info("Stop requested, exiting")


def track_event(
    redis_client: Redis,
    es_client: Elasticsearch,
    stream_name: str,
    stream_id: str,
    result: FetcherResult,
    processor: DocumentProcessor,
    index_name: str,
    stop_event: threading.Event,
) -> str:
    """Index an event and persist the position it allows to resume from.

    Both steps are retried on transient errors (see
    :func:`handle_event_until_done`). The position is only persisted once the
    event has been handled (indexed, removed, skipped or permanently failed),
    which gives at-least-once semantics: after a crash, the last unconfirmed
    event is processed again (indexing is idempotent).

    :param redis_client: the Redis client, storing the checkpoints
    :param es_client: the Elasticsearch client
    :param stream_name: the name of the Redis stream
    :param stream_id: the ID of the event in the stream
    :param result: the document fetched from the stream
    :param processor: the document processor of the target index
    :param index_name: the index (alias) the documents are written to
    :param stop_event: if set while retrying, give up
    :return: the stream cursor to use to read the next event
    """
    handle_event_until_done(
        stream_name,
        result,
        lambda: process_event(stream_name, result, processor, es_client, index_name),
        stop_event,
    )
    # A checkpoint failure must not be silently ignored: without it, a restart
    # would replay the event, which is safe but hides the problem.
    handle_event_until_done(
        stream_name,
        result,
        lambda: set_checkpoint(redis_client, stream_name, index_name, stream_id),
        stop_event,
        skip_non_retryable=False,
    )
    # The exclusive range starts *after* this event, so it is not read again
    # by this generator (a rebuilt generator starts from the checkpoint).
    return f"({stream_id}"
