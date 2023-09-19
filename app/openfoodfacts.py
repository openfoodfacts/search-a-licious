import copy

from app.models.product import DocumentPreprocessor
from app.taxonomy import get_taxonomy
from app.types import JSONType

COUNTRIES_TAXONOMY_URL = (
    "https://static.openfoodfacts.org/data/taxonomies/countries.full.json"
)


class OpenFoodFactsPreprocessor(DocumentPreprocessor):
    def preprocess(self, document: JSONType) -> JSONType:
        # no need to have a deep-copy here
        document = copy.copy(document)
        # We add `supported_langs` field to index taxonomized fields in
        # the language of the product. To determine the list of `supported_langs`, we check:
        # - `languages_code`
        # - `countries_tags`: we add every official language of the countries where the product
        # can be found.
        supported_langs = set(document["languages_codes"])
        countries_tags = document["countries_tags"]
        country_taxonomy = get_taxonomy("country", COUNTRIES_TAXONOMY_URL)

        for country_tag in countries_tags:
            supported_langs |= set(
                country_taxonomy[country_tag]
                .properties["language_codes"]["en"]
                .split(",")
            )

        document["supported_langs"] = list(supported_langs)
        return document
