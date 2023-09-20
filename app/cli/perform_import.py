import time
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path

import tqdm
from elasticsearch.helpers import bulk, parallel_bulk
from elasticsearch_dsl import Index, Search

from app.config import Config
from app.import_queue.redis_client import RedisClient
from app.models.product import DocumentProcessor, generate_index_object
from app.types import JSONType
from app.utils import connection, get_logger
from app.utils.io import jsonl_iter

logger = get_logger(__name__)


def get_document_dict(processor: DocumentProcessor, row, next_index: str) -> JSONType:
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
    start_time,
    num_items: int | None,
    num_processes: int,
    process_id: int,
):
    """Generate documents to index for process number process_id

    We chunk documents based on document num % process_id
    """
    for i, row in enumerate(tqdm.tqdm(jsonl_iter(file_path))):
        if num_items is not None and i > num_items:
            break
        # Only get the relevant
        if i % num_processes != process_id:
            continue

        if i % 100000 == 0 and i:
            # Roughly 2.5M lines as of August 2022
            current_time = time.perf_counter()
            logger.info(
                "Processed: %d lines in %s seconds", i, round(current_time - start_time)
            )

        document_dict = get_document_dict(processor, row, next_index)
        if not document_dict:
            continue

        yield document_dict


def update_alias(es, next_index: str, index_alias: str):
    """repoint the alias to point to the newly created Index"""
    es.indices.update_aliases(
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
    start_time: float,
    num_items: int | None,
    num_processes: int,
    process_id: int,
):
    """One task of import.

    :param Path file_path: the JSONL file to read
    :param str next_index: the index to write to
    :param float start_time: the start time
    :param int num_items: max number of items to import, default to no limit
    :param int num_processes: total number of processes
    :param int process_id: the index of the process (from 0 to num_processes - 1)
    """
    processor = DocumentProcessor(config)
    # open a connection for this process
    es = connection.get_connection(timeout=120, retry_on_timeout=True)
    # Note that bulk works better than parallel bulk for our usecase.
    # The preprocessing in this file is non-trivial, so it's better to parallelize that. If we then do parallel_bulk
    # here, this causes queueing and a lot of memory usage in the importer process.
    success, errors = bulk(
        es,
        gen_documents(
            processor,
            file_path,
            next_index,
            start_time,
            num_items,
            num_processes,
            process_id,
        ),
        raise_on_error=False,
    )
    if not success:
        logger.error("Encountered errors: %s", errors)


def get_redis_products(
    processor: DocumentProcessor, next_index: str, last_updated_timestamp
):
    """Fetch ids of products to update from redis index

    Those ids are set by productopener on products updates
    """
    redis_client = RedisClient()
    logger.info("Processing redis updates since %s", last_updated_timestamp)
    timestamp_processed_values = redis_client.get_processed_since(
        last_updated_timestamp,
    )
    for _, row in timestamp_processed_values:
        document_dict = get_document_dict(processor, row, next_index)
        yield document_dict

    logger.info("Processed %d updates from Redis", len(timestamp_processed_values))


def get_redis_updates(next_index: str, config: Config):
    processor = DocumentProcessor(config)
    es = connection.get_connection()
    # Ensure all documents are searchable after the import
    Index(next_index).refresh()
    field_name = config.index.last_modified_field_name
    query = Search(index=next_index).sort(f"-{field_name}").extra(size=1)
    # Note that we can't use index() because we don't want to also query the main alias
    query._index = [next_index]
    results = query.execute()
    results_dict = [r.to_dict() for r in results]
    last_updated_timestamp = results_dict[0][field_name]

    # Since this is only done by a single process, we can use parallel_bulk
    for success, info in parallel_bulk(
        es, get_redis_products(processor, next_index, last_updated_timestamp)
    ):
        if not success:
            logger.warning("A document failed: %s", info)


def perform_import(
    file_path: Path,
    num_items: int | None,
    num_processes: int,
    start_time: float,
    config: Config,
):
    """Main function running the import sequence"""
    es = connection.get_connection()
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
                start_time,
                num_items,
                num_processes,
                i,
            )
        )
    # run in parallel
    with Pool(num_processes) as pool:
        pool.starmap(import_parallel, args)
    # update with last index updates (hopefully since the jsonl)
    get_redis_updates(next_index, config)
    # make alias point to new index
    update_alias(es, next_index)
