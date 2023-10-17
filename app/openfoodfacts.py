import copy
import re

from app.indexing import BaseDocumentPreprocessor
from app.postprocessing import BaseResultProcessor
from app.taxonomy import get_taxonomy
from app.types import JSONType

COUNTRIES_TAXONOMY_URL = (
    "https://static.openfoodfacts.org/data/taxonomies/countries.full.json"
)


BARCODE_PATH_REGEX = re.compile(r"^(...)(...)(...)(.*)$")


def split_barcode(barcode: str) -> list[str]:
    """Split barcode in the same way as done by Product Opener to generate a
    product image folder.

    :param barcode: The barcode of the product. For the pro platform only,
        it must be prefixed with the org ID using the format
        `{ORG_ID}/{BARCODE}`
    :raises ValueError: raise a ValueError if `barcode` is invalid
    :return: a list containing the splitted barcode
    """
    org_id = None
    if "/" in barcode:
        # For the pro platform, `barcode` is expected to be in the format
        # `{ORG_ID}/{BARCODE}` (ex: `org-lea-nature/3307130803004`)
        org_id, barcode = barcode.split("/", maxsplit=1)

    if not barcode.isdigit():
        raise ValueError(f"unknown barcode format: {barcode}")

    match = BARCODE_PATH_REGEX.fullmatch(barcode)

    splits = [x for x in match.groups() if x] if match else [barcode]

    if org_id is not None:
        # For the pro platform only, images and OCRs belonging to an org
        # are stored in a folder named after the org for all its products, ex:
        # https://images.pro.openfoodfacts.org/images/products/org-lea-nature/330/713/080/3004/1.jpg
        splits.append(org_id)

    return splits


def _generate_file_path(code: str, image_id: str, suffix: str):
    splitted_barcode = split_barcode(code)
    return f"/{'/'.join(splitted_barcode)}/{image_id}{suffix}"


def generate_image_path(code: str, image_id: str) -> str:
    """Generate an image path.

    It's used to generate a unique identifier of an image for a product (and
    to generate an URL to fetch this image from the server).

    :param code: the product barcode
    :param image_id: the image ID (ex: `1`, `ingredients_fr.full`,...)
    :return: the full image path
    """
    return _generate_file_path(code, image_id, ".jpg")


def generate_image_url(code: str, image_id: str) -> str:
    """Generate the image URL for a specific product and image ID.

    :param code: the product barcode
    :param image_id: the image ID (ex: `1`, `ingredients_fr.full`,...)
    :return: the generated image URL
    """
    return "https://images.openfoodfacts.org/images/products" + generate_image_path(
        code, image_id
    )


class DocumentPreprocessor(BaseDocumentPreprocessor):
    def preprocess(self, document: JSONType) -> JSONType | None:
        # no need to have a deep-copy here
        document = copy.copy(document)
        # convert obsolete field into bool
        document["obsolete"] = bool(document.get("obsolete"))
        document["taxonomy_langs"] = self.get_taxonomy_langs(document)
        # Don't keep all nutriment values
        self.select_nutriments(document)
        return document

    def get_taxonomy_langs(self, document: JSONType) -> list[str]:
        # We add `taxonomy_langs` field to index taxonomized fields in
        # the language of the product. To determine the list of
        # `taxonomy_langs`, we check:
        # - `languages_code`
        # - `countries_tags`: we add every official language of the countries
        #   where the product can be found.
        taxonomy_langs = set(document.get("languages_codes", []))
        countries_tags = document.get("countries_tags", [])
        country_taxonomy = get_taxonomy("country", COUNTRIES_TAXONOMY_URL)

        for country_tag in countries_tags:
            # Check that `country_tag` is in taxonomy
            if (country_node := country_taxonomy[country_tag]) is not None:
                # Get all official languages of the country, and add them to
                # `taxonomy_langs`
                if (
                    lang_codes := country_node.properties.get("language_codes", {}).get(
                        "en"
                    )
                ) is not None:
                    taxonomy_langs |= set(
                        lang_code for lang_code in lang_codes.split(",") if lang_code
                    )

        return list(taxonomy_langs)

    def select_nutriments(self, document: JSONType):
        """Only selected interesting nutriments, as there are hundreds of
        possible values and we're limited to 1000 fields (total) by
        Elasticsearch.

        Update `document` in place.
        """
        nutriments = document.get("nutriments", {})

        for key in list(nutriments):
            # Only keep some nutriment values per 100g
            if key not in (
                "energy-kj_100g",
                "energy-kcal_100g",
                "fiber_100g",
                "fat_100g",
                "saturated-fat_100g",
                "carbohydrates_100g",
                "sugars_100g",
                "proteins_100g",
                "salt_100g",
                "sodium_100g",
            ):
                nutriments.pop(key)


class ResultProcessor(BaseResultProcessor):
    def process_after(self, result: JSONType) -> JSONType:
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
            images = product.get("images", {})

            for display_id in display_ids:
                if display_id in images and images[display_id].get("sizes"):
                    rev_id = images[display_id]["rev"]
                    fields[f"image_{image_type}_url"] = generate_image_url(
                        code, f"{display_id}.{rev_id}.400"
                    )
                    fields[f"image_{image_type}_small_url"] = generate_image_url(
                        code, f"{display_id}.{rev_id}.200"
                    )
                    fields[f"image_{image_type}_thumb_url"] = generate_image_url(
                        code, f"{display_id}.{rev_id}.100"
                    )

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
                                        language_code: generate_image_url(
                                            code, f"{image_id}.{rev_id}.400"
                                        )
                                    },
                                    "small": {
                                        language_code: generate_image_url(
                                            code, f"{image_id}.{rev_id}.200"
                                        )
                                    },
                                    "thumb": {
                                        language_code: generate_image_url(
                                            code, f"{image_id}.{rev_id}.100"
                                        )
                                    },
                                },
                            }
                        )

            return fields
