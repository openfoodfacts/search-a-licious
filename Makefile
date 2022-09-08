MOUNT_POINT ?= /mnt
DOCKER_LOCAL_DATA ?= /srv/off/docker_data
ENV_FILE ?= .env
# we need COMPOSE_PROJECT_NAME for some commands
# take it form env, or from env file
COMPOSE_PROJECT_NAME ?= $(shell grep COMPOSE_PROJECT_NAME ${ENV_FILE} | cut -d '=' -f 2)
DOCKER_COMPOSE=docker-compose --env-file=${ENV_FILE}

#------------#
# Production #
#------------#

test:
	echo ${ENV_FILE} ${COMPOSE_PROJECT_NAME}

create_external_volumes:
	@echo "🥫 Creating external volumes (production only) …"
	@for vol_name in esdata01 esdata02 rediscache; \
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
	@echo "🥫 livecheck services…" ; \
	exit_code=0; \
	services=`${DOCKER_COMPOSE} config  --service | tr '\n' ' '`; \
	for service in $$services; do \
	if [ -z `docker-compose ps -q $$service` ] || [ -z `docker ps -q --no-trunc | grep $$(${DOCKER_COMPOSE} ps -q $$service)` ]; then \
		echo "$$service: DOWN"; \
		exit_code=1; \
	else \
		echo "$$service: UP"; \
	fi \
	done; \
	[ $$exit_code -eq 0 ] && echo "Success !"; \
	exit $$exit_code;
