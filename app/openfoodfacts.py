import copy

from app.indexing import BaseDocumentPreprocessor
from app.postprocessing import BaseResultProcessor
from app.taxonomy import get_taxonomy
from app.types import JSONType

COUNTRIES_TAXONOMY_URL = (
    "https://static.openfoodfacts.org/data/taxonomies/countries.full.json"
)


class DocumentPreprocessor(BaseDocumentPreprocessor):
    def preprocess(self, document: JSONType) -> JSONType:
        # no need to have a deep-copy here
        document = copy.copy(document)
        # We add `supported_langs` field to index taxonomized fields in
        # the language of the product. To determine the list of
        # `supported_langs`, we check:
        # - `languages_code`
        # - `countries_tags`: we add every official language of the countries
        #   where the product can be found.
        supported_langs = set(document.get("languages_codes", []))
        countries_tags = document.get("countries_tags", [])
        country_taxonomy = get_taxonomy("country", COUNTRIES_TAXONOMY_URL)

        for country_tag in countries_tags:
            # Check that `country_tag` is in taxonomy
            if (country_node := country_taxonomy[country_tag]) is not None:
                # Get all official languages of the country, and add them to
                # `supported_langs`
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


class ResultProcessor(BaseResultProcessor):
    def process_result(self, result: JSONType) -> JSONType:
        result |= ResultProcessor.build_image_fields(result)
        return result

    @staticmethod
    def build_image_fields(product: JSONType):
        # Python copy of the code from
        # https://github.com/openfoodfacts/openfoodfacts-server/blob/b297ed858d526332649562cdec5f1d36be184984/lib/ProductOpener/Display.pm#L10128
        code = product["code"]
        fields = {}

        for image_type in ["front", "ingredients", "nutrition", "packaging"]:
            display_ids = []
            lang = product.get("lang")
            if lang:
                display_ids.append(f"{image_type}_{lang}")

            display_ids.append(image_type)
            base_url = "https://images.openfoodfacts.org/images/products/"
            images = product.get("images", {})

            for display_id in display_ids:
                if display_id in images and images[display_id].get("sizes"):
                    rev_id = images[display_id]["rev"]
                    fields[
                        f"image_{image_type}_url"
                    ] = f"{base_url}{code}/{display_id}.{rev_id}.400.jpg"
                    fields[
                        f"image_{image_type}_small_url"
                    ] = f"{base_url}{code}/{display_id}.{rev_id}.200.jpg"
                    fields[
                        f"image_{image_type}_thumb_url"
                    ] = f"{base_url}{code}/{display_id}.{rev_id}.100.jpg"

                    if image_type == "front":
                        fields["image_url"] = fields[f"image_{image_type}_url"]
                        fields["image_small_url"] = fields[
                            f"image_{image_type}_small_url"
                        ]
                        fields["image_thumb_url"] = fields[
                            f"image_{image_type}_thumb_url"
                        ]

            if product.get("languages_codes"):
                for language_code in product["languages_codes"]:
                    image_id = f"{image_type}_{language_code}"
                    if images and images.get(image_id) and images[image_id]["sizes"]:
                        fields.setdefault("selected_images", {}).update(
                            {
                                image_type: {
                                    "display": {
                                        language_code: f"{base_url}{code}/{image_id}.{rev_id}.400.jpg"
                                    },
                                    "small": {
                                        language_code: f"{base_url}{code}/{image_id}.{rev_id}.200.jpg"
                                    },
                                    "thumb": {
                                        language_code: f"{base_url}{code}/{image_id}.{rev_id}.100.jpg"
                                    },
                                },
                            }
                        )

            return fields
