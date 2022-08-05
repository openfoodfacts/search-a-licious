"""
Performs an import from a CSV file. Note that this will delete the old index, causing downtime

Pass in the path of the file with the filename argument

Example:
python scripts/perform_import.py --filename=X
"""
from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime

from elasticsearch.helpers import bulk

from app.models.product import Product
from app.utils import connection
from app.utils import constants


def gen_documents(filename, next_index):
    valid_field_names = {
        field_name for field_name in Product._doc_type.mapping.properties.to_dict()[
            'properties'
        ].keys()
    }
    with open(filename) as f:
        input_file = csv.DictReader(f, delimiter='\t')

        for i, row in enumerate(input_file):
            # Use underscores for consistency
            row = {k.replace('-', '_'): v for k, v in row.items()}

            # Some fields have a leading dash (now underscore), remove them
            row = {k: v for k, v in row.items() if not k.startswith('_')}

            # For the first row, check that we have every column name in our index
            if i == 0:
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

            product = Product(**row).to_dict(True)
            # Override the index
            product['_index'] = next_index
            yield product

            if i % 100000 == 0 and i:
                # Roughly 2.5M lines as of July 2022
                print(f'Processed: {i} lines')


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
