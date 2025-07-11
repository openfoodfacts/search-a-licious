import copy
import os
import re

import requests

from app._import import BaseDocumentFetcher
from app._types import FetcherResult, FetcherStatus, JSONType
from app.indexing import BaseDocumentPreprocessor, BaseTaxonomyPreprocessor
from app.postprocessing import BaseResultProcessor
from app.taxonomy import Taxonomy, TaxonomyNode, TaxonomyNodeResult
from app.utils.dict_utils import deep_get
from app.utils.download import http_session
from app.utils.log import get_logger

logger = get_logger(__name__)

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


# The two following functions are copied from openfoodfacts-python
# SDK. We don't use the SDK directly as we don't want to add it as a
# dependency.


def convert_to_legacy_schema(images: JSONType) -> JSONType:
    """Convert the images dictionary to the legacy schema.

    We've improved the schema of the `images` field, but the new
    schema is not compatible with the legacy schema. This function
    converts the new schema to the legacy schema.

    It can be used while migrating the existing Python codebase to the
    new schema.

    The new `images` schema is the following:

    - the `images` field contains the uploaded images under the `uploaded`
        key and the selected images under the `selected` key
    - `uploaded` contains the images that are uploaded, and maps the
        image ID to the detail about the image:
        - `uploaded_t`: the upload timestamp
        - `uploader`: the username of the uploader
        - `sizes`: dictionary mapping image size (`100`, `200`, `400`, `full`)
            to the information about each resized image:
            - `h`: the height of the image
            - `w`: the width of the image
            - `url`: the URL of the image
    - `selected` contains the images that are selected, and maps the
        image key (`nutrition`, `ingredients`, `packaging`, or `front`) to
        a dictionary mapping the language to the selected image details.
        The selected image details are the following fields:
        - `imgid`: the image ID
        - `rev`: the revision ID
        - `sizes`: dictionary mapping image size (`100`, `200`, `400`, `full`)
            to the information about each resized image:
            - `h`: the height of the image
            - `w`: the width of the image
            - `url`: the URL of the image
        - `generation`: information about how to generate the selected image
            from the uploaded image:
            - `geometry`
            - `x1`, `y1`, `x2`, `y2`: the coordinates of the crop
            - `angle`: the rotation angle of the selected image
            - `coordinates_image_size`: 400 or "full", indicates if the
                geometry coordinates are relative to the full image, or to a
                resized version (max width and max height=400)
            - `normalize`: indicates if colors should be normalized
            - `white_magic`: indicates if the background is white and should
                be removed (e.g. photo on a white sheet of paper)

    See https://github.com/openfoodfacts/openfoodfacts-server/pull/11818
    for more details.
    """

    if not is_new_image_schema(images):
        return images

    images_with_legacy_schema = {}

    for image_id, image_data in images.get("uploaded", {}).items():
        images_with_legacy_schema[image_id] = {
            "sizes": {
                # remove URL field
                size: {k: v for k, v in image_size_data.items() if k != "url"}
                for size, image_size_data in image_data["sizes"].items()
            },
            "uploaded_t": image_data["uploaded_t"],
            "uploader": image_data["uploader"],
        }

    for selected_key, image_by_lang in images.get("selected", {}).items():
        for lang, image_data in image_by_lang.items():
            new_image_data = {
                "imgid": image_data["imgid"],
                "rev": image_data["rev"],
                "sizes": {
                    # remove URL field
                    size: {k: v for k, v in image_size_data.items() if k != "url"}
                    for size, image_size_data in image_data["sizes"].items()
                },
                **(image_data.get("generation", {})),
            }
            images_with_legacy_schema[f"{selected_key}_{lang}"] = new_image_data

    return images_with_legacy_schema


def is_new_image_schema(images_data: JSONType) -> bool:
    """Return True if the `images` dictionary follows the new Product Opener
    images schema.

    See https://github.com/openfoodfacts/openfoodfacts-server/pull/11818 for
    more information about this new schema.
    """
    if not images_data:
        return False

    return "selected" in images_data or "uploaded" in images_data


# This is not part of search-a-licious, so we don't use the settings object
OFF_API_URL = os.environ.get("OFF_API_URL", "https://world.openfoodfacts.org")


class TaxonomyPreprocessor(BaseTaxonomyPreprocessor):
    """Preprocessor for Open Food Facts taxonomies."""

    def preprocess(self, taxonomy: Taxonomy, node: TaxonomyNode) -> TaxonomyNodeResult:
        """Preprocess a taxonomy node.

        We add the main language, and we also have specificities for some
        taxonomies.
        """
        if taxonomy.name == "brands":
            # brands are english only, put them in "main lang"
            node.names.update(main=node.names["en"])
            if node.synonyms and (synonyms_en := list(node.synonyms.get("en", []))):
                node.synonyms.update(main=synonyms_en)
        else:
            # main language is entry id prefix + eventual xx entries
            id_lang = node.id.split(":")[0]
            if node_names := node.names.get(id_lang):
                node.names.update(main=node_names)
            node.synonyms.update(main=list(node.synonyms.get(id_lang, [])))
            # add eventual xx entries as synonyms to all languages
            xx_name = node.names.get("xx")
            xx_names = [xx_name] if xx_name else []
            xx_names += node.synonyms.get("xx", [])
            if xx_names:
                for lang in self.config.supported_langs:
                    node.names.setdefault(lang, xx_names[0])
                    lang_synonyms = node.synonyms.setdefault(lang, [])
                    lang_synonyms += xx_names
        return TaxonomyNodeResult(status=FetcherStatus.FOUND, node=node)


class DocumentFetcher(BaseDocumentFetcher):
    def fetch_document(self, stream_name: str, item: JSONType) -> FetcherResult:
        if item.get("action") == "deleted":
            # this is a deleted product, no need to fetch
            return FetcherResult(status=FetcherStatus.REMOVED, document=None)

        code = item["code"]
        url = f"{OFF_API_URL}/api/v3.3/product/{code}"
        try:
            response = http_session.get(url)
        except requests.exceptions.RequestException as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
            return FetcherResult(status=FetcherStatus.RETRY, document=None)
        try:
            json_response = response.json()
        except requests.exceptions.JSONDecodeError as exc:
            logger.warning("Failed to decode JSON response from %s: %s", url, exc)
            return FetcherResult(status=FetcherStatus.OTHER, document=None)

        if (
            not json_response
            or str(json_response.get("status", "")) == "0"
            or not json_response.get("product")
        ):
            # consider it removed
            return FetcherResult(status=FetcherStatus.REMOVED, document=None)

        return FetcherResult(
            status=FetcherStatus.FOUND, document=json_response["product"]
        )


class DocumentPreprocessor(BaseDocumentPreprocessor):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.selected_nutriments = frozenset(
            self.config.fields["nutriments"].fields.keys()
        )
        self.selected_images_keys = (
            frozenset(self.config.fields["selected_images"].fields.keys())
            if "selected_images" in self.config.fields
            else frozenset()
        )

    def preprocess(self, document: JSONType) -> FetcherResult:
        # no need to have a deep-copy here
        document = copy.copy(document)
        # convert obsolete field into bool
        document["obsolete"] = bool(document.get("obsolete"))
        # add "main" language to text_lang fields
        self.add_main_language(document)
        # Don't keep all nutriment values
        self.select_nutriments(document)
        # make nova_groups_markers a list
        self.transform_nova_groups_markers(document)
        self.transform_images(document)
        return FetcherResult(status=FetcherStatus.FOUND, document=document)

    def add_main_language(self, document: JSONType) -> None:
        """We add a "main" language to translated fields (text_lang and
        taxonomies)

        This enables searching in the main language of the product.
        This is important because most of the time,
        products have no entry for a lot of language,
        so this is an interesting fall-back.
        """
        for field in self.config.text_lang_fields:
            if field in document:
                document[field + "_main"] = document[field]

    def select_nutriments(self, document: JSONType):
        """Only selected interesting nutriments, as there are hundreds of
        possible values and we're limited to 1000 fields (total) by
        Elasticsearch.

        Update `document` in place.
        """
        nutriments = document.get("nutriments", {})
        document["nutriments"] = {
            k: nutriments[k] for k in self.selected_nutriments if k in nutriments
        }

    def transform_nova_groups_markers(self, document: JSONType):
        """Transform Nova Groups markers into a list

        ProductOpener structure is made of lists that are to be considered like tuple,
        it is not handy for ES indexing, where we need a list of dict.

        Goes from:
        ```
        {
          3: [['en:ingredient', 'en:chocolate powder']],
          4: [['en:ingredient', 'en:vanillin'], ['en:additive', 'en:e424']],
        }
        ```
        to
        ```
        [
          {'id': 3, marker: [{'marker': 'en:ingredient', 'id': 'en:chocolate powder'}]},
          {'id': 4, marker: [
            {'marker': 'en:ingredient', , 'id': 'en:vanillin'},
            {'marker': 'en:additive', , 'id': 'en:e424'}
          ]},
        ]
        ```
        """
        if "nova_groups_markers" not in document:
            return
        nova_groups_markers = document["nova_groups_markers"]
        document["nova_groups_markers"] = [
            {
                "id": nova_group,
                "marker": [{"type": marker[0], "id": marker[1]} for marker in markers],
            }
            for nova_group, markers in nova_groups_markers.items()
        ]

    def transform_images(self, document: JSONType):
        """
        Images field is very nested. We want to transform it
        to fit ES indexing capability
        and to have only the information we need.

        It creates `uploaded_images` and `selected_images` fields
        according to expected schema.

        In selected_images, we also add informations from the source.
        """
        if "images" not in document:
            return
        uploaded = deep_get(document, "images", "uploaded", default={})
        # create uploaded_images
        document["uploaded_images"] = [
            {
                "id": key,
                "uploaded_t": image["uploaded_t"],
                "uploader": image["uploader"],
                "full_size": {
                    "h": image["sizes"]["full"]["h"],
                    "w": image["sizes"]["full"]["w"],
                },
            }
            for key, image in uploaded.items()
        ]
        # selected images
        document["selected_images"] = {}
        orig_selected_images = deep_get(document, "images", "selected", default={})
        for image_type, selected in orig_selected_images.items():
            if image_type not in self.selected_images_keys:
                continue
            # transform selected images to fit ES indexing capability
            # and to have only the information we need
            document["selected_images"][image_type] = _images = [
                {
                    "lc": lc,
                    "full_size": {
                        "h": image["sizes"]["full"]["h"],
                        "w": image["sizes"]["full"]["w"],
                    },
                    "rev": image["rev"],
                    # will be removed
                    "imgid": image["imgid"],
                }
                for lc, image in selected.items()
            ]
            # add source
            for selected_image in _images:
                imgid = selected_image.pop("imgid")
                uploaded_img = uploaded.get(imgid)
                if not uploaded_img:
                    continue
                selected_image["source"] = {
                    "id": imgid,
                    "uploaded_t": uploaded_img["uploaded_t"],
                    "uploader": uploaded_img["uploader"],
                }
        # remove images
        document.pop("images", None)


class ResultProcessor(BaseResultProcessor):
    def process_after(self, result: JSONType) -> JSONType:
        result |= ResultProcessor.build_image_fields(result)
        return result

    @staticmethod
    def build_image_fields(product: JSONType) -> JSONType:
        """Images are stored in a weird way in Open Food Facts,
        We want to make it far more simple to use in results.
        """
        # Python copy of the code from
        # https://github.com/openfoodfacts/openfoodfacts-server/blob/b297ed858d526332649562cdec5f1d36be184984/lib/ProductOpener/Display.pm#L10128
        code = product["code"]
        fields: JSONType = {}

        for image_type in ["front", "ingredients", "nutrition", "packaging"]:
            display_ids = []
            lang = product.get("lang")
            if lang:
                display_ids.append(f"{image_type}_{lang}")

            display_ids.append(image_type)
            images = convert_to_legacy_schema(product.get("images", {}))

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
                        if "selected_images" not in fields:
                            fields["selected_images"] = {}
                        fields["selected_images"].update(
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
