# ![Search-a-licious](./assets/RVB_HORIZONTAL_WHITE_BG_SEARCH-A-LICIOUS-50.png "Search-a-licious logo")


**NOTE:** this is a prototype which will be heavily evolved to be more generic, more robust and have much more functionalities.

This API is currently in development. Read [Search-a-licious roadmap architecture notes](https://docs.google.com/document/d/1mibE8nACcmen6paSrqT9JQk5VbuvlFUXI1S93yHCK2I/edit) to understand where we are headed.

### Organization

The main file is `api.py`, and the schema is in `models/product.py`.

A CLI is available to perform common tasks.

### Running locally

Note: the Makefile will align the user id with your own uid for a smooth editing experience.

Before running the services, you need to make sure that your [system mmap count is high enough for Elasticsearch to run](https://www.elastic.co/guide/en/elasticsearch/reference/current/vm-max-map-count.html). You can do this by running:

```console
sudo sysctl -w vm.max_map_count=262144
```

Then build the services with:

```
make build
```

Start docker:

```console
docker compose up -d
```

> [!NOTE]
> You may encounter a permission error if your user is not part of the `docker` group, in which case you should either [add it](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user) or modify the Makefile to prefix `sudo` to all docker and docker compose commands.
> Update container crash because we are not connected to any Redis

Docker spins up:
- Two elasticsearch nodes
- [Elasticvue](https://elasticvue.com/)
- The search service on port 8000
- Redis on port 6379

You will then need to import from a JSONL dump (see instructions below).

### Development

#### Pre-requisites
##### Docker
- First of all, you need to have Docker installed on your machine. You can download it [here](https://www.docker.com/products/docker-desktop).
- Be sure you can [run docker without sudo](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user)

##### Direnv
For Linux and macOS users, You can follow our tutorial to install [direnv](https://openfoodfacts.github.io/openfoodfacts-server/dev/how-to-use-direnv/).[^winEnvrc]

Get your user id and group id by running `id -u` and `id -g` in your terminal.
Add a `.envrc` file at the root of the project with the following content:
```shell
export USER_GID=<your_user_gid>
export USER_UID=<your_user_uid>

export CONFIG_PATH=data/config/openfoodfacts.yml
export OFF_API_URL=https://world.openfoodfacts.org
export ALLOWED_ORIGINS='http://localhost,http://127.0.0.1,https://*.openfoodfacts.org,https://*.openfoodfacts.net' 
```

[^winEnvrc]: For Windows users, the .envrc is only taken into account by the `make` commands.

##### Pre-commit
You can follow the following [tutorial](https://pre-commit.com/#install) to install pre-commit on your machine.

#### Install
Be sure that your [system mmap count is high enough for Elasticsearch to run](https://www.elastic.co/guide/en/elasticsearch/reference/current/vm-max-map-count.html). You can do this by running:
```shell
sudo sysctl -w vm.max_map_count=262144
```
To make the change permanent, you need to add a line `vm.max_map_count=262144` to the `/etc/sysctl.conf` file and run the command `sudo sysctl -p` to apply the changes.
This will ensure that the modified value of `vm.max_map_count` is retained even after a system reboot. Without this step, the value will be reset to its default value after a reboot.

#### Run
Now you can run the project with Docker ```docker compose up ```.
After that run the following command on another shell to compile the project: ```make tsc_watch```.
Do this for next installation steps and to run the project.

#### How to explore Elasticsearch data

- Go to http://127.0.0.1:8080/welcome
- Click on "Add Elasticsearch cluster"
- change the cluster name to "docker-cluster"
- Click on "Connect"


#### Importing data
- Import Taxonomies: `make import-taxonomies` 
- Import products :
```shell
    # get some sample data
    curl https://world.openfoodfacts.org/data/exports/products.random-modulo-10000.jsonl.gz --output data/products.random-modulo-10000.jsonl.gz
    gzip -d data/products.random-modulo-10000.jsonl.gz
    # we skip updates because we are not connected to any redis
    make import-dataset filepath='products.random-modulo-10000.jsonl' args='--skip-updates'

#### Pages
Now you can go to :
- http://localhost:8000 to have a simple search page without use lit components
or 
- http://localhost:8000/static/off.html to access to lit components search page

To look into the data, you may use elasticvue, going to http://127.0.0.1:8080/ and reaching  http://127.0.0.1:9200 cluster: `docker-cluster` (unless you changed env variables).

#### Pre-Commit

This repo uses [pre-commit](https://pre-commit.com/) to enforce code styling, etc. To use it:
```console
pre-commit install
```
To run tests without committing:

```console
pre-commit run
```


#### Debug Backend App 
To debug the backend app:
* stop API instance: `docker compose stop api`
* add a pdb.set_trace() at the point you want,
* then launch `docker compose run --rm  --use-aliases api uvicorn app.api:app --proxy-headers --host 0.0.0.0 --port 8000 --reload`[^use_aliases]



### Running the import:
To import data from the [JSONL export](https://world.openfoodfacts.org/data), download the dataset in the `data` folder, then run:

`make import-dataset filepath='products.jsonl.gz'`

If you get errors, try adding more RAM (12GB works well if you have that spare), or slow down the indexing process by setting `num_processes` to 1 in the command above.

Typical import time is 45-60 minutes.

If you want to skip updates (eg. because you don't have a Redis installed), 
use `make import-dataset filepath='products.jsonl.gz' args="--skip-updates"`

You should also import taxonomies:

`make import-taxonomies`


## Fundings

This project has received financial support from the NGI Search (New Generation Internet) program, funded by the European Commission.

<img src="./assets/NGISearch_logo_tag_icon.svg" alt="NGI-search logo" title="NGI-search logo" height="100" />
<img src="./assets/europa-flag.jpg" alt="European flag" title="European flag" height="100" />
