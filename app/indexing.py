import abc
import datetime
import re
from typing import Iterable

from elasticsearch_dsl import (
    Boolean,
    Date,
    Double,
    Float,
    Index,
    Integer,
    Keyword,
    Mapping,
    Object,
    Text,
    analyzer,
)

from app.config import Config, FieldConfig, FieldType, TaxonomySourceConfig
from app.taxonomy import get_taxonomy
from app.types import JSONType
from app.utils import load_class_object_from_string
from app.utils.analyzers import ANALYZER_LANG_MAPPING


def generate_dsl_field(field: FieldConfig, supported_langs: Iterable[str]):
    """Generate Elasticsearch DSL field from a FieldConfig.

    :param field: the field to use as input
    :param supported_langs: a list of supported languages (2-letter codes).
        This is used for to know which sub-fields to create for `text_lang`
        and `taxonomy` field types
    :return: the elasticsearch_dsl field
    """
    if field.type in (FieldType.text_lang, FieldType.taxonomy):
        properties = {
            lang: Text(analyzer=analyzer(ANALYZER_LANG_MAPPING.get(lang, "standard")))
            for lang in supported_langs
        }
        if field.type is FieldType.text_lang:
            # Add subfield used to save main language version for `text_lang`
            properties["main"] = Text(analyzer=analyzer("standard"))
        return Object(required=field.required, dynamic=False, properties=properties)
    elif field.type == FieldType.object:
        return Object(required=field.required, dynamic=True)
    elif field.type == FieldType.keyword:
        return Keyword(required=field.required, multi=field.multi)
    elif field.type == FieldType.text:
        return Text(required=field.required, multi=field.multi)
    elif field.type == FieldType.float:
        return Float(required=field.required, multi=field.multi)
    elif field.type == FieldType.double:
        return Double(required=field.required, multi=field.multi)
    elif field.type == FieldType.integer:
        return Integer(required=field.required, multi=field.multi)
    elif field.type == FieldType.bool:
        return Boolean(required=field.required, multi=field.multi)
    elif field.type == FieldType.date:
        return Date(required=field.required, multi=field.multi)
    elif field.type == FieldType.disabled:
        return Object(required=field.required, enabled=False)
    else:
        raise ValueError(f"unsupported field type: {field.type}")


def preprocess_field_value(
    d: JSONType, input_field: str, split: bool, split_separator: str
):
    input_value = d.get(input_field)

    if not input_value:
        return None
    if split:
        input_value = input_value.split(split_separator)

    return input_value


class BaseDocumentPreprocessor(abc.ABC):
    def __init__(self, config: Config) -> None:
        self.config = config

    @abc.abstractmethod
    def preprocess(self, document: JSONType) -> JSONType | None:
        """Preprocess the document before data ingestion in Elasticsearch.

        This can be used to make document schema compatible with the project
        schema or to add custom fields.

        Is None is returned, the document is not indexed.
        """
        pass


def process_text_lang_field(
    data: JSONType,
    input_field: str,
    split: bool,
    lang_separator: str,
    split_separator: str,
) -> JSONType | None:
    field_input = {}
    target_fields = [
        k
        for k in data
        if re.fullmatch(rf"{re.escape(input_field)}{lang_separator}\w\w([-_]\w\w)?", k)
    ]
    for target_field in (input_field, *target_fields):
        input_value = preprocess_field_value(
            data,
            target_field,
            split=split,
            split_separator=split_separator,
        )
        if input_value is None:
            continue

        if target_field == input_field:
            # we store the "main language" version of the field in main
            # subfield
            key = "main"
        else:
            key = target_field.rsplit(lang_separator, maxsplit=1)[-1]
        field_input[key] = input_value

    return field_input if field_input else None


def process_taxonomy_field(
    data: JSONType, field: FieldConfig, config: Config
) -> JSONType | None:
    field_input = {}
    input_field = field.get_input_field()
    input_value = preprocess_field_value(
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
    taxonomy = get_taxonomy(
        taxonomy_source_config.name, str(taxonomy_source_config.url)
    )

    # to know in which language we should translate the tags using the
    # taxonomy, we use:
    # - the language list defined in the taxonomy config: for every item, we
    #   translate the tags for this list of languages
    # - a custom list of supported languages for the item, this is used to
    #   allow indexing tags for an item that is available in specific countries
    supported_langs = set(taxonomy_config.supported_langs) | set(
        data.get("supported_langs", [])
    )
    for lang in supported_langs:
        for single_tag in input_value:
            if (value := taxonomy.get_localized_name(single_tag, lang)) is not None:
                field_input.setdefault(lang, []).append(value)

    if field.name in data:
        field_input["original"] = data[field.name]

    return field_input if field_input else None


class DocumentProcessor:
    """`DocumentProcessor`s are responsible of converting an item to index
    into a dict that is ready to be indexed by Elasticsearch.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.preprocessor: BaseDocumentPreprocessor | None

        if config.preprocessor is not None:
            preprocessor_cls = load_class_object_from_string(config.preprocessor)
            self.preprocessor = preprocessor_cls(config)
        else:
            self.preprocessor = None

    def from_dict(self, d: JSONType) -> JSONType | None:
        id_field_name = self.config.index.id_field_name

        _id = d.get(id_field_name)
        if _id is None or _id in self.config.document_denylist:
            # We don't process the document if it has no ID or if it's in the
            # denylist
            return None

        inputs = {
            "last_indexed_datetime": datetime.datetime.utcnow(),
            "_id": _id,
        }
        d = self.preprocessor.preprocess(d) if self.preprocessor is not None else d

        if d is None:
            return None

        for field in self.config.fields.values():
            input_field = field.get_input_field()

            if field.type == FieldType.text_lang:
                field_input = process_text_lang_field(
                    d,
                    input_field=field.get_input_field(),
                    split=field.split,
                    lang_separator=self.config.lang_separator,
                    split_separator=self.config.split_separator,
                )

            elif field.type == FieldType.taxonomy:
                field_input = process_taxonomy_field(d, field, self.config)

            else:
                field_input = preprocess_field_value(
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
    supported_langs = config.get_supported_langs()
    for field in config.fields.values():
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
