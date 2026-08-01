MOUNT_POINT ?= /mnt
ENV_FILE ?= .env
# for dev we need to align user uid with the one in the container
# this is handled through build args
UID ?= $(shell id -u)
export USER_UID:=${UID}
# prefer to use docker buildkit
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
# we need COMPOSE_PROJECT_NAME for some commands
# take it form env, or from env file
COMPOSE_PROJECT_NAME ?= $(shell grep COMPOSE_PROJECT_NAME ${ENV_FILE} | cut -d '=' -f 2)

# allows to commands with sudo if needed
#   SUDO=sudo make up
SUDO ?=

# load env variables
# also takes into account envrc (direnv file)
ifneq (,$(wildcard ./${ENV_FILE}))
    -include ${ENV_FILE}
    -include .envrc
    export
endif

DOCKER = $(SUDO) docker
DOCKER_COMPOSE = $(DOCKER) compose --env-file=${ENV_FILE}
DOCKER_COMPOSE_TEST = $(SUDO) COMPOSE_PROJECT_NAME=search_test $(DOCKER_COMPOSE)

.PHONY: build create_external_volumes livecheck up down test test_front test_front_watch test_api import-dataset import-taxonomies sync-scripts build-translations generate-openapi check check_front check_translations lint lint_back lint_front
#------------#
# Production #
#------------#

create_external_volumes:
	@echo "🔎 Creating external volumes (production only) …"
	@for vol_name in esdata01 esdata02 es_synonyms; \
	do \
		vol_name=${COMPOSE_PROJECT_NAME}_$$vol_name; \
		echo creating docker volume $$vol_name \
		# create volume \
		# this bind mount a folder, it will happen when volume will be used \
		${DOCKER} volume create --driver=local "$$vol_name" ; \
	done;

livecheck:
	@echo "🔎 livecheck services…" ; \
	exit_code=0; \
	services=`${DOCKER_COMPOSE} config  --service | tr '\n' ' '`; \
	for service in $$services; do \
	if [ -z `${DOCKER} compose ps -q $$service` ] || [ -z `${DOCKER} ps -q --no-trunc | grep $$(${DOCKER_COMPOSE} ps -q $$service)` ]; then \
		echo "$$service: DOWN"; \
		exit_code=1; \
	else \
		echo "$$service: UP"; \
	fi \
	done; \
	[ $$exit_code -eq 0 ] && echo "Success !"; \
	exit $$exit_code;

#-------------------#
# Compose shortcuts #
#-------------------#

build:
	@echo "🔎 building docker (for dev)"
	${DOCKER_COMPOSE} build ${args}


up: _ensure_network
ifdef service
	${DOCKER_COMPOSE} up -d ${service} 2>&1
else
	${DOCKER_COMPOSE} up -d 2>&1
endif


down:
	@echo "🔎 Bringing down containers …"
	${DOCKER_COMPOSE} down

_ensure_network:
	${DOCKER} network inspect ${COMMON_NET_NAME} >/dev/null || ${DOCKER} network create -d bridge ${COMMON_NET_NAME}

#--------#
# Checks #
#--------#

check:
	@echo "🔎 Running all pre-commit hooks"
	pre-commit run --all-files

# note: this is called by pre-commit
check_front:  _ensure_network
	${DOCKER_COMPOSE} run --rm -T search_nodejs npm run check

# note: this is called by pre-commit, it will also extract translations
check_translations:
	@echo "🔎 Checking translations …"
	cd frontend && rm -rf node_modules && npm ci && npm run translations:extract

lint: lint_back lint_front

lint_back:
	@echo "🔎 Running linters for backend code..."
	pre-commit run black --all-files

lint_front:
	@echo "🔎 Running linters for frontend code..."
	${DOCKER_COMPOSE} run --rm search_nodejs npm run format

tsc_watch:
	@echo "🔎 Running front-end tsc in watch mode..."
	${DOCKER_COMPOSE} run --rm search_nodejs npm run build:watch

update_poetry_lock:
	@echo "🔎 Updating poetry.lock"
	${DOCKER_COMPOSE} run --rm api poetry lock --no-update

#-------#
# Tests #
#-------#

test: _ensure_network check_poetry_lock test_api test_front

check_poetry_lock:
	@echo "🔎 Checking poetry.lock"
# we have to mount whole project folder for pyproject will be checked
	${DOCKER_COMPOSE} run -v $$(pwd):/project -w /project --rm api poetry check --lock

test_api: test_api_unit test_api_integration

test_api_unit:
	@echo "🔎 Running API unit tests..."
	${DOCKER_COMPOSE_TEST} run --rm api pytest ${args} tests/ --ignore=tests/int

# you can use keep_es=1 to avoid stopping elasticsearch after tests (useful during development)
test_api_integration:
	@echo "🔎 Running API integration tests..."
	${DOCKER_COMPOSE_TEST} up -d es01 es02 elasticvue
	${DOCKER_COMPOSE_TEST} run --rm api pytest ${args} tests/ --ignore=tests/unit
	test -z "${keep_es}" && ${DOCKER_COMPOSE_TEST} stop es01 es02 elasticvue || true


test_front:
	@echo "🔎 Running front-end tests..."
	${DOCKER_COMPOSE_TEST} run --rm search_nodejs npm run test

test_front_watch:
	@echo "🔎 Running front-end tests..."
	${DOCKER_COMPOSE_TEST} run --rm search_nodejs npm run test:watch

test_clean:
	@echo "🔎 Cleaning tests instances..."
	${DOCKER_COMPOSE_TEST} down -v

#-----------#
# Utilities #
#-----------#

guard-%: # guard clause for targets that require an environment variable (usually used as an argument)
	@ if [ "${${*}}" = "" ]; then \
   		echo "Environment variable '$*' is mandatory"; \
   		echo use "make ${MAKECMDGOALS} $*=you-args"; \
   		exit 1; \
	fi;

import-dataset: guard-filepath
	@echo "🔎 Importing data …"
	${DOCKER_COMPOSE} run --rm api python3 -m app import /opt/search/data/${filepath} ${args} --num-processes=2

import-taxonomies:
	@echo "🔎 Importing taxonomies …"
	${DOCKER_COMPOSE} run --rm api python3 -m app import-taxonomies ${args}

sync-scripts:
	@echo "🔎 Syncing scripts …"
	${DOCKER_COMPOSE} run --rm api python3 -m app sync-scripts

build-translations:
	@echo "🔎 Building translations …"
	${DOCKER_COMPOSE} run --rm search_nodejs npm run translations:build

cleanup-indexes:
	@echo "🔎 Cleaning indexes …"
	${DOCKER_COMPOSE} run --rm api python3 -m app cleanup-indexes ${args}

generate-openapi: _ensure_network
	@echo "🔎 Generating OpenAPI spec …"
	${DOCKER_COMPOSE} run --rm api python3 -m app export-openapi /opt/search/data/searchalicious-openapi.yml

generate-custom-elements: _ensure_network
	@echo "🔎 Generating custome-elements.json …"
	${DOCKER_COMPOSE} run --rm search_nodejs npm run analyze

generate-config-schema: _ensure_network
	@echo "🔎 Generating config-schema.yml …"
	${DOCKER_COMPOSE} run --rm api python3 -m app export-config-schema /opt/search/data/searchalicious-config-schema.yml

generate-settings-schema: _ensure_network
	@echo "🔎 Generating settings-schema.yml …"
	${DOCKER_COMPOSE} run --rm api python3 -m app export-settings-schema /opt/search/data/searchalicious-settings-schema.yml

#-------#
# Tests #
#-------#

unit-tests:
	@echo "🔎 Running unit tests …"
	# change project name to run in isolation
	${DOCKER_COMPOSE_TEST} run --rm api poetry run pytest --cov-report xml --cov=app tests/unit
