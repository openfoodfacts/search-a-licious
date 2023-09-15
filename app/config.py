from enum import StrEnum, auto

from pydantic import BaseModel


class TaxonomySourceConfig(BaseModel):
    name: str
    url: str


class TaxonomyConfig(BaseModel):
    sources: list[TaxonomySourceConfig]
    export_langs: list[str]


class FieldType(StrEnum):
    keyword = auto()
    date = auto()
    double = auto()
    text = auto()
    text_lang = auto()
    taxonomy = auto()


class FieldConfig(BaseModel):
    name: str
    type: FieldType
    required: bool = False
    input_field: str | None = None
    split: bool = False
    # only for taxonomy field type
    taxonomy_name: str | None = None

    def get_input_field(self):
        return self.input_field or self.name


class Config(BaseModel):
    fields: list[FieldConfig]
    split_separator: str = ","
    taxonomy: TaxonomyConfig

    def get_input_fields(self) -> set[str]:
        return {field.name for field in self.fields} | {
            field.input_field for field in self.fields if field.input_field is not None
        }


CONFIG = Config(
    fields=[
        FieldConfig(name="code", type=FieldType.keyword, required=True),
        FieldConfig(name="product_name", type=FieldType.text_lang),
        FieldConfig(name="generic_name", type=FieldType.text_lang),
        FieldConfig(
            name="categories",
            type=FieldType.taxonomy,
            input_field="categories_tags",
            taxonomy_name="category",
        ),
        FieldConfig(
            name="labels",
            type=FieldType.taxonomy,
            input_field="labels_tags",
            taxonomy_name="label",
        ),
        FieldConfig(name="brands", type=FieldType.text, split=True),
        FieldConfig(name="lang", type=FieldType.keyword),
        FieldConfig(name="quantity", type=FieldType.text),
        FieldConfig(name="categories_tags", type=FieldType.keyword),
        FieldConfig(name="labels_tags", type=FieldType.keyword),
        FieldConfig(name="countries_tags", type=FieldType.keyword),
        FieldConfig(name="unique_scans_n", type=FieldType.double),
    ],
    taxonomy=TaxonomyConfig(
        sources=[
            TaxonomySourceConfig(
                name="category",
                url="https://static.openfoodfacts.org/data/taxonomies/categories.full.json",
            ),
            TaxonomySourceConfig(
                name="label",
                url="https://static.openfoodfacts.org/data/taxonomies/labels.full.json",
            ),
        ],
        export_langs=["en", "fr", "es", "de", "it", "nl"],
    ),
)
