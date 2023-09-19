import abc
import datetime
import functools
import re

from elasticsearch_dsl import Date, Document

from app.config import CONFIG, Config, FieldConfig, FieldType, TaxonomySourceConfig
from app.dsl import generate_dsl_field
from app.taxonomy import get_taxonomy
from app.types import JSONType
from app.utils import constants, load_class_object_from_string


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
        pass


def process_text_lang_field(
    data: JSONType, field: FieldConfig, config: Config
) -> JSONType | None:
    field_input = {}
    input_field = field.get_input_field()
    for target_key in (
        k
        for k in data
        if re.fullmatch(f"{re.escape(input_field)}{config.lang_separator}\w\w([-_]\w\w)?", k)
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


class ProductProcessor:
    def __init__(self, config: Config) -> None:
        self.config = config

        if config.preprocessor is not None:
            preprocessor_cls = load_class_object_from_string(config.preprocessor)
            self.preprocessor = preprocessor_cls(config)
        else:
            self.preprocessor = None

    def from_dict(self, d: JSONType):
        inputs = {}
        d = self.preprocessor(d) if self.preprocessor is not None else d

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

        product = Product(**inputs)
        product.fill_internal_fields()
        return product


FIELD_BY_NAME = {field.name: field for field in CONFIG.fields}
_generate_dsl_field = functools.partial(
    generate_dsl_field, supported_lang=CONFIG.taxonomy.supported_langs
)


class Product(Document):
    """Additional fields are added at index time, so below is just a subset of the available fields."""

    class Index:
        name = constants.INDEX_ALIAS
        settings = {"number_of_shards": 4}

    def fill_internal_fields(self):
        self.meta["id"] = self.code
        self.last_indexed_datetime = datetime.datetime.now()

    def save(self, **kwargs):
        self.fill_internal_fields()
        super().save(**kwargs)

    # date of last index for the purposes of search
    last_indexed_datetime = Date(required=True)

    # we generate DSL fields manually for now, we will use a smarter approach later
    code = _generate_dsl_field(FIELD_BY_NAME["code"])
    product_name = _generate_dsl_field(FIELD_BY_NAME["product_name"])
    generic_name = _generate_dsl_field(FIELD_BY_NAME["generic_name"])
    categories = _generate_dsl_field(FIELD_BY_NAME["categories"])
    labels = _generate_dsl_field(FIELD_BY_NAME["labels"])
    brands = _generate_dsl_field(FIELD_BY_NAME["brands"])
    stores = _generate_dsl_field(FIELD_BY_NAME["stores"])
    emb_codes = _generate_dsl_field(FIELD_BY_NAME["emb_codes"])
    lang = _generate_dsl_field(FIELD_BY_NAME["lang"])
    quantity = _generate_dsl_field(FIELD_BY_NAME["quantity"])
    categories_tags = _generate_dsl_field(FIELD_BY_NAME["categories_tags"])
    labels_tags = _generate_dsl_field(FIELD_BY_NAME["labels_tags"])
    countries_tags = _generate_dsl_field(FIELD_BY_NAME["countries_tags"])
    states_tags = _generate_dsl_field(FIELD_BY_NAME["states_tags"])
    origins_tags = _generate_dsl_field(FIELD_BY_NAME["origins_tags"])
    unique_scans_n = _generate_dsl_field(FIELD_BY_NAME["unique_scans_n"])
    nutrition_grades = _generate_dsl_field(FIELD_BY_NAME["nutrition_grades"])
    ecoscore_grade = _generate_dsl_field(FIELD_BY_NAME["ecoscore_grade"])
    nova_groups = _generate_dsl_field(FIELD_BY_NAME["nova_groups"])
