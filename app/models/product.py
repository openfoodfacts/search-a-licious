import datetime
import re

from elasticsearch_dsl import Date, Document, Double, Keyword, Object, Text

from app.config import CONFIG, FieldConfig, FieldType, TaxonomySourceConfig
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

            for lang in taxonomy_config.export_langs:
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


class Product(Document):
    """
    This was initially created with the scripts/generate_schema.py script. However, note that there have been manual
    adjustments.

    Furthermore, additional fields are added at index time, so below is just a subset of the available fields.
    """

    class Index:
        name = constants.INDEX_ALIAS
        settings = {
            "number_of_shards": 4,
            "index.mapping.nested_fields.limit": 200,
            "index.mapping.total_fields.limit": 20000,
        }

    def fill_internal_fields(self):
        self.meta["id"] = self.code
        self.last_indexed_datetime = datetime.datetime.now()

    def save(self, **kwargs):
        self.fill_internal_fields()
        super().save(**kwargs)

    # date of last index for the purposes of search
    last_indexed_datetime = Date(required=True)

    # barcode of the product (can be EAN-13 or internal codes for some food stores),
    # for products without a barcode, Open Food Facts assigns a number starting with the 200 reserved prefix
    code = Keyword(required=True)
    product_name = Object(dynamic=True)
    generic_name = Object(dynamic=True)
    categories = Object(dynamic=True)
    labels = Object(dynamic=True)
    brands = Text()
    lang = Keyword()
    quantity = Text()
    categories_tags = Keyword(multi=True)
    labels_tags = Keyword(multi=True)
    countries_tags = Keyword(multi=True)
    unique_scans_n = Double()
