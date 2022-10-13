"""
Performs an import from a MongoDB products.bson file.

Pass in the path of the file with the filename argument

Example:
python scripts/perform_import_parallel.py --filename=X
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime
from multiprocessing import Pool

import bson
from elasticsearch.helpers import bulk
from elasticsearch.helpers import parallel_bulk
from elasticsearch_dsl import Index

from app.import_queue.redis_client import RedisClient
from app.models.product import create_product_from_dict
from app.models.product import Product
from app.utils import connection
from app.utils import constants


def get_product_dict(row, next_index):
    """Return the product dict suitable for a bulk insert operation
    """
    product = create_product_from_dict(row)
    if not product:
        return None
    product_dict = product.to_dict(True)

    # Override the index
    product_dict['_index'] = next_index
    return product_dict


def gen_documents(filename, next_index, start_time, num_items, num_processes, process_id):
    """Generate documents to index for process number process_id

    We chunk documents based on document num % process_id
    """
    with open(filename, 'rb') as f:
        for i, row in enumerate(bson.decode_file_iter(f)):
            if i > num_items:
                break
            # Only get the relevant
            if i % num_processes != process_id:
                continue

            if i % 100000 == 0 and i:
                # Roughly 2.5M lines as of August 2022
                current_time = time.perf_counter()
                print(
                    f'Processed: {i} lines in {round(current_time - start_time)} seconds',
                )

            # At least one document doesn't have a code set, don't import it
            if not row.get('code'):
                continue

            if row['code'] in constants.BLACKLISTED_DOCUMENTS:
                continue

            product_dict = get_product_dict(row, next_index)
            if not product_dict:
                continue

            yield product_dict


def update_alias(es, next_index):
    """repoint the alias to point to the newly created Index
    """
    es.indices.update_aliases(
        body={
            'actions': [
                {
                    'remove': {
                        'alias': constants.INDEX_ALIAS,
                        'index': constants.INDEX_ALIAS_PATTERN,
                    },
                },
                {'add': {'alias': constants.INDEX_ALIAS, 'index': next_index}},
            ],
        },
    )


def import_parallel(filename, next_index, start_time, num_items, num_processes, process_id):
    """One task of import

    :param str filename: the bson file to read
    :param str next_index: the index to write to
    :param float start_time: the start time
    :param int num_items: max number of items to import
    :param int num_processes: total number of processes
    :param int process_id: the index of the process (from 0 to num_processes - 1)
    """
    # open a connection for this process
    es = connection.get_connection(timeout=120, retry_on_timeout=True)
    # Note that bulk works better than parallel bulk for our usecase.
    # The preprocessing in this file is non-trivial, so it's better to parallelize that. If we then do parallel_bulk
    # here, this causes queueing and a lot of memory usage in the importer process.
    success, errors = bulk(
        es, gen_documents(
            filename, next_index,
            start_time, num_items, num_processes, process_id,
        ),
        raise_on_error=False,
    )
    if not success:
        print('Encountered errors:')
        print(errors)


def get_redis_products(next_index, last_updated_timestamp):
    """Fetch ids of products to update from redis index

    Those ids are set by productopener on products updates
    """
    redis_client = RedisClient()
    print(f'Processing redis updates since {last_updated_timestamp}')
    timestamp_processed_values = redis_client.get_processed_since(
        last_updated_timestamp,
    )
    for _, row in timestamp_processed_values:
        product_dict = get_product_dict(row, next_index)
        yield product_dict

    print(f'Processed {len(timestamp_processed_values)} updates from Redis')


def get_redis_updates(next_index):
    es = connection.get_connection()
    # Ensure all documents are searchable after the import
    Index(next_index).refresh()
    query = Product.search().sort('-last_modified_t').extra(size=1)
    # Note that we can't use index() because we don't want to also query the main alias
    query._index = [next_index]
    results = query.execute()
    results_dict = [r.to_dict() for r in results]
    last_updated_timestamp = results_dict[0]['last_modified_t']

    # Since this is only done by a single process, we can use parallel_bulk
    for success, info in parallel_bulk(es, get_redis_products(next_index, last_updated_timestamp)):
        if not success:
            print('A document failed: ', info)


def perform_import(filename, num_items, num_processes, start_time):
    """Main function running the import sequence
    """
    es = connection.get_connection()
    # we create a temporary index to import to
    # at the end we will change alias to point to it
    next_index = constants.INDEX_ALIAS_PATTERN.replace(
        '*', datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f'),
    )
    # create the index
    Product.init(index=next_index)

    # split the work between processes
    args = []
    for i in range(num_processes):
        args.append((
            filename, next_index, start_time,
            num_items, num_processes, i,
        ))
    # run in parallel
    with Pool(num_processes) as pool:
        pool.starmap(import_parallel, args)
    # update with last index updates (hopefully since the bson)
    get_redis_updates(next_index)
    # make alias point to new index
    update_alias(es, next_index)


if __name__ == '__main__':
    parser = argparse.ArgumentParser('perform_import')
    parser.add_argument(
        '--filename', help='Filename where Mongo products.bson file is located', type=str,
    )
    parser.add_argument(
        '--num_items', help='How many items to import', type=int, default=100000000,
    )
    parser.add_argument(
        '--num_processes', help='How many import processes to run in parallel', type=int, default=2,
    )
    args = parser.parse_args()

    start_time = time.perf_counter()
    perform_import(
        args.filename, args.num_items,
        args.num_processes, start_time,
    )
    end_time = time.perf_counter()
    print(f'Import time: {end_time - start_time} seconds')
