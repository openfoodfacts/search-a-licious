from __future__ import annotations

import json
from functools import lru_cache

from app.models.request import SearchBase


@lru_cache(maxsize=None)
def get_json_schema():
    with open('app/product.schema.json') as json_file:
        return json.load(json_file)


def create_response(es_results, request: SearchBase):
    resp = [convert_es_result(r, request) for r in es_results]
    return resp


def convert_es_result(es_result, request: SearchBase):
    if not es_result:
        return None

    result_dict = es_result.to_dict()
    result_dict = add_images_urls_to_product(result_dict)

    # Trim fields as needed
    if request.response_fields:
        trimmed_result_dict = {}
        for response_field in request.response_fields:
            if response_field in result_dict:
                trimmed_result_dict[response_field] = result_dict[response_field]

        result_dict = trimmed_result_dict

    return result_dict


def add_images_urls_to_product(product):
    # Python copy of the code from https://github.com/openfoodfacts/openfoodfacts-server/blob/b297ed858d526332649562cdec5f1d36be184984/lib/ProductOpener/Display.pm#L10128
    code = product['code']

    for image_type in ['front', 'ingredients', 'nutrition', 'packaging']:
        display_ids = []
        lc = product.get('lc')
        if lc:
            display_ids.append('{}_{}'.format(image_type, lc))

        display_ids.append(image_type)

        for display_id in display_ids:
            if product.get('images') and product['images'].get(display_id) \
                    and product['images'][display_id].get('sizes'):

                product['image_{}_url'.format(image_type)] = 'https://images.openfoodfacts.org/images/products/{}/{}.{}.{}.jpg'.format(
                    code,
                    display_id,
                    product['images'][display_id].get('rev'),
                    400,
                )
                product['image_{}_small_url'.format(image_type)] = 'https://images.openfoodfacts.org/images/products/{}/{}.{}.{}.jpg'.format(
                    code,
                    display_id,
                    product['images'][display_id].get('rev'),
                    200,
                )
                product['image_{}_thumb_url'.format(image_type)] = 'https://images.openfoodfacts.org/images/products/{}/{}.{}.{}.jpg'.format(
                    code,
                    display_id,
                    product['images'][display_id].get('rev'),
                    100,
                )

                if image_type == 'front':
                    product['image_url'] = product[
                        'image_{}_url'.format(
                            image_type,
                        )
                    ]
                    product['image_small_url'] = product[
                        'image_{}_small_url'.format(
                            image_type,
                        )
                    ]
                    product['image_thumb_url'] = product[
                        'image_{}_thumb_url'.format(
                            image_type,
                        )
                    ]

        if product.get('languages_codes'):
            for language_code in product['languages_codes']:
                image_id = '{}_{}'.format(image_type, language_code)
                if product.get('images') and product['images'].get(image_id) and product['images'][image_id]['sizes']:
                    if not product.get('selected_images'):
                        product['selected_images'] = {}
                    product['selected_images'].update({
                        image_type: {
                            'display': {
                                language_code: 'https://images.openfoodfacts.org/images/products/{}/{}.{}.{}.jpg'.format(
                                    code,
                                    image_id,
                                    product['images'][image_id].get('rev'),
                                    400,
                                ),
                            },
                            'small': {
                                language_code: 'https://images.openfoodfacts.org/images/products/{}/{}.{}.{}.jpg'.format(
                                    code,
                                    image_id,
                                    product['images'][image_id].get('rev'),
                                    200,
                                ),
                            },
                            'thumb': {
                                language_code: 'https://images.openfoodfacts.org/images/products/{}/{}.{}.{}.jpg'.format(
                                    code,
                                    image_id,
                                    product['images'][image_id].get('rev'),
                                    100,
                                ),
                            },
                        },
                    })

    return product
