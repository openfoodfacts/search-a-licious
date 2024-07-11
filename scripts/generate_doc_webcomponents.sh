#!/usr/bin/env bash

# Separate step to create webcomponents documentation

# fail on errors
set -e

echo "Creating webcomponents documentation"
# copy custom-elements.json to the pages folder, inside a dist folder (to mimic production)
mkdir -p gh_pages/users/ref-web-components/dist
cp frontend/public/dist/custom-elements.json gh_pages/users/ref-web-components/dist/custom-elements.json
sudo chown $UID -R gh_pages/users/ref-web-components
