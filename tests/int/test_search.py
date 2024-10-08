from .data_generation import Product


def search_sample():
    # category granulated sugars has synonyms white sugars / refined sugars
    # and in french saccharose, saccarose, sucre blanc, suche de table
    # label organic has synonyms organically grown / organically produced
    # / from organic farming
    # and french bio / biologique / issu de l'agriculture biologique

    # some brown sugar nutrients
    brown_sugar_nutriments = dict(
        nutriments__energy_kcal_100g=350,
        nutriments__carbohydrates_100g=90,
        nutriments__sugars_100g=90,
        nutriments__proteins_100g=1.5,
    )
    data = [
        # some sugar
        Product(
            product_name_en="Main Granulated Sugar",
            product_name_fr="Sucre semoule principal",
            categories_tags=["en:sweeteners", "en:sugars", "en:granulated-sugars"],
            labels_tags=["en:no-lactose", "en:organic"],
        ),
        Product(
            product_name_en="Organic Granulated Sugar",
            product_name_fr="Sucre semoule bio",
            categories_tags=["en:sweeteners", "en:sugars", "en:granulated-sugars"],
            labels_tags=["en:organic"],
        ),
        Product(
            product_name_en="No Lactose Granulated Sugar",
            product_name_fr=None,
            categories_tags=["en:sweeteners", "en:sugars", "en:granulated-sugars"],
            labels_tags=["en:no-lactose"],
        ),
        Product(
            product_name_en="No label Granulated Sugar",
            product_name_fr=None,
            categories_tags=["en:sweeteners", "en:sugars", "en:granulated-sugars"],
            labels_tags=None,
        ),
        Product(
            product_name_en="Organic Brown Sugar",
            product_name_fr="Sucre brun",
            categories_tags=["en:sweeteners", "en:sugars", "en:brown-sugars"],
            labels_tags=["en:organic"],
            **brown_sugar_nutriments
        ),
        Product(
            product_name_en="Brown Sugar",
            product_name_fr="Sucre brun",
            categories_tags=["en:sweeteners", "en:sugars", "en:brown-sugars"],
            labels_tags=[],
            **brown_sugar_nutriments
        ),
    ]
    # make created_t, modified_t and unique_scans_n predictable for sorting
    created_t = 1537090000
    modified_t = 1700525044
    day_in_second = 86400
    for i, product in enumerate(data):
        product["created_t"] = created_t - i * day_in_second
        product["last_modified_t"] = modified_t + i * day_in_second
        product["unique_scans_n"] = (i + 1) * 100
    return data


def hits_attr(data, name):
    """small utility to list attrs"""
    return [product[name] for product in data["hits"]]


def test_search_all(data_ingester, test_client):
    data_ingester(search_sample())
    resp = test_client.get("/search?sort_by=unique_scans_n")
    assert resp.status_code == 200
    data = resp.json()
    # all products
    assert data["count"] == 6
    assert len(data["hits"]) == 6
    # no duplicates
    assert len(set(hits_attr(data, "code"))) == 6
    # sorted ok
    assert hits_attr(data, "unique_scans_n") == list(range(100, 700, 100))
