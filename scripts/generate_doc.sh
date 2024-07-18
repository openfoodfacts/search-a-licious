#!/usr/bin/env bash

# generating documentation

# fail on errors
set -e

mkdir -p gh_pages

# generate config reference documentation
scripts/generate-config-docs.sh

# script to generate documentation
echo "Build documentation with MkDocs"
scripts/build_mkdocs.sh

# cleanup config generation and copy config schema
mv docs/users/ref-config.md{.orig,}
cp data/searchalicious-config-schema.yml gh_pages/users/ref-config/

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

echo "Generate python code documentation using sphinx"
scripts/build_sphinx.sh

echo "To see your doc locally, run: python3 -m http.server -d gh_pages 8001"