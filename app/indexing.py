import abc
import datetime
import re

from elasticsearch_dsl import Date, Index, Mapping

from app.config import CONFIG, Config, FieldConfig, FieldType, TaxonomySourceConfig
from app.dsl import generate_dsl_field
from app.taxonomy import get_taxonomy
from app.types import JSONType
from app.utils import load_class_object_from_string


def preprocess_field(d: JSONType, input_field: str, split: bool, split_separator: str):
    input_value = d.get(input_field)

    if not input_value:
        return None
    if split:
        input_value = input_value.split(split_separator)

    return input_value


class DocumentPreprocessor(abc.ABC):
    def __init__(self, config: Config) -> None:
        self.config = config

    @abc.abstractmethod
    def preprocess(self, document: JSONType) -> JSONType:
        """Preprocess the document before data ingestion in Elasticsearch.

        This can be used to make document schema compatible with the project
        schema or to add custom fields.
        """
        pass


def process_text_lang_field(
    data: JSONType, field: FieldConfig, config: Config
) -> JSONType | None:
    field_input = {}
    input_field = field.get_input_field()
    for target_key in (
        k
        for k in data
        if re.fullmatch(
            f"{re.escape(input_field)}{config.lang_separator}\w\w([-_]\w\w)?", k
        )
    ):
        input_value = preprocess_field(
            data,
            target_key,
            split=field.split,
            split_separator=config.split_separator,
        )
        if input_value is None:
            continue
        lang = target_key.rsplit(config.lang_separator, maxsplit=1)[-1]
        field_input[lang] = input_value

    return field_input if field_input else None


def process_taxonomy_field(
    data: JSONType, field: FieldConfig, config: Config
) -> JSONType | None:
    field_input = {}
    input_field = field.get_input_field()
    input_value = preprocess_field(
        data, input_field, split=field.split, split_separator=config.split_separator
    )
    if input_value is None:
        return None

    taxonomy_config = config.taxonomy
    taxonomy_sources_by_name = {
        source.name: source for source in taxonomy_config.sources
    }
    taxonomy_source_config: TaxonomySourceConfig = taxonomy_sources_by_name[
        field.taxonomy_name
    ]
    taxonomy = get_taxonomy(taxonomy_source_config.name, taxonomy_source_config.url)

    # to know in which language we should translate the tags using the taxonomy, we use:
    # - the language list defined in the taxonomy config: for every item, we translate
    #   the tags for this list of languages
    # - a custom list of supported languages for the item, this is used to allow indexing
    #   tags for an item that is available in specific countries
    supported_langs = set(taxonomy_config.supported_langs) | set(
        data.get("supported_langs", [])
    )
    for lang in supported_langs:
        for single_tag in input_value:
            if (value := taxonomy.get_localized_name(single_tag, lang)) is not None:
                field_input.setdefault(lang, []).append(value)

    return field_input if field_input else None


class DocumentProcessor:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.preprocessor: DocumentPreprocessor | None

        if config.preprocessor is not None:
            preprocessor_cls = load_class_object_from_string(config.preprocessor)
            self.preprocessor = preprocessor_cls(config)
        else:
            self.preprocessor = None

    def from_dict(self, d: JSONType) -> JSONType | None:
        id_field_name = self.config.index.id_field_name

        _id = d.get(id_field_name)
        if _id is None or _id in self.config.document_denylist:
            # We don't process the document if it has no ID or if it's in the denylist
            return None

        inputs = {
            "last_indexed_datetime": datetime.datetime.utcnow(),
            "_id": _id,
        }
        d = self.preprocessor.preprocess(d) if self.preprocessor is not None else d

        for field in self.config.fields:
            input_field = field.get_input_field()

            if field.type == FieldType.text_lang:
                field_input = process_text_lang_field(d, field, self.config)

            elif field.type == FieldType.taxonomy:
                field_input = process_taxonomy_field(d, field, self.config)

            else:
                field_input = preprocess_field(
                    d,
                    input_field,
                    split=field.split,
                    split_separator=self.config.split_separator,
                )

            if field_input:
                inputs[field.name] = field_input

        return inputs


def generate_mapping_object(config: Config) -> Mapping:
    mapping = Mapping()
    supported_langs = CONFIG.get_supported_langs()
    for field in config.fields:
        mapping.field(
            field.name, generate_dsl_field(field, supported_langs=supported_langs)
        )

    # date of last index for the purposes of search
    mapping.field("last_indexed_datetime", Date(required=True))
    return mapping


def generate_index_object(index_name: str, config: Config) -> Index:
    index = Index(index_name)
    index.settings(
        number_of_shards=config.index.number_of_shards,
        number_of_replicas=config.index.number_of_replicas,
    )
    mapping = generate_mapping_object(config)
    index.mapping(mapping)
    return index
