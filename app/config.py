import logging
from enum import StrEnum, auto
from inspect import cleandoc as cd_
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
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


class ScriptType(StrEnum):
    expression = "expression"
    painless = "painless"


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
    """Configuration on how to fetch a particular taxonomy."""

    name: Annotated[
        str,
        Field(
            description=cd_(
                """Name of the taxonomy

                This is the name you will use in the configuration (and the API)
                to reference this taxonomy
                """
            )
        ),
    ]
    url: Annotated[
        HttpUrl,
        Field(
            description=cd_(
                """URL of the taxonomy.

                The target file must be in JSON format
                and follows Open Food Facts JSON taxonomy format.

                This is a dict where each key correspond to a taxonomy entry id,
                values are dict with following properties:

                * name: contains a dict giving the name (string) for this entry
                  in various languages (keys are language codes)
                * synonyms: contains a dict giving a list of synonyms by language code
                * parents: contains a list of direct parent ids (taxonomy is a directed acyclic graph)

                Other keys correspond to properties associated to this entry (eg. wikidata id).
                """
            )
        ),
    ]


class FieldType(StrEnum):
    """Supported field types in Search-a-Licious are:

    * keyword: string values that won't be interpreted (tokenized).
      Good for things like tags, serial, property values, etc.
    * date: Date fields
    * double, float, half_float, scaled_float:
      different ways of storing floats with different capacity
    * short, integer, long, unsigned_long :
      integers (with different capacity:  8 / 16 / 32 bits)
    * bool: boolean (true / false) values
    * text: a text which is tokenized to enable full text search
    * text_lang: like text, but with different values in different languages.
      Tokenization will use analyzers specific to each languages.
    * taxonomy: a field akin to keyword but
      with support for matching using taxonomy synonyms and translations
      (and in fact also a text mapping possibility)
    * disabled: a field that is not stored nor searchable
      (see [Elasticsearch help])
    * object: this field contains a dict with sub-fields.
    """

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
        """Return wether this field type can be considered numeric"""
        return self in (FieldType.integer, FieldType.float, FieldType.double)


# add url to FieldType doc
if FieldType.__doc__:
    FieldType.__doc__ += f"\n\n[Elasticsearch help]: {ES_DOCS_URL}/enabled.html"


class FieldConfig(BaseModel):
    # name of the field (internal field), it's added here for convenience.
    # It's set by the `add_field_name_to_each_field` classmethod.
    name: Annotated[str, Field(description="name of the field (must be unique")] = ""
    type: Annotated[
        FieldType,
        Field(description=f"Type of the field\n\n{cd_(FieldType.__doc__)}"),
    ]
    required: Annotated[
        bool,
        Field(
            description=cd_(
                """if required=True, the field is required in the input data

                An entry that does not contains a value for this field will be rejected.
                """
            )
        ),
    ] = False
    input_field: Annotated[
        str | None,
        Field(
            description=cd_(
                """name of the input field to use when importing data

                By default, Search-a-licious use the same name as the field name.

                This is useful to index the same field using different types or configurations.
                """
            )
        ),
    ] = None
    split: Annotated[
        bool,
        Field(
            description=cd_(
                """do we split the input field with `split_separator` ?

                This is useful if you have some text fields that contains list of values,
                (for example a comma separated list of values, like apple,banana,carrot).

                You must set split_separator to the character that separates the values in the dataset.
                """
            )
        ),
    ] = False
    full_text_search: Annotated[
        bool,
        Field(
            description=cd_(
                """Wether this field in included on default full text search.

                If `false`, the field is only used during search
                when filters involving this field are provided
                (as opposed to full text search expressions without any explicit field).
                """
            )
        ),
    ] = False
    bucket_agg: Annotated[
        bool,
        Field(
            description=cd_(
                """do we add an bucket aggregation to the elasticsearch query for this field.

                It is used to return a 'faceted-view' with the number of results for each facet value,
                or to generate bar charts.

                Only valid for keyword or numeric field types.
                """
            )
        ),
    ] = False
    taxonomy_name: Annotated[
        str | None,
        Field(
            description=cd_(
                """the name of the taxonomy associated with this field.

                It must only be provided for taxonomy field type.
                """
            )
        ),
    ] = None
    add_taxonomy_synonyms: Annotated[
        bool,
        Field(
            description=cd_(
                """if True, add all synonyms of the taxonomy values to the index.
                The flag is ignored if the field type is not `taxonomy`.
                """
            )
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
        """Return wether this field type is supposed to have different values
        per languages"""
        return self.type in (FieldType.taxonomy, FieldType.text_lang)


class BaseESIndexConfig(BaseModel):
    """Base class for configuring ElasticSearch indexes"""

    name: Annotated[
        str,
        Field(
            description=cd_(
                """Name of the index alias to use.

                Search-a-licious will create an index using this name and an import date,
                but alias will always point to the latest index.

                The alias must not already exists in your ElasticSearch instance.
                """
            )
        ),
    ]
    number_of_shards: Annotated[
        int,
        Field(
            description=cd_(
                f"""Number of shards to use for the index.

                Shards are useful to distribute the load on your cluster.
                (see [index settings]({ES_DOCS_URL}/index-modules.html#_static_index_settings))
                """
            )
        ),
    ] = 4
    number_of_replicas: Annotated[
        int,
        Field(
            description=cd_(
                f"""Number of replicas to use for the index.

                More replica means more resiliency but also more disk space and memory.

                (see [index settings]({ES_DOCS_URL}/index-modules.html#_static_index_settings))
                """
            )
        ),
    ] = 1


class ESIndexConfig(BaseESIndexConfig):
    """This is the configuration for the main index containing the data.

    It's used to create the index in ElasticSearch, and configure its mappings
    (along with the *fields* config)
    """

    id_field_name: Annotated[
        str,
        Field(
            description=cd_(
                """Name of the field to use for `_id`.
                it is mandatory to provide one.

                If your dataset does not have an identifier field,
                you should use a document preprocessor to compute one (see `preprocessor`).
                """
            )
        ),
    ]
    last_modified_field_name: Annotated[
        str,
        Field(
            description=cd_(
                """Name of the field containing the date of last modification,
                in your indexed objects.

                This is used for incremental updates using Redis queues.

                The field value must be an int/float representing the timestamp.
                """
            )
        ),
    ]


class TaxonomyIndexConfig(BaseESIndexConfig):
    """This is the configuration of
    the ElasticSearch index storing the taxonomies.

    All taxonomies are stored within the same index.

    It enables functions like auto-completion, or field suggestions
    as well as enrichment of requests with synonyms.
    """


class TaxonomyConfig(BaseModel):
    """Configuration of taxonomies,
    that is collections of entries with synonyms in multiple languages.

    See [Explain taxonomies](../explain-taxonomies)

    Field may be linked to taxonomies.

    It enables enriching search with synonyms,
    as well as providing suggestions,
    or informative facets.

    Note: if you define taxonomies, you must import them using
    [import-taxonomies command](../ref-python/cli.html#python3-m-app-import-taxonomies)
    """

    sources: Annotated[
        list[TaxonomySourceConfig],
        Field(description="Configurations of taxonomies that this project will use."),
    ]
    exported_langs: Annotated[
        list[str],
        Field(
            description=cd_(
                """a list of languages for which
                we want taxonomized fields to be always exported during indexing.

                During indexing, we use the taxonomy to translate every taxonomized field
                in a language-specific subfield.

                The list of language depends on the value defined here and on the optional
                `taxonomy_langs` field that can be defined in each document.

                Beware that providing many language might inflate the index size.
                """,
            )
        ),
    ]
    index: Annotated[
        TaxonomyIndexConfig,
        Field(description=TaxonomyIndexConfig.__doc__),
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


INDEX_CONFIG_INDEX_DESCRIPTION = """
Through this settings, you can tweak some of the index settings.
"""


class IndexConfig(BaseModel):
    """This object gives configuration for one index.

    One index usually correspond to one dataset.
    """

    index: Annotated[ESIndexConfig, Field(description=ESIndexConfig.__doc__)]
    fields: Annotated[
        dict[str, FieldConfig],
        Field(
            description=cd_(
                """Configuration of all fields we need to store in the index.

                Keys are field names,
                values contain the field configuration.

                This is a very important part of the configuration.

                Most of the ElasticSearch mapping will depends on it.
                ElasticSearch will also use this configuration
                to provide intended behaviour.

                (see also [Explain Configuration](./explain_configuration.md#fields))

                If you change those settings you will have to re-index all the data.
                (But you can do so in the background).
                """
            )
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
        Field(description="Used for vega charts. Use CSS color code."),
    ] = "#aaa"
    accent_color: Annotated[
        str,
        Field(description="Used for vega. Should be CSS color code."),
    ] = "#222"
    taxonomy: Annotated[TaxonomyConfig, Field(description=TaxonomyConfig.__doc__)]
    supported_langs: Annotated[
        list[str],
        Field(
            description="A list of all supported languages, it is used to build index mapping",
            examples=[["en", "fr", "it"]],
        ),
    ]
    document_fetcher: Annotated[
        str,
        Field(
            description=cd_(
                """The full qualified reference to the document fetcher,
                i.e. the class responsible from fetching the document.
                using the document ID present in the Redis Stream.

                It should inherit `app._import.BaseDocumentFetcher`
                and specialize the `fetch_document` method.

                To keep things sleek,
                you generally have few item fields in the event stream payload.
                This class will fetch the full document using your application API.
                """
            ),
            examples=["app.openfoodfacts.DocumentFetcher"],
        ),
    ]
    preprocessor: (
        Annotated[
            str,
            Field(
                description=cd_(
                    """The full qualified reference to the preprocessor
                    to use before data import.

                    This class must inherit `app.indexing.BaseDocumentPreprocessor`
                    and specialize the `preprocess` method.

                    This is used to adapt the data schema
                    or to add search-a-licious specific fields
                    for example.
                    """
                ),
                examples=["app.openfoodfacts.DocumentPreprocessor"],
            ),
        ]
        | None
    ) = None
    result_processor: (
        Annotated[
            str,
            Field(
                description=cd_(
                    """The full qualified reference to the elasticsearch result processor
                    to use after search query to Elasticsearch.

)                    This class must inherit `app.postprocessing.BaseResultProcessor`
                    and specialize the `process_after`

                    This is can be used to add custom fields computed from index content.
                    """
                ),
                examples=["app.openfoodfacts.ResultProcessor"],
            ),
        ]
        | None
    ) = None
    scripts: (
        Annotated[
            dict[str, ScriptConfig],
            Field(
                description=cd_(
                    """You can add scripts that can be used for sorting results.

                    Each key is a script name, with it's configuration.
                    """
                ),
            ),
        ]
        | None
    ) = None
    match_phrase_boost: Annotated[
        float,
        Field(
            description=cd_(
                """How much we boost exact matches on individual fields

            This only makes sense when using "best match" order.
            """
            )
        ),
    ] = 2.0
    document_denylist: Annotated[
        set[str],
        Field(
            description=cd_(
                """list of documents IDs to ignore.

            Use this to skip some documents at indexing time.
            """
            )
        ),
    ] = Field(default_factory=set)

    redis_stream_name: Annotated[
        str | None,
        Field(
            description=cd_(
                """Name of the Redis stream to read from when listening to document updates.

                If not provided, document updates won't be listened to for this index.
                """
            )
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
        """It's handy to have the name of the field in the field definition"""
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


CONFIG_DESCRIPTION_INDICES = """
A Search-a-licious instance only have one configuration file,
but is capable of serving multiple datasets

It provides a section for each index you want to create (corresponding to a dataset).

The key is the ID of the index that can be referenced at query time.
One index corresponds to a specific set of documents and can be queried independently.

If you have multiple indexes, one of those index must be designed as the default one,
see `default_index`.
"""


class Config(BaseModel):
    """Search-a-licious server configuration.

    The configuration is loaded from a YAML file,
    that must satisfy this schema.

    Validations will be performed while we load it.
    """

    indices: dict[str, IndexConfig] = Field(
        description="configuration of indices.\n\n" + CONFIG_DESCRIPTION_INDICES
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
