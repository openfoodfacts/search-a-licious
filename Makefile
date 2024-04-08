MOUNT_POINT ?= /mnt
DOCKER_LOCAL_DATA ?= /srv/off/docker_data
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

# load env variables
# also takes into account envrc (direnv file)
ifneq (,$(wildcard ./${ENV_FILE}))
    -include ${ENV_FILE}
    -include .envrc
    export
endif

DOCKER_COMPOSE=docker compose --env-file=${ENV_FILE}
DOCKER_COMPOSE_TEST=COMPOSE_PROJECT_NAME=search_test docker compose --env-file=${ENV_FILE}

#------------#
# Production #
#------------#

create_external_volumes:
	@echo "🔎 Creating external volumes (production only) …"
	@for vol_name in esdata01 esdata02; \
	do \
		vol_name=${COMPOSE_PROJECT_NAME}_$$vol_name; \
		vol_path=${DOCKER_LOCAL_DATA}/$$vol_name; \
		echo creating docker volume $$vol_name at $$vol_path; \
		# ensure directory \
		mkdir -p -v "$$vol_path"; \
		# create volume \
		# this bind mount a folder, it will happen when volume will be used \
		docker volume create --driver=local -o type=none -o o=bind -o device="$$vol_path" "$$vol_name" ; \
	done;

livecheck:
	@echo "🔎 livecheck services…" ; \
	exit_code=0; \
	services=`${DOCKER_COMPOSE} config  --service | tr '\n' ' '`; \
	for service in $$services; do \
	if [ -z `docker compose ps -q $$service` ] || [ -z `docker ps -q --no-trunc | grep $$(${DOCKER_COMPOSE} ps -q $$service)` ]; then \
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
	${DOCKER_COMPOSE} build --progress=plain


up:
ifdef service
	${DOCKER_COMPOSE} up -d ${service} 2>&1
else
	${DOCKER_COMPOSE} up -d 2>&1
endif


down:
	@echo "🔎 Bringing down containers …"
	${DOCKER_COMPOSE} down

#--------#
# Checks #
#--------#

check:
	@echo "🔎 Running all pre-commit hooks"
	pre-commit run --all-files

lint:
	@echo "🔎 Running linters..."
	pre-commit run black --all-files
	${DOCKER_COMPOSE} run --rm search_nodejs npm run format

#-------#
# Tests #
#-------#

test: test_api test_front

test_api:
	@echo "🔎 Running API tests..."
	${DOCKER_COMPOSE_TEST} run --rm api pytest tests/

test_front:
	@echo "🔎 Running front-end tests..."
	${DOCKER_COMPOSE_TEST} run --rm search_nodejs npm run test



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
	${DOCKER_COMPOSE} run --rm api python3 -m app import /opt/search/data/${filepath} --num-processes=2


#-------#
# Tests #
#-------#

unit-tests:
	@echo "🔎 Running unit tests …"
	# change project name to run in isolation
	${DOCKER_COMPOSE_TEST} run --rm api poetry run pytest --cov-report xml --cov=app tests/unit
