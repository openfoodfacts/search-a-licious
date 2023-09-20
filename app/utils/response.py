from app.types import JSONType


def create_response(es_results, projection: set[str] | None = None):
    return [convert_es_result(r, projection) for r in es_results]


def convert_es_result(es_result, projection: set[str] | None = None):
    if not es_result:
        return None

    result_dict = add_images_urls_to_product(es_result.to_dict())

    # Trim fields as needed
    if projection is not None:
        return dict((k, v) for k, v in result_dict.items() if k in projection)

    return result_dict


def add_images_urls_to_product(product: JSONType):
    # Python copy of the code from https://github.com/openfoodfacts/openfoodfacts-server/blob/b297ed858d526332649562cdec5f1d36be184984/lib/ProductOpener/Display.pm#L10128
    code = product["code"]

    for image_type in ["front", "ingredients", "nutrition", "packaging"]:
        display_ids = []
        lang = product.get("lang")
        if lang:
            display_ids.append(f"{image_type}_{lang}")

        display_ids.append(image_type)
        base_url = "https://images.openfoodfacts.org/images/products/"

        for display_id in display_ids:
            images = product.get("images", {})
            if display_id in images and images[display_id].get("sizes"):
                rev_id = product["images"][display_id]["rev"]
                product[
                    f"image_{image_type}_url"
                ] = f"{base_url}{code}/{display_id}.{rev_id}.400.jpg"
                product[
                    f"image_{image_type}_small_url"
                ] = f"{base_url}{code}/{display_id}.{rev_id}.200.jpg"
                product[
                    f"image_{image_type}_thumb_url"
                ] = f"{base_url}{code}/{display_id}.{rev_id}.100.jpg"

                if image_type == "front":
                    product["image_url"] = product[f"image_{image_type}_url"]
                    product["image_small_url"] = product[
                        f"image_{image_type}_small_url"
                    ]
                    product["image_thumb_url"] = product[
                        f"image_{image_type}_thumb_url"
                    ]

        if product.get("languages_codes"):
            for language_code in product["languages_codes"]:
                image_id = f"{image_type}_{language_code}"
                if (
                    product.get("images")
                    and product["images"].get(image_id)
                    and product["images"][image_id]["sizes"]
                ):
                    if not product.get("selected_images"):
                        product["selected_images"] = {}
                    product["selected_images"].update(
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

    return product
