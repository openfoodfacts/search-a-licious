#!/usr/bin/env bash
set -e
# Renders markdown doc in docs to html in gh_pages

# get group id to use it in the docker
GID=$(id -g)

# create image
docker build --build-arg "USER_UID=$UID" --build-arg "USER_GID=$GID" --tag 'mkdocs-builder' -f scripts/Dockerfile.mkdocs .

# we use minidocks way of choosing UID / GID
docker run --rm \
  -e USER_ID=$UID -e GROUP_ID=$GID \
  -v $(pwd):/app -w /app \
  mkdocs-builder build
