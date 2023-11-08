import abc
import datetime
import re
from typing import Iterable

from elasticsearch_dsl import (
    Boolean,
    Date,
    Double,
    Field,
    Float,
    Index,
    Integer,
    Keyword,
    Mapping,
    Object,
    Text,
    analyzer,
    Completion,
)

from app.config import (
    ANALYZER_LANG_MAPPING,
    Config,
    FieldConfig,
    FieldType,
    TaxonomyConfig,
    TaxonomySourceConfig,
)
from app.taxonomy import get_taxonomy
from app._types import JSONType
from app.utils import load_class_object_from_string


def generate_dsl_field(
        field: FieldConfig, supported_langs: Iterable[str], taxonomy_langs: Iterable[str]
) -> Field:
    """Generate Elasticsearch DSL field from a FieldConfig.

    :param field: the field to use as input
    :param supported_langs: an iterable of languages (2-letter codes),
        used to know which sub-fields to create for `text_lang` field types
    :param taxonomy_langs: an iterabl of languages (2-letter codes),
        used to know which sub-fields to create for `taxonomy` field types
    :return: the elasticsearch_dsl field
    """
    if field.type is FieldType.taxonomy:
        # in `other`, we store the text of all languages that don't have a
        # built-in ES analyzer. By using a single field, we don't create as
        # many subfields as there are supported languages
        properties = {"other": Text(analyzer=analyzer("standard"))}
        for lang in taxonomy_langs:
            if lang in ANALYZER_LANG_MAPPING:
                properties[lang] = Text(analyzer=analyzer(ANALYZER_LANG_MAPPING[lang]))
        return Object(required=field.required, dynamic=False, properties=properties)

    elif field.type is FieldType.text_lang:
        properties = {
            # we use `other` field for the same reason as for the `taxonomy`
            # type
            "other": Text(analyzer=analyzer("standard")),
            # Add subfield used to save main language version for `text_lang`
            "main": Text(analyzer=analyzer("standard")),
        }
        for lang in supported_langs:
            if lang in ANALYZER_LANG_MAPPING:
                if field.completion_analyser:
                    properties[lang] = Completion(analyzer=analyzer(ANALYZER_LANG_MAPPING[lang]))
                else:
                    properties[lang] = Text(analyzer=analyzer(ANALYZER_LANG_MAPPING[lang]))
        return Object(required=field.required, dynamic=False, properties=properties)

    elif field.type == FieldType.object:
        return Object(required=field.required, dynamic=True)
    elif field.type == FieldType.keyword:
        return Keyword(required=field.required)
    elif field.type == FieldType.text:
        return Text(required=field.required)
    elif field.type == FieldType.float:
        return Float(required=field.required)
    elif field.type == FieldType.double:
        return Double(required=field.required)
    elif field.type == FieldType.integer:
        return Integer(required=field.required)
    elif field.type == FieldType.bool:
        return Boolean(required=field.required)
    elif field.type == FieldType.date:
        return Date(required=field.required)
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
        supported_langs: set[str],
) -> JSONType | None:
    field_input: JSONType = {}
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
            # here key is the lang 2-letters code
            key = target_field.rsplit(lang_separator, maxsplit=1)[-1]
            # Here we check whether the language is supported, otherwise
            # we use the default "other" field, that aggregates texts
            # from all unsupported languages
            # it's the only subfield that is a list instead of a string
            if key not in supported_langs:
                field_input.setdefault("other", []).append(input_value)
                continue

        field_input[key] = input_value

    return field_input if field_input else None


def process_text_nested_lang_field(
        data: JSONType,
        input_field: str,
        supported_langs: set[str],
) -> JSONType | None:
    field_input: JSONType = {}
    input_value = data.get(input_field)
    for lang, items in input_value.items():
        if lang in supported_langs:
            field_input[lang] = items
        else:
            field_input.setdefault("other", []).extend(items)
    return field_input if field_input else None


def process_taxonomy_field(
        data: JSONType,
        field: FieldConfig,
        taxonomy_config: TaxonomyConfig,
        split_separator: str,
        taxonomy_langs: set[str],
) -> JSONType | None:
    field_input: JSONType = {}
    input_field = field.get_input_field()
    input_value = preprocess_field_value(
        data, input_field, split=field.split, split_separator=split_separator
    )
    if input_value is None:
        return None

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
    # - a custom list of supported languages for the item (`taxonomy_langs`
    # field), this is used to allow indexing tags for an item that is available
    # in specific countries
    langs = taxonomy_langs | set(data.get("taxonomy_langs", []))
    for lang in langs:
        for single_tag in input_value:
            if (value := taxonomy.get_localized_name(single_tag, lang)) is not None:
                # If language is not supported (=no elasticsearch specific
                # analyzers), we store the data in a "other" field
                key = lang if lang in ANALYZER_LANG_MAPPING else "other"
                field_input.setdefault(key, []).append(value)

    if field.name in data:
        field_input["original"] = data[field.name]

    return field_input if field_input else None


class DocumentProcessor:
    """`DocumentProcessor`s are responsible of converting an item to index
    into a dict that is ready to be indexed by Elasticsearch.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.supported_langs = config.get_supported_langs()
        self.taxonomy_langs = config.get_taxonomy_langs()
        self.preprocessor: BaseDocumentPreprocessor | None

        if config.preprocessor is not None:
            preprocessor_cls = load_class_object_from_string(config.preprocessor)
            self.preprocessor = preprocessor_cls(config)
        else:
            self.preprocessor = None

    def from_dict(self, data: JSONType) -> JSONType | None:
        """Generate an item ready to be indexed by elasticsearch-dsl
        from an item dict.

        :param data: the input data
        :return: a dict ready to be indexed
        """
        id_field_name = self.config.index.id_field_name

        _id = data.get(id_field_name)
        if _id is None or _id in self.config.document_denylist:
            # We don't process the document if it has no ID or if it's in the
            # denylist
            return None

        inputs = {
            "last_indexed_datetime": datetime.datetime.utcnow().isoformat(),
            "_id": _id,
        }
        processed_data = (
            self.preprocessor.preprocess(data)
            if self.preprocessor is not None
            else data
        )

        if processed_data is None:
            return None

        for field in self.config.fields.values():
            input_field = field.get_input_field()

            if field.type == FieldType.text_lang:
                if field.nested_lang_source:
                    field_input = process_text_nested_lang_field(
                        processed_data,
                        input_field=field.get_input_field(),
                        supported_langs=self.supported_langs,
                    )
                else:
                    field_input = process_text_lang_field(
                        processed_data,
                        input_field=field.get_input_field(),
                        split=field.split,
                        lang_separator=self.config.lang_separator,
                        split_separator=self.config.split_separator,
                        supported_langs=self.supported_langs,
                    )

            elif field.type == FieldType.taxonomy:
                field_input = process_taxonomy_field(
                    data=processed_data,
                    field=field,
                    taxonomy_config=self.config.taxonomy,
                    split_separator=self.config.split_separator,
                    taxonomy_langs=self.taxonomy_langs,
                )

            else:
                field_input = preprocess_field_value(
                    processed_data,
                    input_field,
                    split=field.split,
                    split_separator=self.config.split_separator,
                )

            if field_input:
                inputs[field.name] = field_input

        return inputs


def generate_mapping_object(config: Config) -> Mapping:
    mapping = Mapping()
    supported_langs = config.supported_langs
    taxonomy_langs = config.taxonomy.exported_langs
    for field in config.fields.values():
        mapping.field(
            field.name,
            generate_dsl_field(
                field, supported_langs=supported_langs, taxonomy_langs=taxonomy_langs
            ),
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
