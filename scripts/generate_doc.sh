#!/usr/bin/env bash

COLOR_RESET="\033[0m"
COLOR_BOLD="\033[1m"
COLOR_BLUE="\033[34m"

is_tty() {
  [[ -t 1 && "$TERM" != "dumb" ]]
}

# Start a log group
start_group() {
  local title="${1}"
  if [ -n "$GITHUB_ACTIONS" ]; then
    printf "::group::%s\n" "$title"
  else
    local prefix="==> ${title}"
    if is_tty; then
      printf "${COLOR_BOLD}${COLOR_BLUE}%s${COLOR_RESET}\n" "$prefix"
    else
      printf "%s\n" "$prefix"
    fi
  fi
}

# End a log group
end_group() {
  if [ -n "$GITHUB_ACTIONS" ]; then
    echo "::endgroup::"
  else
    echo ""
  fi
}

# generating documentation

# fail on errors
set -e

mkdir -p gh_pages

# script to generate documentation
start_group "Generate documentation with mkdocs"
scripts/build_mkdocs.sh
end_group

start_group "Generate documentation for configuration file and settings"
scripts/build_schema.sh config
scripts/build_schema.sh settings
end_group

start_group "Generate OpenAPI documentation"
make generate-openapi
end_group

start_group "Generate openapi html with redocly"
docker run --rm \
  -v $(pwd)/data:/data \
  -v $(pwd)/gh_pages/:/output \
  --user "$(id -u):$(id -g)" \
  ghcr.io/redocly/redoc/cli:latest \
  build -o /output/users/ref-openapi/index.html searchalicious-openapi.yml
end_group

start_group "Generate webcomponents documentation"
make generate-custom-elements
mkdir -p gh_pages/users/ref-web-components/dist
cp frontend/public/dist/custom-elements.json gh_pages/users/ref-web-components/dist/custom-elements.json
sudo chown $UID -R gh_pages/users/ref-web-components
end_group

start_group "Generate python code documentation using sphinx"
scripts/build_sphinx.sh
end_group

# tell GitHub we don't want to use jekyll ! (otherwise it will remove _static)
# see https://github.blog/news-insights/the-library/bypassing-jekyll-on-github-pages/
if [ -n "$GITHUB_ACTIONS" ]; then
  touch gh_pages/.nojekyll
fi

echo "To see your doc locally, run: python3 -m http.server -d gh_pages 8001"
