import datetime
import functools
import re

from elasticsearch_dsl import Date, Document, Object

from app.config import CONFIG, FieldConfig, FieldType, TaxonomySourceConfig
from app.dsl import generate_dsl_field
from app.taxonomy import get_taxonomy
from app.types import JSONType
from app.utils import constants


def preprocess_field(d: JSONType, input_field: str, split: bool, split_separator: str):
    input_value = d.get(input_field)

    if not input_value:
        return None
    if split:
        input_value = input_value.split(split_separator)

    return input_value


def create_product_from_dict(d: JSONType):
    field: FieldConfig
    inputs = {}
    split_separator = CONFIG.split_separator
    taxonomy_config = CONFIG.taxonomy
    taxonomy_sources_by_name = {
        source.name: source for source in taxonomy_config.sources
    }

    for field in CONFIG.fields:
        input_field = field.get_input_field()

        if field.type == FieldType.text_lang:
            field_input = {}
            for target_key in (
                k for k in d if re.fullmatch(f"{re.escape(input_field)}_\w\w", k)
            ):
                input_value = preprocess_field(
                    d, target_key, split=field.split, split_separator=split_separator
                )
                if input_value is None:
                    continue
                lang = target_key.rsplit("_", maxsplit=1)[-1]
                field_input[lang] = input_value

            if field_input:
                inputs[field.name] = field_input

        elif field.type == FieldType.taxonomy:
            field_input = {}
            input_value = preprocess_field(
                d, input_field, split=field.split, split_separator=split_separator
            )
            if input_value is None:
                continue
            taxonomy_source_config: TaxonomySourceConfig = taxonomy_sources_by_name[
                field.taxonomy_name
            ]
            taxonomy = get_taxonomy(
                taxonomy_source_config.name, taxonomy_source_config.url
            )

            for lang in taxonomy_config.supported_langs:
                for single_tag in input_value:
                    if (
                        value := taxonomy.get_localized_name(single_tag, lang)
                    ) is not None:
                        field_input.setdefault(lang, []).append(value)

            if field_input:
                inputs[field.name] = field_input

        else:
            input_value = preprocess_field(
                d, input_field, split=field.split, split_separator=split_separator
            )
            if input_value is None:
                continue

            inputs[field.name] = input_value

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
