from enum import StrEnum, auto

from pydantic import BaseModel, HttpUrl, model_validator


class TaxonomySourceConfig(BaseModel):
    name: str
    url: HttpUrl


class TaxonomyConfig(BaseModel):
    sources: list[TaxonomySourceConfig]
    supported_langs: list[str]


class FieldType(StrEnum):
    keyword = auto()
    date = auto()
    double = auto()
    text = auto()
    text_lang = auto()
    taxonomy = auto()


class FieldConfig(BaseModel):
    # name of the field, must be unique across the config
    name: str
    # type of the field, see `FieldType` for possible values
    type: FieldType
    # if required=True, the field is required in the input data
    required: bool = False
    # name of the input field to use when importing data
    input_field: str | None = None
    # do we split the input field with `split_separator`
    split: bool = False
    # do we include the field in the multi-match query used as baseline results
    include_multi_match: bool = False
    # only for taxonomy field type
    taxonomy_name: str | None = None
    # can the keyword field contain multiple value (keyword type only)
    multi: bool = False
    # is the last_modified field, it's used to perform incremental update using Redis queues
    is_last_modified_field: bool = False

    @model_validator(mode="after")
    def multi_should_be_used_for_keyword_type_only(self):
        """Validator that checks that `multi` flag is only True for fields
        with type `keyword`."""
        if self.type not in (FieldType.keyword, FieldType.text) and self.multi:
            raise ValueError("multi=True should only be used with keyword type")
        return self

    @model_validator(mode="after")
    def taxonomy_name_should_be_used_for_taxonomy_type_only(self):
        """Validator that checks that `taxonomy_name` is only provided for fields
        with type `taxonomy`."""
        if self.type is not FieldType.taxonomy and self.taxonomy_name is not None:
            raise ValueError("taxonomy_name should be provided for taxonomy type only")
        return self

    def get_input_field(self):
        """Return the name of the field to use in input data."""
        return self.input_field or self.name

    def has_lang_subfield(self) -> bool:
        return self.type in (FieldType.taxonomy, FieldType.text_lang)


class Config(BaseModel):
    fields: list[FieldConfig]
    split_separator: str = ","
    # for `text_lang` FieldType, the separator between the name of the field
    # and the language code, ex: product_name_it if lang_separator="_"
    lang_separator: str = "_"
    taxonomy: TaxonomyConfig
    # The full qualified reference to the preprocessor to use before data import
    # This is used to adapt the data schema or to add search-a-licious specific fields
    # for example.
    preprocessor: str | None = None
    # A list of supported languages, it is used to build index mapping
    supported_langs: list[str] | None = None
    # How much we boost exact matches on individual fields
    match_phrase_boost: float = 2.0

    @model_validator(mode="after")
    def taxonomy_name_should_be_defined(self):
        """Validator that checks that for if `taxonomy_type` is defined for a field,
        it refers to a taxonomy defined in `taxonomy.sources`."""
        defined_taxonomies = [source.name for source in self.taxonomy.sources]
        for field in self.fields:
            if (
                field.taxonomy_name is not None
                and field.taxonomy_name not in defined_taxonomies
            ):
                raise ValueError(
                    f"'{field.taxonomy_name}' should be defined in `taxonomy.sources`"
                )
        return self

    @model_validator(mode="after")
    def field_name_should_be_unique(self):
        """Validator that checks that all fields have unique names."""
        seen: set[str] = set()
        for field in self.fields:
            if field.name in seen:
                raise ValueError(
                    f"each field name should be unique, duplicate found: '{field.name}'"
                )
            seen.add(field.name)
        return self

    @model_validator(mode="after")
    def only_one_field_should_be_is_last_modified_field(self):
        """Validator that checks that there is a single field with `is_last_modified_field=True`."""
        if sum(1 for field in self.fields if field.is_last_modified_field) > 1:
            raise ValueError(
                f"only one field should have `is_last_modified_field=True`"
            )
        return self

    @model_validator(mode="after")
    def if_split_should_be_multi(self):
        """Validator that checks that multi=True if split=True.."""
        for field in self.fields:
            if field.split and not field.multi:
                raise ValueError(f"multi should be True if split=True")
        return self

    def get_input_fields(self) -> set[str]:
        return {field.name for field in self.fields} | {
            field.input_field for field in self.fields if field.input_field is not None
        }

    def get_supported_langs(self) -> set[str]:
        return set(self.supported_langs or []) | set(self.taxonomy.supported_langs)

    def get_last_modified_field(self) -> FieldConfig:
        for field in self.fields:
            if field.is_last_modified_field:
                return field
        return None


CONFIG = Config(
    fields=[
        FieldConfig(name="code", type=FieldType.keyword, required=True),
        FieldConfig(
            name="product_name", type=FieldType.text_lang, include_multi_match=True
        ),
        FieldConfig(
            name="generic_name", type=FieldType.text_lang, include_multi_match=True
        ),
        FieldConfig(
            name="categories",
            type=FieldType.taxonomy,
            input_field="categories_tags",
            taxonomy_name="category",
            include_multi_match=True,
        ),
        FieldConfig(
            name="labels",
            type=FieldType.taxonomy,
            input_field="labels_tags",
            taxonomy_name="label",
            include_multi_match=True,
        ),
        FieldConfig(
            name="brands",
            type=FieldType.text,
            split=True,
            multi=True,
            include_multi_match=True,
        ),
        FieldConfig(name="stores", type=FieldType.text, split=True, multi=True),
        FieldConfig(name="emb_codes", type=FieldType.text, split=True, multi=True),
        FieldConfig(name="lang", type=FieldType.keyword),
        FieldConfig(name="quantity", type=FieldType.text),
        FieldConfig(name="categories_tags", type=FieldType.keyword, multi=True),
        FieldConfig(name="labels_tags", type=FieldType.keyword, multi=True),
        FieldConfig(name="countries_tags", type=FieldType.keyword, multi=True),
        FieldConfig(name="states_tags", type=FieldType.keyword, multi=True),
        FieldConfig(name="origins_tags", type=FieldType.keyword, multi=True),
        FieldConfig(name="unique_scans_n", type=FieldType.double),
        FieldConfig(name="nutrition_grades", type=FieldType.keyword),
        FieldConfig(name="ecoscore_grade", type=FieldType.keyword),
        FieldConfig(name="nova_groups", type=FieldType.keyword),
        FieldConfig(
            name="last_modified_t", type=FieldType.date, is_last_modified_field=True
        ),
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
        supported_langs=["en", "fr", "es", "de", "it", "nl"],
    ),
    preprocessor="app.openfoodfacts.OpenFoodFactsPreprocessor",
    supported_langs=[
        "aa",
        "ab",
        "ae",
        "af",
        "ak",
        "am",
        "ar",
        "as",
        "at",
        "au",
        "ay",
        "az",
        "be",
        "bg",
        "bi",
        "bn",
        "br",
        "bs",
        "ca",
        "ch",
        "co",
        "cs",
        "cu",
        "cy",
        "da",
        "de",
        "dv",
        "dz",
        "el",
        "en",
        "eo",
        "es",
        "et",
        "eu",
        "fa",
        "fi",
        "fj",
        "fo",
        "fr",
        "fy",
        "ga",
        "gb",
        "gd",
        "gl",
        "gn",
        "gp",
        "gu",
        "gv",
        "ha",
        "he",
        "hi",
        "hk",
        "ho",
        "hr",
        "ht",
        "hu",
        "hy",
        "hz",
        "id",
        "in",
        "io",
        "is",
        "it",
        "iw",
        "ja",
        "jp",
        "jv",
        "ka",
        "kk",
        "kl",
        "km",
        "kn",
        "ko",
        "ku",
        "ky",
        "la",
        "lb",
        "lc",
        "ln",
        "lo",
        "lt",
        "lu",
        "lv",
        "mg",
        "mh",
        "mi",
        "mk",
        "ml",
        "mn",
        "mo",
        "mr",
        "ms",
        "mt",
        "my",
        "na",
        "nb",
        "nd",
        "ne",
        "nl",
        "nn",
        "no",
        "nr",
        "ny",
        "oc",
        "om",
        "pa",
        "pl",
        "ps",
        "pt",
        "qq",
        "qu",
        "re",
        "rm",
        "rn",
        "ro",
        "rs",
        "ru",
        "rw",
        "sd",
        "se",
        "sg",
        "sh",
        "si",
        "sk",
        "sl",
        "sm",
        "sn",
        "so",
        "sq",
        "sr",
        "ss",
        "st",
        "sv",
        "sw",
        "ta",
        "te",
        "tg",
        "th",
        "ti",
        "tk",
        "tl",
        "tn",
        "to",
        "tr",
        "ts",
        "ug",
        "uk",
        "ur",
        "us",
        "uz",
        "ve",
        "vi",
        "wa",
        "wo",
        "xh",
        "xx",
        "yi",
        "yo",
        "zh",
        "zu",
    ],
    match_phrase_boost=2.0,
)
