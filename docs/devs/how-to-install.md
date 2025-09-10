# How to install for local development

## Pre-requisites

First, follow same [prerequisite as for normal installation](../users/how-to-install.md#prerequisites):
* configuring mmap count
* installing docker and docker compose


## Installing Pre-commit

We use pre-commit to check the code quality.

You can follow the following [tutorial](https://pre-commit.com/#install)
to install pre-commit on your machine.


## Installing Direnv

Direnv is a tool to automatically set environment variables depending on the current directory.
This is handy to personalize the environment for each project as environments variables have priority over the `.env` file.

For Linux and macOS users, You can follow our tutorial to install [direnv](https://openfoodfacts.github.io/openfoodfacts-server/dev/how-to-use-direnv/).[^winEnvrc]

## Setting up your environment

You have several options to set up your environment:
1. use direnv, and thus use the `.envrc` file to set up your environment
2. add a .envrc that you source in your terminal.
3. modify the .env file directly, in which case you should be careful to not commit your changes

The 1st and 2nd options are the recommended ones.
The following steps are for those options, in case you edit the `.env` just ignore the "export " keywords.

Get your user id and group id by running `id -u` and `id -g` in your terminal.

Add a `.envrc` file at the root of the project with the following content:

```shell
export USER_GID=<your_user_gid>
export USER_UID=<your_user_uid>

export CONFIG_PATH=data/config/openfoodfacts.yml
export OFF_API_URL=https://world.openfoodfacts.org
```

[^winEnvrc]: For Windows users, the .envrc is only taken into account by the `make` commands.


## Building containers

To build the containers, you can run the following command:
```bash
make build
```

Note: the Makefile will align the user id with your own uid for a smooth editing experience (having same user id in container and host, so that you have permission to edit files).

## Running

Now you can run the project with Docker `docker compose up `.

After that run the following command on another shell to compile the project: `make tsc_watch`.

Do this for next installation steps and to run the project.


> [!NOTE]
> * You may encounter a permission error if your user is not part of the `docker` group, in which case you should either [add it](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user) or modify the Makefile to prefix `sudo` to all docker and docker compose commands.
> * Update container crash because we are not connected to any Redis, this is not a problem

Docker spins up:
- Two elasticsearch nodes, one being exposed on port 9200 [^localhost_expose]
  * test it going to http://127.0.0.1:9200
- [Elasticvue](https://elasticvue.com/) on port 8080
  * test it going to http://127.0.0.1:8080
- The search service on port 8000
  * test the API going to http://search.localhost:8000/docs
  * test the UI going to http://search.localhost:8000/

[^localhost_expose]: by default we only expose on the localhost interface.
This is driven by the `*_EXPOSE` variables in `.env`.

Congratulations, you  have successfully installed the project !

You will then need to import from a JSONL dump (see instructions below).

## Importing data into your development environment

- Import Taxonomies: `make import-taxonomies`
- Import products :
   ```bash
    # get some sample data
    curl https://world.openfoodfacts.org/data/exports/products.random-modulo-10000.jsonl.gz --output data/products.random-modulo-10000.jsonl.gz
    gzip -d data/products.random-modulo-10000.jsonl.gz
    # we skip updates because we are not connected to any redis
    make import-dataset filepath='products.random-modulo-10000.jsonl' args='--skip-updates'
   ```

Verify you have data by going to http://search.localhost:8000/

## Exploring Elasticsearch data

When you need to explore the elasticsearch data, you can use elasticvue.

- Go to http://127.0.0.1:8080/welcome
- Click on "Add Elasticsearch cluster"
- change the cluster name to "docker-cluster" at http://127.0.0.1:9200
- Click on "Connect"
