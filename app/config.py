import json
from enum import StrEnum, auto
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
from pydantic.json_schema import GenerateJsonSchema
from pydantic_settings import BaseSettings


class LoggingLevel(StrEnum):
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
    # Path of the search-a-licious yaml configuration file
    config_path: Path | None = None
    redis_expiration: int = 60 * 60 * 36  # 36h
    redis_reader_timeout: int = 5
    elasticsearch_url: str = "http://localhost:9200"
    redis_host: str = "localhost"
    # TODO: this should be in the config below
    openfoodfacts_base_url: str = "https://world.openfoodfacts.org"
    sentry_dns: str | None = None
    log_level: LoggingLevel = LoggingLevel.INFO
    taxonomy_cache_dir: Path = Path("/opt/search/data/taxonomies")


settings = Settings()


class ConfigGenerateJsonSchema(GenerateJsonSchema):
    """Config to add fields to generated JSON schema for Config."""

    def generate(self, schema, mode="validation"):
        json_schema = super().generate(schema, mode=mode)
        json_schema["title"] = "JSON schema for search-a-licious configuration file"
        json_schema["$schema"] = self.schema_dialect
        return json_schema


class TaxonomySourceConfig(BaseModel):
    name: Annotated[str, Field(description="name of the taxonomy")]
    url: Annotated[
        HttpUrl,
        Field(
            description="URL of the taxonomy, must be in JSON format and follows Open Food Facts "
            "taxonomy format."
        ),
    ]


class TaxonomyConfig(BaseModel):
    sources: Annotated[
        list[TaxonomySourceConfig],
        Field(description="configurations of used taxonomies"),
    ]
    supported_langs: Annotated[
        list[str],
        Field(
            description="a list of languages for which we want taxonomized fields "
            "to be always exported during indexing. During indexation, we use the taxonomy "
            "to translate every taxonomized field in a language-specific subfield. The list "
            "of language depends on the value defined here and on the optional "
            "`supported_langs` field that can be defined in each document."
        ),
    ]


class FieldType(StrEnum):
    keyword = auto()
    date = auto()
    double = auto()
    float = auto()
    integer = auto()
    bool = auto()
    text = auto()
    text_lang = auto()
    taxonomy = auto()
    # if the field is not enabled (=not indexed and not parsed), see:
    # https://www.elastic.co/guide/en/elasticsearch/reference/current/enabled.html
    disabled = auto()
    object = auto()

    def is_numeric(self):
        return self in (FieldType.integer, FieldType.float, FieldType.double)


class FieldConfig(BaseModel):
    # name of the field (internal field), it's added here for convenience
    _name: str = ""
    type: Annotated[
        FieldType,
        Field(description="type of the field, see `FieldType` for possible values"),
    ]
    required: Annotated[
        bool,
        Field(description="if required=True, the field is required in the input data"),
    ] = False
    input_field: Annotated[
        str | None,
        Field(description="name of the input field to use when importing data"),
    ] = None
    #
    split: Annotated[
        bool, Field(description="do we split the input field with `split_separator`")
    ] = False
    include_multi_match: Annotated[
        bool,
        Field(
            description="do we include the field in the multi-match query used as baseline results"
        ),
    ] = False
    taxonomy_name: Annotated[
        str | None, Field(description="only for taxonomy field type")
    ] = None
    multi: Annotated[
        bool,
        Field(
            description="can the keyword field contain multiple value (keyword type only)"
        ),
    ] = False

    @property
    def name(self) -> str:
        """Get field name."""
        return self._name

    @model_validator(mode="after")
    def multi_should_be_used_for_selected_type_only(self):
        """Validator that checks that `multi` flag is only True for fields
        with specific types."""
        if (
            not (
                self.type in (FieldType.keyword, FieldType.text, FieldType.bool)
                or self.type.is_numeric()
            )
            and self.multi
        ):
            raise ValueError(f"multi=True is not compatible with type={self.type}")
        return self

    @model_validator(mode="after")
    def taxonomy_name_should_be_used_for_taxonomy_type_only(self):
        """Validator that checks that `taxonomy_name` is only provided for
        fields with type `taxonomy`."""
        if self.type is not FieldType.taxonomy and self.taxonomy_name is not None:
            raise ValueError("taxonomy_name should be provided for taxonomy type only")
        return self

    def get_input_field(self):
        """Return the name of the field to use in input data."""
        return self.input_field or self.name

    def has_lang_subfield(self) -> bool:
        return self.type in (FieldType.taxonomy, FieldType.text_lang)


class IndexConfig(BaseModel):
    name: Annotated[str, Field(description="name of the index alias to use")]
    id_field_name: Annotated[
        str, Field(description="name of the field to use for `_id`")
    ]
    last_modified_field_name: Annotated[
        str,
        Field(
            description="name of the field containing the date of last modification, "
            "used for incremental updates using Redis queues"
        ),
    ]
    number_of_shards: Annotated[
        int, Field(description="number of shards to use for the index")
    ] = 4
    number_of_replicas: Annotated[
        int, Field(description="number of replicas to use for the index")
    ] = 1


class Config(BaseModel):
    index: Annotated[IndexConfig, Field(description="configuration of the index")]
    fields: Annotated[
        dict[str, FieldConfig],
        Field(
            description="configuration of all fields in the index, keys are field "
            "names and values contain the field configuration"
        ),
    ]
    split_separator: Annotated[
        str,
        Field(
            description="separator to use when splitting values, for fields that have split=True"
        ),
    ] = ","
    lang_separator: Annotated[
        str,
        Field(
            description="for `text_lang` FieldType, the separator between the name of the field "
            'and the language code, ex: product_name_it if lang_separator="_"'
        ),
    ] = "_"
    taxonomy: Annotated[
        TaxonomyConfig, Field(description="configuration of the taxonomies used")
    ]
    preprocessor: Annotated[
        str,
        Field(
            description="The full qualified reference to the preprocessor to use before "
            "data import. This is used to adapt the data schema or to add search-a-licious "
            "specific fields for example."
        ),
    ] | None = None
    result_processor: Annotated[
        str,
        Field(
            description="The full qualified reference to the elasticsearch result processor "
            "to use after search query to Elasticsearch. This is used to add custom fields "
            "for example."
        ),
    ] | None = None
    supported_langs: Annotated[
        list[str] | None,
        Field(
            description="A list of all supported languages, it is used to build index mapping"
        ),
    ] = None
    match_phrase_boost: Annotated[
        float, Field(description="How much we boost exact matches on individual fields")
    ] = 2.0
    document_denylist: Annotated[
        set[str], Field(description="list of documents IDs to ignore")
    ] = Field(default_factory=set)

    @model_validator(mode="after")
    def taxonomy_name_should_be_defined(self):
        """Validator that checks that for if `taxonomy_type` is defined for a
        field, it refers to a taxonomy defined in `taxonomy.sources`."""
        defined_taxonomies = [source.name for source in self.taxonomy.sources]
        for field in self.fields.values():
            if (
                field.taxonomy_name is not None
                and field.taxonomy_name not in defined_taxonomies
            ):
                raise ValueError(
                    f"'{field.taxonomy_name}' should be defined in `taxonomy.sources`"
                )
        return self

    @model_validator(mode="after")
    def field_references_must_exist_and_be_valid(self):
        """Validator that checks that every field reference in IndexConfig
        refers to an existing field and is valid."""
        if self.index.id_field_name not in self.fields:
            raise ValueError(
                f"id_field_name={self.index.id_field_name} but field was not declared"
            )

        if self.index.last_modified_field_name not in self.fields:
            raise ValueError(
                f"last_modified_field_name={self.index.last_modified_field_name} but field was not declared"
            )

        last_modified_field = self.fields[self.index.last_modified_field_name]

        if last_modified_field.type != FieldType.date:
            raise ValueError(
                "last_modified_field_name is expected to be of type FieldType.Date"
            )

        return self

    @model_validator(mode="after")
    def if_split_should_be_multi(self):
        """Validator that checks that multi=True if split=True.."""
        for field in self.fields.values():
            if field.split and not field.multi:
                raise ValueError("multi should be True if split=True")
        return self

    @field_validator("fields")
    @classmethod
    def add_field_name_to_each_field(cls, fields):
        for field_name, field_item in fields.items():
            field_item._name = field_name
        return fields

    def get_input_fields(self) -> set[str]:
        return set(self.fields) | {
            field.input_field for field in self.fields if field.input_field is not None
        }

    def get_supported_langs(self) -> set[str]:
        """Return the set of supported languages."""
        return set(self.supported_langs or []) | set(self.taxonomy.supported_langs)

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Create a Config from a yaml configuration file."""
        with path.open("r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def export_json_schema(cls):
        """Export JSON schema."""
        (Path(__file__).parent.parent / "json_schema.json").write_text(
            json.dumps(
                cls.model_json_schema(schema_generator=ConfigGenerateJsonSchema),
                indent=4,
            )
        )


# CONFIG is a global variable that contains the search-a-licious configuration
# used. It is specified by the envvar CONFIG_PATH.
CONFIG: Config | None = None
if settings.config_path:
    if not settings.config_path.is_file():
        raise RuntimeError(f"config file does not exist: {settings.config_path}")

    CONFIG = Config.from_yaml(settings.config_path)


def check_config_is_defined():
    """Raise a RuntimeError if the Config path is not set."""
    if CONFIG is None:
        raise RuntimeError(
            "No configuration is configured, set envvar "
            "CONFIG_PATH with the path of the yaml configuration file"
        )
