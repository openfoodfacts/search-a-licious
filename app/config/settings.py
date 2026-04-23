import functools
import logging
from enum import StrEnum, auto
from inspect import cleandoc as cd_
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import (
    BaseModel,
    Field,
    FileUrl,
    HttpUrl,
    field_validator,
    model_validator,
)
from pydantic.json_schema import GenerateJsonSchema
from pydantic_settings import BaseSettings

log = logging.getLogger(__name__)
ES_DOCS_URL = "https://www.elastic.co/guide/en/elasticsearch/reference/current"
class LoggingLevel(StrEnum):
    """Accepted logging levels

    * NOTSET - means no los
    * DEBUG / INFO / WARNING / ERROR / CRITICAL
      - match standard Python logging levels
    """

    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    def to_int(self):
        if self is LoggingLevel.NOTSET:
            return 0
        elif self is LoggingLevel.DEBUG:
            return 10
        elif self is LoggingLevel.INFO:
            return 20
        elif self is LoggingLevel.WARNING:
            return 30
        elif self is LoggingLevel.ERROR:
            return 40
        elif self is LoggingLevel.CRITICAL:
            return 50


class Settings(BaseSettings):
    """Settings for Search-a-licious

    The most important settings is `config_path`.

    Those settings can be overridden through environment
    by using the name in capital letters.
    If you use docker compose, a good way to do that
    is to modify those values in your .env file.
    """

    config_path: Annotated[
        Path | None,
        Field(
            description=cd_(
                """Path to the search-a-licious yaml configuration file.

                See [Explain configuration file](../explain-configuration/) for more information
                """
            )
        ),
    ] = None
    elasticsearch_url: Annotated[
        str,
        Field(
            description=cd_(
                """URL to the ElasticSearch instance

                Bare in mind this is from inside the container.
                """
            )
        ),
    ] = "http://localhost:9200"
    redis_host: Annotated[
        str,
        Field(
            description=cd_(
                """Host for the Redis instance containing event stream

                Bare in mind this is from inside the container.
                """
            )
        ),
    ] = "localhost"
    redis_port: Annotated[
        int,
        Field(description="Port for the redis host instance containing event stream"),
    ] = 6379
    redis_reader_timeout: Annotated[
        int, Field(description="timeout in seconds to read redis event stream")
    ] = 5
    sentry_dns: Annotated[
        str | None,
        Field(
            description="Sentry DNS to report incident, if None no incident is reported"
        ),
    ] = None
    log_level: Annotated[
        LoggingLevel, Field(description=f"Log level. {LoggingLevel.__doc__}")
    ] = LoggingLevel.INFO
    taxonomy_cache_dir: Annotated[
        Path,
        Field(
            description="Directory where to store taxonomies before ingestion to ElasticSearch"
        ),
    ] = Path("data/taxonomies")
    user_agent: Annotated[
        str,
        Field(
            description="User-Agent used when fetching resources (taxonomies) or documents"
        ),
    ] = "search-a-licious"
    synonyms_path: Annotated[
        Path,
        Field(
            description="Path of the directory that will contain synonyms for ElasticSearch instances"
        ),
    ] = Path("/opt/search/synonyms")


settings = Settings()

# Mapping from language 2-letter code to Elasticsearch language analyzer names
class SettingsGenerateJsonSchema(GenerateJsonSchema):
    """Config to add fields to generated JSON schema for Settings."""

    def generate(self, schema, mode="validation"):
        json_schema = super().generate(schema, mode=mode)
        json_schema["title"] = "JSON schema for search-a-licious settings"
        json_schema["$schema"] = self.schema_dialect
        return json_schema


