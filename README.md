# ![Search-a-licious](./assets/RVB_HORIZONTAL_WHITE_BG_SEARCH-A-LICIOUS-50.png "Search-a-licious logo")


**NOTE:** this is a prototype which will be heavily evolved to be more generic, more robust and have much more functionalities.


Open Food Facts Search API V3 using ElasticSearch - https://wiki.openfoodfacts.org/Search_API_V3

This API is currently in development. It is not serving any production traffic. The [Work Plan](https://wiki.openfoodfacts.org/Search_API_V3#Work_Plan) will be updated as development continues.

The file product.schema.json contains a partial schema of the returned products.

### Organization
The main file is `api.py`, and the Product schema is in `models/product.py`.

The `scripts/` directory contains various scripts for manual validation, constructing the product schema, importing, etc.

### Running locally

Note: the Makefile will align the user id with your own uid for a smooth editing experience.

Build with:

```
make build
```

Start docker:

```console
docker-compose up -d
```

Docker spins up:
- Two elasticsearch nodes
- [Elasticvue](https://elasticvue.com/)
- The search service on port 8000
- Redis on port 6379

You will then need to import from MongoDB (see instructions below).

### Development
For development, you have two options for running the service:
1. Docker
2. Locally

To develop on docker, make the changes you need, then build the image and compose by running:
```console
docker-compose up -d
```

However, this tends to be slower than developing locally.

To develop locally, create a venv, install dependencies, then run the service:
```console
virtualenv .
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.api:app --reload --port=8001 --workers=4
```
Note that it's important to use port 8001, as port 8000 will be used by the docker version of the search service.

### Pre-Commit
This repo uses [pre-commit](https://pre-commit.com/) to enforce code styling, etc. To use it:
```console
pre-commit run
```

### Running the import:
To import data from the [MongoDB export](https://world.openfoodfacts.org/data):

1. First ensure that your docker environment has at least 150GB of disk and 6GB of RAM. This can be found under settings --> resources

2. Run the following command:
   ```console
   python scripts/perform_import_parallel.py --filename=/path/to/products.bson --num_processes=2
   ```

   Or using docker:
   ```console
   docker-compose run --rm -v $(pwd)/path/to/products.bson:/mnt/products.bson:ro searchservice python3 app/scripts/perform_import_parallel.py --filename=/mnt/products.bson --num_processes=2
   ```

If you get errors, try adding more RAM (12GB works well if you have that spare), or slow down the indexing process by setting `num_processes` to 1 in the command above.

Typical import time is 1-1.5 hours on an M1 Macbook.

### Testing via CLI:
Under `scripts/` there are scripts that allow you to send requests to the service, ES or Redis.

For example, to run the autocomplete query on the local docker instance, do:
```console
python scripts/http_autocomplete_query.py --port=8000
```
