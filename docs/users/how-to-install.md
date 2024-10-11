# How to install search-a-licious


## Prerequisites

### Ensure mmap count is high enough

If you are on Linux, before running the services, you need to make sure that your [system mmap count is high enough for Elasticsearch to run](https://www.elastic.co/guide/en/elasticsearch/reference/current/vm-max-map-count.html). You can do this by running:

```console
sudo sysctl -w vm.max_map_count=262144
```

To make the change permanent, you need to add a line `vm.max_map_count=262144` to the `/etc/sysctl.conf` file and run the command `sudo sysctl -p` to apply the changes.
This will ensure that the modified value of `vm.max_map_count` is retained even after a system reboot. Without this step, the value will be reset to its default value after a reboot.

### Install docker and docker compose

search-a-licious uses docker and docker compose to manage the services it needs to run.
You will need to install both of these before you can use search-a-licious.

Once [docker](https://docs.docker.com/engine/install/) and [docker compose](https://docs.docker.com/compose/install/) are installed, clone the git repository locally.

## Settings

All configuration are passed through environment variables to services through the use of a `.env` file. A sample `.env` file is provided in the repository, you will need to edit this file to suit your needs.

The only required change is to set the `CONFIG_PATH` variable to the path of your YAML configuration file. This file is used to configure the search-a-licious indexer and search services. See the [create your configuration, in tutorial](./tutorial.md#create-a-configuration-file)

If you want to see more about applications settings, see the [Reference for Settings](./ref-settings.md)

Look closely at each variable in the `.env` file.
You must at the very least:
* change `RESTART_POLICY` to `always`
* change `COMPOSE_FILE` to `docker-compose.yml;docker/prod.yml;docker/monitor.yml` (monitor is optional but recommended)
* change `MEM_LIMIT` to set elasticsearch memory limit
* change `NGINX_BASIC_AUTH_USER_PASSWD`

Then you can either:
* rebuild the docker images by running `make build`
* use images from our github repository. For this,
  * edit the .env file and set `TAG` to the commit sha corresponding to the version you want to use

Our [CI file for deployment](https://github.com/openfoodfacts/search-a-licious/blob/main/.github/workflows/container-deploy.yml) might be of inspiration.

## Launching

You should now be able to start docker:

```console
docker compose up -d
```

> [!NOTES]
> * You may encounter a permission error if your user is not part of the `docker` group, in which case you should either [add it](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user) or modify the Makefile to prefix `sudo` to all docker and docker compose commands.
> * Update container might crash because if you are note connected to any Redis, Search-a-licious will still run. You need to connect to Redis only if you want continuous updates. See [How to update the index](./how-to-update-index.md)


## Using it

To understand what you can then do, continue with the [tutorial](./tutorial.md).