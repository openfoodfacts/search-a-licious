# Install search-a-licious

search-a-licious uses docker and docker compose to manage the services it needs to run. You will need to install both of these before you can use search-a-licious.

Once docker is installed, clone the git repository locally.

All configuration are passed through environment variables to services through the use of a .env file. A default .env file is provided in the repository, you will need to edit this file to suit your needs.

The only required change is to set the `CONFIG_PATH` variable to the path of your YAML configuration file. This file is used to configure the search-a-licious indexer and search services.



