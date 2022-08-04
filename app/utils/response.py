import json
import os

from jsonschema import validate
from functools import lru_cache

from app.models.product import Product
from app.models.request import SearchBase


@lru_cache(maxsize=None)
def get_json_schema():
    with open('app/product.schema.json') as json_file:
        return json.load(json_file)


def create_response(es_results, request: SearchBase):
    json_schema = get_json_schema()
    resp = [convert_es_result(r, request, json_schema) for r in es_results]
    return resp


def convert_es_result(es_result, request: SearchBase, json_schema):
    if not es_result:
        return None

    # Add missing fields to maintain backwards compatibility
    field_names = list(Product._doc_type.mapping.properties.to_dict()['properties'].keys())
    result_dict = {field_name: [] if field_name.endswith('_tags') else '' for field_name in field_names}
    result_dict.update(es_result.to_dict())

    # Trim fields as needed
    if request.response_fields:
        trimmed_result_dict = {}
        for response_field in request.response_fields:
            if response_field in result_dict:
                trimmed_result_dict[response_field] = result_dict[response_field]

        result_dict = trimmed_result_dict

    # Now, check if we match the JSON schema, this adds ~0.15s latency, so only do if using debug mode
    if os.getenv('DEBUG'):
        validate(instance=result_dict, schema=json_schema)

    return result_dict
