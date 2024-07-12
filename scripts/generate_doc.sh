#!/usr/bin/env bash

# generating documentation

# fail on errors
set -e

mkdir -p gh_pages

# script to generate documentation
echo "Build documentation with MkDocs"
scripts/build_mkdocs.sh

# TODO: generating python and documentation with sphinx

echo "Generate OpenAPI documentation"
make generate-openapi

echo "Generate openapi html with redocly"
docker run --rm \
    -v $(pwd)/data:/data -v $(pwd)/gh_pages/:/output \
    ghcr.io/redocly/redoc/cli:latest \
    build -o /output/users/ref-openapi/index.html searchalicious-openapi.yml
sudo chown $UID -R gh_pages/users/ref-openapi

echo "Generate webcomponents documentation"
make generate-custom-elements
mkdir -p gh_pages/users/ref-web-components/dist
cp frontend/public/dist/custom-elements.json gh_pages/users/ref-web-components/dist/custom-elements.json
sudo chown $UID -R gh_pages/users/ref-web-components

echo "To see your doc locally, run: python3 -m http.server -d gh_pages 8001"