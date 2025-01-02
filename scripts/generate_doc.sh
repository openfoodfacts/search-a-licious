#!/usr/bin/env bash

# generating documentation

# fail on errors
set -e

mkdir -p gh_pages

# script to generate documentation
echo "Build documentation with MkDocs"
scripts/build_mkdocs.sh

echo "Generate documentation for configuration file and settings"
scripts/build_schema.sh config
scripts/build_schema.sh settings

echo "Generate OpenAPI documentation"
echo '::group::{generate_openapi}'
make generate-openapi
echo "::endgroup::"

echo "Generate openapi html with redocly"
echo '::group::{generate_openapi_html}'
docker run --rm \
    -v $(pwd)/data:/data -v $(pwd)/gh_pages/:/output \
    ghcr.io/redocly/redoc/cli:latest \
    build -o /output/users/ref-openapi/index.html searchalicious-openapi.yml
sudo chown $UID -R gh_pages/users/ref-openapi
echo "::endgroup::"

echo "Generate webcomponents documentation"
echo '::group::{generate_custom_elements}'
make generate-custom-elements
mkdir -p gh_pages/users/ref-web-components/dist
cp frontend/public/dist/custom-elements.json gh_pages/users/ref-web-components/dist/custom-elements.json
sudo chown $UID -R gh_pages/users/ref-web-components
echo "::endgroup::"

echo "Generate python code documentation using sphinx"
scripts/build_sphinx.sh

# tell GitHub we don't want to use jekyll ! (otherwise it will remove _static)
# see https://github.blog/news-insights/the-library/bypassing-jekyll-on-github-pages/
touch gh_pages/.nojekyll

echo "To see your doc locally, run: python3 -m http.server -d gh_pages 8001"