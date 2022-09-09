# syntax = docker/dockerfile:1.2
# Base user uid / gid keep 1000 on prod, align with your user on dev
ARG USER_UID=1000
ARG USER_GID=1000


FROM python:3.9
# Instructions from https://fastapi.tiangolo.com/deployment/docker/
ARG USER_UID
ARG USER_GID
RUN groupadd -g $USER_GID off && \
    useradd -u $USER_UID -g off -m off && \
    mkdir -p /home/off && \
    mkdir -p /code && \
    chown off:off -R /code /home/off
WORKDIR /code
COPY --chown=off:off ./requirements.txt /code/requirements.txt
RUN  pip install --no-cache-dir --upgrade -r /code/requirements.txt

USER off:off
COPY --chown=off:off ./app /code/app
CMD ["uvicorn", "app.api:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
