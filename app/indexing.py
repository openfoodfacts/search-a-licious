import abc
import datetime
import re
from typing import Iterable

from elasticsearch_dsl import Index, Mapping, analyzer
from elasticsearch_dsl import field as dsl_field

from app._types import FetcherResult, FetcherStatus, JSONType
from app.config import (
    ANALYZER_LANG_MAPPING,
    Config,
    FieldConfig,
    FieldType,
    IndexConfig,
    TaxonomyConfig,
)
from app.utils import load_class_object_from_string
from app.utils.analyzers import (
    get_autocomplete_analyzer,
    get_taxonomy_indexing_analyzer,
    get_taxonomy_search_analyzer,
    number_of_fields,
)

FIELD_TYPE_TO_DSL_TYPE = {
    FieldType.keyword: dsl_field.Keyword,
    FieldType.date: dsl_field.Date,
    FieldType.half_float: dsl_field.HalfFloat,
    FieldType.scaled_float: dsl_field.ScaledFloat,
    FieldType.float: dsl_field.Float,
    FieldType.double: dsl_field.Double,
    FieldType.integer: dsl_field.Integer,
    FieldType.short: dsl_field.Short,
    FieldType.long: dsl_field.Long,
    FieldType.unsigned_long: dsl_field.Long,
    FieldType.bool: dsl_field.Boolean,
    FieldType.text: dsl_field.Text,
}


def generate_dsl_field(
    field: FieldConfig, supported_langs: Iterable[str]
) -> dsl_field.Field:
    """Generate Elasticsearch DSL field from a FieldConfig.

    This will be used to generate the Elasticsearch mapping.

    This is an important part, because it will define the behavior of each field.

    :param field: the field to use as input
    :param supported_langs: an iterable of languages (2-letter codes),
        used to know which sub-fields to create for `text_lang`
        and `taxonomy` field types
    :return: the elasticsearch_dsl field
    """
    if field.type is FieldType.taxonomy:
        # We will store the taxonomy identifier as keyword
        # And also store it in subfields with query analyzers for each language,
        # that will activate synonyms and specific normalizations
        if field.taxonomy_name is None:
            raise ValueError("Taxonomy field must have a taxonomy_name set in config")
        sub_fields = {
            lang: dsl_field.Text(
                # we almost use keyword analyzer as we really map synonyms to a keyword
                analyzer=get_taxonomy_indexing_analyzer(field.taxonomy_name, lang),
                # but on query we need to fold and match with synonyms
                search_analyzer=get_taxonomy_search_analyzer(
                    field.taxonomy_name, lang, with_synonyms=True
                ),
            )
            for lang in supported_langs
        }
        return dsl_field.Keyword(required=field.required, fields=sub_fields)
    elif field.type is FieldType.text_lang:
        properties = {
            lang: dsl_field.Text(
                analyzer=analyzer(ANALYZER_LANG_MAPPING.get(lang, "standard")),
            )
            for lang in supported_langs
        }
        return dsl_field.Object(dynamic=False, properties=properties)
    elif field.type == FieldType.object:
        return dsl_field.Object(dynamic=True)
    elif field.type == FieldType.disabled:
        return dsl_field.Object(enabled=False)
    else:
        cls_ = FIELD_TYPE_TO_DSL_TYPE.get(field.type)
        if cls_ is None:
            raise ValueError(f"unsupported field type: {field.type}")
        return cls_()


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
    def preprocess(self, document: JSONType) -> FetcherResult:
        """Preprocess the document before data ingestion in Elasticsearch.

        This can be used to make document schema compatible with the project
        schema or to add custom fields.

        :return: a FetcherResult object:

        * the status can be used to pilot wether
          to index or not the document (even delete it)
        * the document is the document transformed document

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
    """Process data for a `text_lang` field type.

    Generates a dict ready to be indexed by Elasticsearch, with a subfield for
    each language.

    :param data: input data, as a dict
    :param input_field: the name of the field to use as input
    :param split: whether to split the input field value, using
        `split_separator` as separator
    :param lang_separator: the separator used to separate the language code
        from the field name
    :param split_separator: the separator used to split the input field value,
        in case of multi-valued input (if `split` is True)
    :param supported_langs: a set of supported languages (2-letter codes), used
        to know which sub-fields to create
    :return: the processed data, as a dict
    """
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
            if key not in supported_langs:
                continue

        field_input[key] = input_value

    return field_input if field_input else None


def process_taxonomy_field(
    data: JSONType,
    field: FieldConfig,
    taxonomy_config: TaxonomyConfig,
    split_separator: str,
) -> JSONType | None:
    """Process data for a `taxonomy` field type.

    There is not much to be done here,
    as the magic of synonyms etc. happens by ES itself,
    thanks to our mapping definition,
    and a bit at query time.

    :param data: input data, as a dict
    :param field: the field config
    :param split_separator: the separator used to split the input field value,
        in case of multi-valued input (if `field.split` is True)
    :return: the processed value
    """
    input_field = field.get_input_field()
    input_value = preprocess_field_value(
        data, input_field, split=field.split, split_separator=split_separator
    )
    return input_value if input_value else None


class DocumentProcessor:
    """`DocumentProcessor` is responsible of converting an item to index
    into a dict that is ready to be indexed by Elasticsearch.
    """

    def __init__(self, config: IndexConfig) -> None:
        self.config = config
        self.supported_langs_set = config.supported_langs_set
        self.preprocessor: BaseDocumentPreprocessor | None

        if config.preprocessor is not None:
            preprocessor_cls = load_class_object_from_string(config.preprocessor)
            self.preprocessor = preprocessor_cls(config)
        else:
            self.preprocessor = None

    def inputs_from_data(self, id_, processed_data: JSONType) -> JSONType:
        """Generate a dict with the data to be indexed in ES"""
        inputs = {
            "last_indexed_datetime": datetime.datetime.utcnow().isoformat(),
            "_id": id_,
        }
        for field in self.config.fields.values():
            input_field = field.get_input_field()

            if field.type == FieldType.text_lang:
                # dispath languages in a sub-dictionary
                field_input = process_text_lang_field(
                    processed_data,
                    input_field=field.get_input_field(),
                    split=field.split,
                    lang_separator=self.config.lang_separator,
                    split_separator=self.config.split_separator,
                    supported_langs=self.supported_langs_set,
                )
            # nothing to do, all the magic of subfield is done thanks to ES
            elif field.type == FieldType.taxonomy:
                field_input = process_taxonomy_field(
                    data=processed_data,
                    field=field,
                    taxonomy_config=self.config.taxonomy,
                    split_separator=self.config.split_separator,
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

    def from_result(self, result: FetcherResult) -> FetcherResult:
        """Generate an item ready to be indexed by elasticsearch-dsl
        from a fetcher result.

        :param result: the input data
        :return: a new result with transformed data, ready to be indexed
          or removed or skipped.

          In case of indexing or removal, the document always contains an `id_` item
        """
        data = result.document
        if data is None:
            # unexpected !
            return FetcherResult(status=FetcherStatus.OTHER, document=None)
        id_field_name = self.config.index.id_field_name

        _id = data.get(id_field_name)
        if _id is None or _id in self.config.document_denylist:
            # We don't process the document if it has no ID or if it's in the
            # denylist
            return FetcherResult(status=FetcherStatus.SKIP, document=None)

        processed_result = (
            self.preprocessor.preprocess(data)
            if (self.preprocessor is not None)
            and (result.status == FetcherStatus.FOUND)
            else result
        )

        if processed_result.status == FetcherStatus.REMOVED:
            return FetcherResult(
                status=FetcherStatus.REMOVED,
                document={"_id": _id},
            )
        elif (
            processed_result.status != FetcherStatus.FOUND
            or processed_result.document is None
        ):
            return processed_result

        processed_data = processed_result.document

        inputs = self.inputs_from_data(_id, processed_data)

        return FetcherResult(status=processed_result.status, document=inputs)


def generate_mapping_object(config: IndexConfig) -> Mapping:
    """ES Mapping for project index, that will contain the data"""
    mapping = Mapping()
    supported_langs = config.supported_langs
    # note: when we reference new analyzers in the mapping as analyzers objects,
    # Elasticsearch DSL will reference them in the analyzer section by itself
    for field in config.fields.values():
        mapping.field(
            field.name,
            generate_dsl_field(field, supported_langs=supported_langs),
        )

    # date of last index for the purposes of search
    # this is a field internal to Search-a-licious and independent of the project
    mapping.field("last_indexed_datetime", dsl_field.Date(required=True))
    return mapping


def generate_index_object(index_name: str, config: IndexConfig) -> Index:
    """Index configuration for project index, that will contain the data"""
    index = Index(index_name)
    settings = {
        "number_of_shards": config.index.number_of_shards,
        "number_of_replicas": config.index.number_of_replicas,
    }
    mapping = generate_mapping_object(config)
    num_fields = number_of_fields(mapping)
    # add 25% margin
    num_fields = int(num_fields * 1.25)
    if num_fields > 1000:
        # default limit is 1000 fields, set a specific one
        settings["index.mapping.total_fields.limit"] = num_fields
    index.settings(**settings)
    index.mapping(mapping)
    return index


def generate_taxonomy_mapping_object(config: IndexConfig) -> Mapping:
    """ES Mapping for indexes containing taxonomies entries"""
    mapping = Mapping()
    supported_langs = config.supported_langs
    mapping.field("id", dsl_field.Keyword(required=True))
    mapping.field("taxonomy_name", dsl_field.Keyword(required=True))
    mapping.field(
        "name",
        dsl_field.Object(
            required=True,
            dynamic=False,
            properties={
                lang: dsl_field.Keyword(required=False) for lang in supported_langs
            },
        ),
    ),
    mapping.field(
        "synonyms",
        dsl_field.Object(
            required=True,
            dynamic=False,
            properties={
                lang: dsl_field.Completion(
                    analyzer=get_autocomplete_analyzer(lang),
                    contexts=[
                        {
                            "name": "taxonomy_name",
                            "path": "taxonomy_name",
                            "type": "category",
                        }
                    ],
                )
                for lang in supported_langs
            },
        ),
    )
    return mapping


def generate_taxonomy_index_object(index_name: str, config: IndexConfig) -> Index:
    """
    Index configuration for indexes containing taxonomies entries
    """
    index = Index(index_name)
    taxonomy_index_config = config.taxonomy.index
    index.settings(
        number_of_shards=taxonomy_index_config.number_of_shards,
        number_of_replicas=taxonomy_index_config.number_of_replicas,
    )
    mapping = generate_taxonomy_mapping_object(config)
    index.mapping(mapping)
    return index
