#!/usr/bin/env bash
# Build config documentation in markdown
# Use it before using mkdocs

set -e

# get group id to use it in the docker
GID=$(id -g)

# ensure dest dir
mkdir -p gh_pages/tmp/ref-config

# create yaml
make generate-config-schema
# and copy it to the documentation folder
cp data/searchalicious-config-schema.yml gh_pages/tmp/ref-config/
# ajv instance of json-schema-static-doc only knows some schema !
sed -i -e "s|https://json-schema.org/draft/2020-12/|https://json-schema.org/draft/2019-09/|g" gh_pages/tmp/ref-config/searchalicious-config-schema.yml
# create image
docker build --build-arg "USER_UID=$UID" --build-arg "USER_GID=$GID" --tag 'json-schema-static-docs' -f scripts/Dockerfile.json-schema-static-docs .

# use image to generate documentation
docker run --rm --user node \
  -v $(pwd)/scripts/generate-config-docs.js:/scripts/generate-config-docs.js \
  -v $(pwd)/gh_pages/tmp/ref-config:/docs \
  json-schema-static-docs node /scripts/generate-config-docs.js

