#!/usr/bin/env bash
set -e
# Renders markdown doc in docs to html in gh_pages

# get group id to use it in the docker
GID=$(id -g)

if [[ -e gh_pages/tmp/ref-config/searchalicious-config-schema.md ]]
then
  # replace ref-config by the generated file
  if [[ -e docs/users/ref-config.md ]]
  then
    mv docs/users/ref-config.md{,.orig}
  fi
  mv gh_pages/tmp/ref-config/searchalicious-config-schema.md docs/users/ref-config.md
fi

# create image
docker build --build-arg "USER_UID=$UID" --build-arg "USER_GID=$GID" --tag 'mkdocs-builder' -f scripts/Dockerfile.mkdocs .

# we use minidocks way of choosing UID / GID
docker run --rm \
  -e USER_ID=$UID -e GROUP_ID=$GID \
  -v $(pwd):/app -w /app \
  mkdocs-builder build

# cleanup
if [[ -e docs/users/ref-config.md.orig ]]
then
  mv docs/users/ref-config.md{,.orig}
fi
rm -rf gh_pages/tmp
