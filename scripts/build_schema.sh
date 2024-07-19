#!/usr/bin/env bash
# Build config documentation in markdown
# Use it before using mkdocs

set -e

# get group id to use it in the docker
GID=$(id -g)

# ensure dest dir
mkdir -p build/ref-config

# create yaml
make generate-config-schema
# create image
docker build --build-arg "USER_UID=$UID" --build-arg "USER_GID=$GID" --tag 'json-schema-for-humans' -f scripts/Dockerfile.schema .

# use image to generate documentation
docker run --rm --user user \
  -v $(pwd)/scripts/schema-config.json:/docs/schema-config.json \
  -v $(pwd)/data/searchalicious-config-schema.yml:/docs/in/searchalicious-config-schema.yml \
  -v $(pwd)/build/ref-config:/docs/out \
  json-schema-for-humans \
  generate-schema-doc --config-file /docs/schema-config.json /docs/in/ /docs/out/

# copy to ref-config folder
mv build/ref-config/* gh_pages/users/ref-config/
# also source
cp data/searchalicious-config-schema.yml gh_pages/users/ref-config/
