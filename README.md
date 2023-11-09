# ![Search-a-licious](./assets/RVB_HORIZONTAL_WHITE_BG_SEARCH-A-LICIOUS-50.png "Search-a-licious logo")


**NOTE:** this is a prototype which will be heavily evolved to be more generic, more robust and have much more functionalities.

This API is currently in development. Read [Search-a-licious roadmap architecture notes](https://docs.google.com/document/d/1mibE8nACcmen6paSrqT9JQk5VbuvlFUXI1S93yHCK2I/edit) to understand where we are headed.

### Organization
The main file is `api.py`, and the schema is in `models/product.py`.

A CLI is available to perform common tasks.

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

You will then need to import from a JSONL dump (see instructions below).

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
To import data from the [JSONL export](https://world.openfoodfacts.org/data):

1Run the following command:
```console
python3 -m app import /path/to/products.jsonl.gz --num_processes=2
```

Or using docker:
```console
docker-compose run --rm -v $(pwd)/path/to/products.jsonl.gz:/mnt/products.jsonl.gz:ro api python3 -m app import /mnt/products.jsonl.gz --num-processes=2
```

If you get errors, try adding more RAM (12GB works well if you have that spare), or slow down the indexing process by setting `num_processes` to 1 in the command above.

Typical import time is 45-60 minutes.
