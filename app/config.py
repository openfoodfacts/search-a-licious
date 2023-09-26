from enum import StrEnum, auto
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
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


class TaxonomySourceConfig(BaseModel):
    name: str
    url: HttpUrl


class TaxonomyConfig(BaseModel):
    sources: list[TaxonomySourceConfig]
    supported_langs: list[str]


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
    # type of the field, see `FieldType` for possible values
    type: FieldType
    # if required=True, the field is required in the input data
    required: bool = False
    # name of the input field to use when importing data
    input_field: str | None = None
    # do we split the input field with `split_separator`
    split: bool = False
    # do we include the field in the multi-match query used as baseline results
    include_multi_match: bool = False
    # only for taxonomy field type
    taxonomy_name: str | None = None
    # can the keyword field contain multiple value (keyword type only)
    multi: bool = False

    @property
    def name(self):
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
    # name of the index alias to use
    name: str
    # name of the field to use for `_id`
    id_field_name: str
    # name of the field containing the date of last modification, used for
    # incremental updates using Redis queues
    last_modified_field_name: str
    number_of_shards: int = 4
    number_of_replicas: int = 1


class Config(BaseModel):
    # configuration of the index
    index: IndexConfig
    # configuration of all fields in the index, keys are field names and values
    # contain the field configuration
    fields: dict[str, FieldConfig]
    split_separator: str = ","
    # for `text_lang` FieldType, the separator between the name of the field
    # and the language code, ex: product_name_it if lang_separator="_"
    lang_separator: str = "_"
    taxonomy: TaxonomyConfig
    # The full qualified reference to the preprocessor to use before data
    # import This is used to adapt the data schema or to add search-a-licious
    # specific fields for example.
    preprocessor: str | None = None
    # The full qualified reference to the elasticsearch result processor to use
    # after search query to Elasticsearch.
    # This is used to add custom fields for example.
    result_processor: str | None = None
    # A list of supported languages, it is used to build index mapping
    supported_langs: list[str] | None = None
    # How much we boost exact matches on individual fields
    match_phrase_boost: float = 2.0
    # list of documents IDs to ignore
    document_denylist: set[str] = Field(default_factory=set)

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
        return set(self.supported_langs or []) | set(self.taxonomy.supported_langs)

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Create a Config from a yaml configuration file."""
        with path.open("r") as f:
            data = yaml.safe_load(f)
        return cls(**data)


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
