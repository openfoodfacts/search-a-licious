"""
Performs an import from a CSV file. Note that this will delete the old index, causing downtime

Pass in the path of the file with the filename argument

Example:
python scripts/perform_import.py --filename=X
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime

from elasticsearch.helpers import bulk

from app.models.product import Product
from app.queue.redis_client import RedisClient
from app.utils import connection
from app.utils import constants


def get_product_dict(row, next_index, should_perform_check):
    # Use underscores for consistency
    row = {k.replace('-', '_'): v for k, v in row.items()}

    # Some fields have a leading dash (now underscore), remove them
    row = {k: v for k, v in row.items() if not k.startswith('_')}

    # For the first row, check that we have every column name in our index
    if should_perform_check:
        valid_field_names = {
            field_name for field_name in Product._doc_type.mapping.properties.to_dict()[
                'properties'
            ].keys()
        }
        column_names = row.keys()
        missing_column_names = []
        for column_name in column_names:
            if column_name not in valid_field_names and column_name:
                missing_column_names.append(column_name)

        if missing_column_names:
            print(f'Missing: {missing_column_names}')
            exit(-1)

    # Remove all empty values, we don't want to waste space in the index
    row = {k: v for k, v in row.items() if v != ''}

    # Split tags
    for k in row.keys():
        if k.endswith('_tags'):
            row[k] = row[k].split(',')

    product = Product(**row)
    product.fill_internal_fields()
    product_dict = product.to_dict(True)

    # Override the index
    product_dict['_index'] = next_index
    return product_dict


def gen_documents(filename, next_index):
    last_updated_timestamp = 0
    redis_client = RedisClient()
    with open(filename) as f:
        input_file = csv.DictReader(f, delimiter='\t')

        for i, row in enumerate(input_file):
            product_dict = get_product_dict(row, next_index, i == 0)
            print(product_dict)
            last_updated_timestamp = max(
                last_updated_timestamp, int(
                    product_dict['_source'].get('last_modified_t', 0),
                ),
            )
            yield product_dict

            if i % 100000 == 0 and i:
                # Roughly 2.5M lines as of July 2022
                print(f'Processed: {i} lines')

    print(f'Processing redis updates since {last_updated_timestamp}')
    timestamp_processed_values = redis_client.get_processed_since(
        last_updated_timestamp,
    )
    for _, value in timestamp_processed_values:
        row = json.loads(value)
        product_dict = get_product_dict(row, next_index, i == 0)
        yield product_dict
    print(f'Processed {len(timestamp_processed_values)} updates from Redis')


def update_alias(es, next_index):
    # repoint the alias to point to the newly created index
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


def perform_import(filename):
    es = connection.get_connection()
    next_index = constants.INDEX_ALIAS_PATTERN.replace(
        '*', datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f'),
    )

    Product.init(index=next_index)
    bulk(es, gen_documents(filename, next_index))
    update_alias(es, next_index)


if __name__ == '__main__':
    parser = argparse.ArgumentParser('perform_import')
    parser.add_argument(
        '--filename', help='Filename where CSV file is located', type=str,
    )
    args = parser.parse_args()

    start_time = time.perf_counter()
    perform_import(args.filename)
    end_time = time.perf_counter()
    print(f'Import time: {end_time - start_time} seconds')
