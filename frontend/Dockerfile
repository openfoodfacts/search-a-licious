# syntax = docker/dockerfile:1.2
# Base user uid / gid keep 1000 on prod, align with your user on dev
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

# builder is the node service, only used to build project in prod
FROM node:lts as builder
ARG USER_UID
ARG USER_GID
RUN usermod --uid $USER_UID node && \
  groupmod --gid $USER_GID node && \
  mkdir -p /opt/search-a-licious/node_modules && \
  mkdir -p /opt/search-a-licious/src && \
  mkdir -p /opt/search-a-licious/dev && \
  mkdir -p /home/node/.npm && \
  mkdir /playwright && \
  chown node:node -R /opt/search-a-licious/ && \
  chown node:node -R /home/node/.npm && \
  chown node:node -R /playwright
# tricky but we can't set uid and gid from variables with RUN --mount
# so we ensure permissions while we are root
RUN --mount=type=cache,id=search-a-licious-npm-cache,target=/home/node/.npm,mode=0777 \
  chown -R node:node /home/node/.npm
COPY --chown=node:node package*.json /opt/search-a-licious
WORKDIR /opt/search-a-licious
# we build playwright inside the image as it is only for dev
ENV PLAYWRIGHT_BROWSERS_PATH=/playwright
USER node
# install dependencies
RUN --mount=type=cache,id=search-a-licious-npm-cache,target=/home/node/.npm,mode=0777 \
  npm install && \
  npx playwright install
USER root
RUN  --mount=type=cache,id=search-a-licious-apt-cache,target=/var/cache/apt \
  npx playwright install-deps chromium
USER node
# add local binaries to path
ENV PATH /opt/search-a-licious/node_modules/.bin:$PATH

# copy files
COPY --chown=node:node src /opt/search-a-licious/src
COPY --chown=node:node dev /opt/search-a-licious/dev
COPY --chown=node:node dev /opt/search-a-licious/public
COPY --chown=node:node .eslintrc.json /opt/search-a-licious/.eslintrc.json
COPY --chown=node:node .prettierrc.json /opt/search-a-licious/.prettierrc.json
COPY --chown=node:node tsconfig.json /opt/search-a-licious/tsconfig.json
COPY --chown=node:node rollup.config.js /opt/search-a-licious/rollup.config.js
# build for production
# no need of a public url, we are at the root
RUN npm run build && npm run bundle
CMD ["npm", "run", "serve"]

# nginx
FROM nginx:stable
WORKDIR /opt/search-a-licious
ARG USER_UID
ARG USER_GID
RUN usermod -u $USER_UID www-data && \
  groupmod --gid $USER_GID www-data
COPY --from=builder /opt/search-a-licious/public/ /opt/search-a-licious/public/
