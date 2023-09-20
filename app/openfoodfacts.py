import copy

from app.indexing import DocumentPreprocessor
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
        supported_langs = set(document.get("languages_codes", []))
        countries_tags = document.get("countries_tags", [])
        country_taxonomy = get_taxonomy("country", COUNTRIES_TAXONOMY_URL)

        for country_tag in countries_tags:
            # Check that `country_tag` is in taxonomy
            if (country_node := country_taxonomy[country_tag]) is not None:
                # Get all official languages of the country, and add them to `supported_langs`
                if (
                    lang_codes := country_node.properties.get("language_codes", {}).get(
                        "en"
                    )
                ) is not None:
                    supported_langs |= set(
                        lang_code for lang_code in lang_codes.split(",") if lang_code
                    )

        document["supported_langs"] = list(supported_langs)
        return document
