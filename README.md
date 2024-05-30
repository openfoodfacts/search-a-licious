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
make up
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



To debug the backend app:
* stop api instance: `docker compose stop api`
* add a pdb.set_trace() at the point you want,
* then launch `docker compose run --rm  --use-aliases api uvicorn app.api:app --proxy-headers --host 0.0.0.0 --port 8000 --reload`[^use_aliases]

[^use_aliases]: the `--use-aliases` make it so that this container is reachable as "api" for the other containers in the compose


### Pre-Commit

This repo uses [pre-commit](https://pre-commit.com/) to enforce code styling, etc. To use it:
```console
pre-commit install
```

To run tests without committing:

```console
pre-commit run
```

### Running the import:
To import data from the [JSONL export](https://world.openfoodfacts.org/data), download the dataset in the `data` folder, then run:

`make import-dataset filepath='products.jsonl.gz'`

If you get errors, try adding more RAM (12GB works well if you have that spare), or slow down the indexing process by setting `num_processes` to 1 in the command above.

Typical import time is 45-60 minutes.

If you want to skip updates (eg. because you don't have a Redis installed), 
use `make import-dataset filepath='products.jsonl.gz' args="--skip-updates"`


## Fundings

This project has received financial support from the NGI Search (New Generation Internet) program, funded by the European Commission.

![NGI-search logo](./assets/NGISearch_logo_tag_icon.svg "NGI-search logo"){height=100px}
![European flag](./assets/europa-flag.jpg "European flag"){height=100px}