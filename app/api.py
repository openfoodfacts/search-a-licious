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
        match_queries.append(Q('match', **{field: request.text}))

    results = Product.search().query('bool', should=match_queries).extra(size=request.get_num_results()).execute()
    resp = response.create_response(results, request)
    return resp


@app.post("/search")
def search(request: SearchRequest):
    raise NotImplementedError()
