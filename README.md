# openfoodfacts-search
Open Food Facts Search API V3 using ElasticSearch - https://wiki.openfoodfacts.org/Search_API_V3

This API is currently in development. It is not serving any production traffic. The [Work Plan](https://wiki.openfoodfacts.org/Search_API_V3#Work_Plan) will be updated as development continues.

The file product.schema.json contains the schema of the returned products.

### Organization
The main file is `api.py`, and the Product schema is in `models/product.py`.

The `scripts/` directory contains various scripts for manual validation, constructing the product schema, importing, etc.

### Running locally
Start docker:
```console
docker-compose up -d
```

Docker spins up:
- Two elasticsearch nodes
- [Elasticvue](https://elasticvue.com/)
- The search service on port 8000

You will then need to import from CSV (see instructions below).

### Development
For development, you have two options for running the service:
1. Docker
2. Locally

To develop on docker, make the changes you need, then build the image and compose by running:
```console
docker build -t off_search_image .
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

### Helpful commands:
To import data from the [CSV export](https://world.openfoodfacts.org/data):
```console
python scripts/perform_import.py --filename=/path/to/file.csv
