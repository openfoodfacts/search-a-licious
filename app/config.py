import json
import logging
from enum import StrEnum, auto
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
from pydantic.json_schema import GenerateJsonSchema
from pydantic_settings import BaseSettings

log = logging.getLogger(__name__)


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


class ScriptType(StrEnum):
    expression = "expression"
    painless = "painless"


class Settings(BaseSettings):
    # Path of the search-a-licious yaml configuration file
    config_path: Path | None = None
    redis_reader_timeout: int = 5
    elasticsearch_url: str = "http://localhost:9200"
    redis_host: str = "localhost"
    redis_port: int = 6379
    sentry_dns: str | None = None
    log_level: LoggingLevel = LoggingLevel.INFO
    taxonomy_cache_dir: Path = Path("data/taxonomies")
    # User-Agent used when fetching resources (taxonomies) or documents
    user_agent: str = "search-a-licious"


settings = Settings()

# Mapping from language 2-letter code to Elasticsearch language analyzer names
ANALYZER_LANG_MAPPING = {
    "en": "english",
    "fr": "french",
    "it": "italian",
    "es": "spanish",
    "de": "german",
    "nl": "dutch",
    "ar": "arabic",
    "hy": "armenian",
    "eu": "basque",
    "bn": "bengali",
    "pt-BR": "brazilian",
    "bg": "bulgarian",
    "ca": "catalan",
    "cz": "czech",
    "da": "danish",
    "et": "estonian",
    "fi": "finnish",
    "gl": "galician",
    "el": "greek",
    "hi": "hindi",
    "hu": "hungarian",
    "id": "indonesian",
    "ga": "irish",
    "lv": "latvian",
    "lt": "lithuanian",
    "no": "norwegian",
    "fa": "persian",
    "pt": "portuguese",
    "ro": "romanian",
    "ru": "russian",
    "sv": "swedish",
    "tr": "turkish",
    "th": "thai",
}


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


class FieldType(StrEnum):
    keyword = auto()
    date = auto()
    half_float = auto()
    scaled_float = auto()
    float = auto()
    double = auto()
    integer = auto()
    short = auto()
    long = auto()
    unsigned_long = auto()
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
    # name of the field (internal field), it's added here for convenience.
    # It's set by the `add_field_name_to_each_field` classmethod.
    name: Annotated[str, Field(description="name of the field, must be unique")] = ""
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
    full_text_search: Annotated[
        bool,
        Field(
            description="do we include perform full text search using this field. If "
            "false, the field is only used during search when filters involving this "
            "field are provided."
        ),
    ] = False
    bucket_agg: Annotated[
        bool,
        Field(
            description="do we add an bucket aggregation to the elasticsearch query for this field. "
            "It is used to return a 'faceted-view' with the number of results for each facet value. "
            "Only valid for keyword or numeric field types."
        ),
    ] = False
    taxonomy_name: Annotated[
        str | None,
        Field(
            description="the name of the taxonomy associated with this field. "
            "It must only be provided for taxonomy field type."
        ),
    ] = None
    add_taxonomy_synonyms: Annotated[
        bool,
        Field(
            description="if True, add all synonyms of the taxonomy values to the index. "
            "The flag is ignored if the field type is not `taxonomy`."
        ),
    ] = True

    @model_validator(mode="after")
    def bucket_agg_should_be_used_for_keyword_and_numeric_types_only(self):
        """Validator that checks that `bucket_agg` is only provided for
        fields with types `keyword`, `double`, `float`, `integer` or `bool`."""
        if self.bucket_agg and not (
            self.type.is_numeric() or self.type in (FieldType.keyword, FieldType.bool)
        ):
            raise ValueError(
                "bucket_agg should be provided for taxonomy or numeric type only"
            )
        return self

    def get_input_field(self):
        """Return the name of the field to use in input data."""
        return self.input_field or self.name

    def has_lang_subfield(self) -> bool:
        return self.type in (FieldType.taxonomy, FieldType.text_lang)


class ESIndexConfig(BaseModel):
    name: Annotated[str, Field(description="name of the index alias to use")]
    id_field_name: Annotated[
        str, Field(description="name of the field to use for `_id`")
    ]
    last_modified_field_name: Annotated[
        str,
        Field(
            description="name of the field containing the date of last modification, "
            "used for incremental updates using Redis queues. The field value must be an "
            "int/float representing the timestamp."
        ),
    ]
    number_of_shards: Annotated[
        int, Field(description="number of shards to use for the index")
    ] = 4
    number_of_replicas: Annotated[
        int, Field(description="number of replicas to use for the index")
    ] = 1


class TaxonomyIndexConfig(BaseModel):
    """We have an index storing multiple taxonomies

    It enables functions like auto-completion, or field suggestions
    as well as enrichment of requests with synonyms
    """

    name: Annotated[
        str,
        Field(description="name of the taxonomy index alias to use"),
    ]
    number_of_shards: Annotated[
        int, Field(description="number of shards to use for the index")
    ] = 4
    number_of_replicas: Annotated[
        int, Field(description="number of replicas to use for the index")
    ] = 1


class TaxonomyConfig(BaseModel):
    """Configuration of taxonomies,
    that is collections of entries with synonyms in multiple languages

    Field may be linked to taxonomies.
    """

    sources: Annotated[
        list[TaxonomySourceConfig],
        Field(description="configurations of used taxonomies"),
    ]
    exported_langs: Annotated[
        list[str],
        Field(
            description="a list of languages for which we want taxonomized fields "
            "to be always exported during indexing. During indexing, we use the taxonomy "
            "to translate every taxonomized field in a language-specific subfield. The list "
            "of language depends on the value defined here and on the optional "
            "`taxonomy_langs` field that can be defined in each document.",
        ),
    ]
    index: Annotated[
        TaxonomyIndexConfig,
        Field(
            description="configuration of the taxonomy index. There is a single index for all taxonomies."
        ),
    ]


class ScriptConfig(BaseModel):
    """Scripts can be used to sort results of a search.

    This use ElasticSearch internal capabilities
    """

    lang: Annotated[
        ScriptType,
        Field(description="The script language, as supported by Elasticsearch"),
    ] = ScriptType.expression
    source: Annotated[
        str,
        Field(description="The source of the script"),
    ]
    params: (
        Annotated[
            dict[str, Any],
            Field(
                description="Params for the scripts. We need this to retrieve and validate parameters"
            ),
        ]
        | None
    )
    static_params: (
        Annotated[
            dict[str, Any],
            Field(
                description="Additional params for the scripts that can't be supplied by the API (constants)"
            ),
        ]
        | None
    )
    # Or some type checking/transformation ?


class IndexConfig(BaseModel):
    """Inside the config file we can have several indexes defined.

    This object gives configuration for one index.
    """

    index: Annotated[
        ESIndexConfig, Field(description="configuration of the Elasticsearch index")
    ]
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
    primary_color: Annotated[
        str,
        Field(description="Used for vega charts. Should be html code."),
    ] = "#aaa"
    accent_color: Annotated[
        str,
        Field(
            description="Used for vega. Should be html code."
            'and the language code, ex: product_name_it if lang_separator="_"'
        ),
    ] = "#222"
    taxonomy: Annotated[
        TaxonomyConfig, Field(description="configuration of the taxonomies used")
    ]
    supported_langs: Annotated[
        list[str],
        Field(
            description="A list of all supported languages, it is used to build index mapping"
        ),
    ]
    document_fetcher: Annotated[
        str,
        Field(
            description="The full qualified reference to the document fetcher, i.e. the class "
            "responsible from fetching the document using the document ID present in the Redis "
            "Stream.",
            examples=["app.openfoodfacts.DocumentFetcher"],
        ),
    ]
    preprocessor: (
        Annotated[
            str,
            Field(
                description="The full qualified reference to the preprocessor to use before "
                "data import. This is used to adapt the data schema or to add search-a-licious "
                "specific fields for example.",
                examples=["app.openfoodfacts.DocumentPreprocessor"],
            ),
        ]
        | None
    ) = None
    result_processor: (
        Annotated[
            str,
            Field(
                description="The full qualified reference to the elasticsearch result processor "
                "to use after search query to Elasticsearch. This is used to add custom fields "
                "for example.",
                examples=["app.openfoodfacts.ResultProcessor"],
            ),
        ]
        | None
    ) = None
    scripts: (
        Annotated[
            dict[str, ScriptConfig],
            Field(
                description="You can add scripts that can be used for sorting results",
            ),
        ]
        | None
    ) = None
    match_phrase_boost: Annotated[
        float, Field(description="How much we boost exact matches on individual fields")
    ] = 2.0
    document_denylist: Annotated[
        set[str], Field(description="list of documents IDs to ignore")
    ] = Field(default_factory=set)

    redis_stream_name: Annotated[
        str | None,
        Field(
            description="name of the Redis stream to read from when listening to document updates. "
            "If not provided, document updates won't be listened to for this index."
        ),
    ] = None

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
        """Validator that checks that every field reference in ESIndexConfig
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

    @field_validator("fields")
    @classmethod
    def add_field_name_to_each_field(cls, fields: dict[str, FieldConfig]):
        for field_name, field_item in fields.items():
            field_item.name = field_name
        return fields

    def get_supported_langs(self) -> set[str]:
        """Return the set of supported languages for `text_lang` fields.

        It's used to know which language-specific subfields to create.
        """
        return (
            set(self.supported_langs or [])
            # only keep langs for which a built-in analyzer built-in, other
            # langs will be stored in a unique `other` subfield
        ) & set(ANALYZER_LANG_MAPPING)

    def get_taxonomy_langs(self) -> set[str]:
        """Return the set of exported languages for `taxonomy` fields.

        It's used to know which language-specific subfields to create.
        """
        # only keep langs for which a built-in analyzer built-in, other
        # langs will be stored in a unique `other` subfield
        return (set(self.taxonomy.exported_langs)) & set(ANALYZER_LANG_MAPPING)

    def get_fields_with_bucket_agg(self):
        return [
            field_name for field_name, field in self.fields.items() if field.bucket_agg
        ]


class Config(BaseModel):
    """This is the global config object that reflects
    the yaml configuration file.

    Validations will be performed while we load it.
    """

    indices: dict[str, IndexConfig] = Field(
        description="configuration of indices. "
        "The key is the ID of the index that can be referenced at query time. "
        "One index corresponds to a specific set of documents and can be queried independently."
    )
    default_index: Annotated[
        str,
        Field(
            description="the default index to use when no index is specified in the query",
        ),
    ]

    @model_validator(mode="after")
    def defaut_index_must_exist(self):
        """Validator that checks that default_index exists."""
        if self.default_index not in self.indices:
            raise ValueError(
                f"default_index={self.default_index} but index was not declared (available indices: {list(self.indices.keys())})"
            )
        return self

    @model_validator(mode="after")
    def redis_stream_name_should_be_unique(self):
        """Validator that checks that every redis_stream_name is unique."""
        redis_stream_names = [
            index.redis_stream_name
            for index in self.indices.values()
            if index.redis_stream_name is not None
        ]
        if len(redis_stream_names) != len(set(redis_stream_names)):
            raise ValueError("redis_stream_name should be unique")
        return self

    def get_index_config(self, index_id: str | None) -> tuple[str, IndexConfig]:
        """Return a (index_id, IndexConfig) for the given index_id.

        If no index_id is provided, the default index is used.
        If the index_id is not found, (index_id, None) is returned.
        """
        if index_id is None:
            index_id = self.default_index
        return index_id, self.indices[index_id]

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Create a Config from a yaml configuration file."""
        with path.open("r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def export_json_schema(cls):
        """Export JSON schema."""
        (Path(__file__).parent.parent / "config_schema.json").write_text(
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


def set_global_config(config_path: Path):
    global CONFIG
    CONFIG = Config.from_yaml(config_path)
