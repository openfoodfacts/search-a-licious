# openfoodfacts-search
Open Food Facts Search API V3 using ElasticSearch - https://wiki.openfoodfacts.org/Search_API_V3

This API is currently in development. It is not serving any production traffic. The [Work Plan](https://wiki.openfoodfacts.org/Search_API_V3#Work_Plan) will be updated as development continues

### Organization
The main file is `api.py`, and the Product schema is in `models/product.py`. 

The `scripts/` directory contains various scripts for manual validation, constructing the product schema, importing, etc.

### Running locally
Docker spins up:
- Two elasticsearch nodes
- [Elasticvue](https://elasticvue.com/)

You will then need to import from CSV (see instructions below).

Make sure your environment is configured:
```commandline
export ELASTIC_PASSWORD=PASSWORD_HERE
```


### Helpful commands:

To start docker:
```console
docker-compose up -d
```

To start server:
```console
uvicorn api:app --reload
```

To import data from the [CSV export](https://world.openfoodfacts.org/data):
```console
python scripts/perform_import.py --filename=/path/to/file.csv