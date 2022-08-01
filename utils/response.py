from models.product import Product
from models.request import SearchBase


def create_response(es_results, request: SearchBase):
    resp = [convert_es_result(r, request) for r in es_results]
    return resp


def convert_es_result(es_result, request: SearchBase):
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
                trimmed_result_dict[response_field]  = result_dict[response_field]

        result_dict = trimmed_result_dict

    return result_dict
