from elasticsearch_dsl import Q
from fastapi import FastAPI, HTTPException

from app.models.product import Product
from app.models.request import AutocompleteRequest, SearchRequest
from app.utils import connection, constants, response

app = FastAPI()
connection.get_connection()


# TODO: Remove this commented out code, so that it's not confusing about where the current GET API is served
# (retaining temporarily as a proof of concept)
# @app.get("/{barcode}")
# def get_product(barcode: str):
#     results = Product.search().query("match", code=barcode).execute()
#     results_dict = [r.to_dict() for r in results]
#
#     if not results_dict:
#         raise HTTPException(status_code=404, detail="Barcode not found")
#
#     product = results_dict[0]
#     return product

@app.post("/autocomplete")
def autocomplete(request: AutocompleteRequest):
    # TODO: This function needs unit testing
    if not request.search_fields:
        request.search_fields = constants.AUTOCOMPLETE_FIELDS
    for field in request.search_fields:
        if field not in constants.AUTOCOMPLETE_FIELDS:
            raise HTTPException(status_code=400, detail="Invalid field: {}".format(field))

    match_queries = []
    for field in request.search_fields:
        autocomplete_field_name = '{}__autocomplete'.format(field)
        match_queries.append(Q('match', **{autocomplete_field_name: request.text}))

    results = Product.search().query('bool', should=match_queries).extra(size=request.get_num_results()).execute()
    resp = response.create_response(results, request)
    return resp


def validate_field(field, fields_to_types, valid_types, filter_type):
    if field not in fields_to_types:
        raise HTTPException(status_code=400, detail="Field {} does not exist".format(field))
    field_type = fields_to_types[field]['type']
    if field_type not in valid_types:
        raise HTTPException(status_code=400, detail="Field {} is not of type {}".format(field, filter_type))
    return field_type

def create_search_query(request: SearchRequest):
    fields_to_types = Product._doc_type.mapping.properties.to_dict()['properties']
    must_queries = []
    must_not_queries = []
    range_queries = []

    for filter in request.string_filters:
        field = filter.field
        field_type = validate_field(field, fields_to_types, ['text', 'keyword'], 'string')
        # If it's a text field, use the raw nested field for the eq, ne case
        if field_type == 'text' and filter.operator in ['eq', 'ne']:
            field = '{}__raw'.format(field)

        if filter.operator == 'eq':
            must_queries.append(Q('term', **{field: filter.value}))
        elif filter.operator == 'ne':
            must_not_queries.append(Q('term', **{field: filter.value}))
        elif filter.operator == 'like':
            must_queries.append(Q('match', **{field: filter.value}))
        elif filter.operator == 'without':
            must_not_queries.append(Q('exists', field=field))

    for filter in request.numeric_filters:
        field = filter.field
        validate_field(field, fields_to_types, ['double'], 'numeric')

        if filter.operator == 'eq':
            must_queries.append(Q('term', **{field: filter.value}))
        elif filter.operator == 'ne':
            must_not_queries.append(Q('term', **{field: filter.value}))
        elif filter.operator == 'lt':
            range_queries.append({field: {'lt': filter.value}})
        elif filter.operator == 'gt':
            range_queries.append({field: {'gt': filter.value}})
        elif filter.operator == 'without':
            must_not_queries.append(Q('exists', field=field))

    for filter in request.date_time_filters:
        field = filter.field
        validate_field(field, fields_to_types, ['date'], 'date_time')

        if filter.operator == 'lt':
            range_queries.append({field: {'lt': filter.value}})
        elif filter.operator == 'gt':
            range_queries.append({field: {'gt': filter.value}})
        elif filter.operator == 'without':
            must_not_queries.append(Q('exists', field=field))

    query = Product.search().query(
        'bool',
        must=must_queries,
        must_not=must_not_queries,
    )
    if range_queries:
        for range_query in range_queries:
            query = query.filter(
                'range', **range_query,
            )
    return query.extra(size=request.get_num_results())

@app.post("/search")
def search(request: SearchRequest):
    # TODO: Add unit tests
    if not request.string_filters and not request.numeric_filters and not request.date_time_filters:
        raise HTTPException(status_code=400, detail="At least one filter must be used")

    results = create_search_query(request).execute()
    resp = response.create_response(results, request)
    return resp
