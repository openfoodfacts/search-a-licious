#!/usr/bin/env bash
# Build sphinx documentation

set -e

# get group id to use it in the docker
GID=$(id -g)

# create image
docker build --build-arg "USER_UID=$UID" --build-arg "USER_GID=$GID" --tag 'sphinx-builder' -f scripts/Dockerfile.sphinx .

# ensure dest dir
mkdir -p gh_pages/sphinx

# use image to generate documentation
docker run --rm --user user \
  -v $(pwd)/scripts/sphinx:/docs \
  -v $(pwd)/docs/sphinx:/docs/source \
  -v $(pwd)/app:/docs/app \
  -v $(pwd)/gh_pages/sphinx:/docs/build \
  -e PYTHONPATH=/docs/ \
  -e SPHINXOPTS="-W --keep-going" \
  sphinx-builder make html

# move to the right place and cleanup
rm -rf gh_pages/users/ref-python || true
mv gh_pages/sphinx/html gh_pages/users/ref-python
rm -rf gh_pages/sphinx/
