import time
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path

import tqdm
from elasticsearch.helpers import bulk, parallel_bulk
from elasticsearch_dsl import Index

from app.config import CONFIG, Config
from app.import_queue.redis_client import RedisClient
from app.models.product import Product, ProductProcessor
from app.utils import connection, constants, get_logger
from app.utils.io import jsonl_iter

logger = get_logger(__name__)


def get_product_dict(processor: ProductProcessor, row, next_index: str):
    """Return the product dict suitable for a bulk insert operation"""
    product = processor.from_dict(row)
    if not product:
        return None
    product_dict = product.to_dict(True)

    # Override the index
    product_dict["_index"] = next_index
    return product_dict


def gen_documents(
    processor: ProductProcessor,
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

        # At least one document doesn't have a code set, don't import it
        if not row.get("code"):
            continue

        if row["code"] in constants.BLACKLISTED_DOCUMENTS:
            continue

        product_dict = get_product_dict(processor, row, next_index)
        if not product_dict:
            continue

        yield product_dict


def update_alias(es, next_index):
    """repoint the alias to point to the newly created Index"""
    es.indices.update_aliases(
        body={
            "actions": [
                {
                    "remove": {
                        "alias": constants.INDEX_ALIAS,
                        "index": constants.INDEX_ALIAS_PATTERN,
                    },
                },
                {"add": {"alias": constants.INDEX_ALIAS, "index": next_index}},
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
    processor = ProductProcessor(config)
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
    processor: ProductProcessor, next_index: str, last_updated_timestamp
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
        product_dict = get_product_dict(processor, row, next_index)
        yield product_dict

    logger.info("Processed %d updates from Redis", len(timestamp_processed_values))


def get_redis_updates(next_index: str, config: Config):
    es = connection.get_connection()
    # Ensure all documents are searchable after the import
    Index(next_index).refresh()
    field_name = config.get_last_modified_field().name
    query = Product.search().sort(f"-{field_name}").extra(size=1)
    # Note that we can't use index() because we don't want to also query the main alias
    query._index = [next_index]
    results = query.execute()
    results_dict = [r.to_dict() for r in results]
    last_updated_timestamp = results_dict[0]["last_modified_t"]

    # Since this is only done by a single process, we can use parallel_bulk
    for success, info in parallel_bulk(
        es, get_redis_products(next_index, last_updated_timestamp)
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
    next_index = constants.INDEX_ALIAS_PATTERN.replace(
        "*",
        datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f"),
    )
    # create the index
    Product.init(index=next_index)

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
