from __future__ import annotations

import os

import requests


class ProductClient:
    def __init__(self):
        pass

    def get_product(self, code):
        url = '{}/api/v2/product/{}'.format(
            os.getenv(
                'OPENFOODFACTS_API_URL',
                'https://world.openfoodfacts.org',
            ),
            code,
        )
        response = requests.get(url)
        json_response = response.json()
        if not json_response or not json_response.get('product'):
            return None
        return json_response['product']
