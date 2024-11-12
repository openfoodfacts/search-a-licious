#!/usr/bin/env bash
# Build config documentation in markdown
# Use it before using mkdocs

echo "::group::{build_schema $1}"

# Parameter is the schema type: config / settings
SCHEMA=$1

[[ -z $SCHEMA ]] && echo "You must provide a schema type: config / settings" && exit 1

set -e

# get group id to use it in the docker
GID=$(id -g)

# ensure dest dir
mkdir -p build/ref-$SCHEMA

# create yaml
make generate-$SCHEMA-schema
# create image
docker build --build-arg "USER_UID=$UID" --build-arg "USER_GID=$GID" --tag 'json-schema-for-humans' -f scripts/Dockerfile.schema .

# use image to generate documentation
docker run --rm --user user \
  -v $(pwd)/scripts/schema-config.json:/docs/schema-config.json \
  -v $(pwd)/data/searchalicious-$SCHEMA-schema.yml:/docs/in/searchalicious-$SCHEMA-schema.yml \
  -v $(pwd)/build/ref-$SCHEMA:/docs/out \
  json-schema-for-humans \
  generate-schema-doc --config-file /docs/schema-config.json /docs/in/ /docs/out/

# copy to ref-$SCHEMA folder
mv build/ref-$SCHEMA/* gh_pages/users/ref-$SCHEMA/
# also source
cp data/searchalicious-$SCHEMA-schema.yml gh_pages/users/ref-$SCHEMA/

echo "::endgroup::"