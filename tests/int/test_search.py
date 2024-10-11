import pytest

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
            code="3012345670001",
            product_name_en="Main Granulated Sugar",
            product_name_fr="Sucre semoule principal",
            categories_tags=["en:sweeteners", "en:sugars", "en:granulated-sugars"],
            labels_tags=["en:no-lactose", "en:organic"],
        ),
        Product(
            code="3012345670002",
            product_name_en="Organic Granulated Sugar",
            product_name_fr="Sucre semoule bio",
            categories_tags=["en:sweeteners", "en:sugars", "en:granulated-sugars"],
            labels_tags=["en:organic"],
        ),
        Product(
            code="3012345670003",
            product_name_en="No Lactose Granulated Sugar",
            product_name_fr=None,
            categories_tags=["en:sweeteners", "en:sugars", "en:granulated-sugars"],
            labels_tags=["en:no-lactose"],
        ),
        Product(
            code="3012345670004",
            product_name_en="No label Granulated Sugar",
            product_name_fr=None,
            categories_tags=["en:sweeteners", "en:sugars", "en:granulated-sugars"],
            labels_tags=None,
        ),
        Product(
            code="3012345670005",
            product_name_en="Organic Brown Sugar",
            product_name_fr="Sucre roux bio",
            categories_tags=["en:sweeteners", "en:sugars", "en:brown-sugars"],
            labels_tags=["en:organic"],
            **brown_sugar_nutriments,
        ),
        Product(
            code="3012345670006",
            product_name_en="Brown Sugar",
            product_name_fr="Sucre roux",
            categories_tags=["en:sweeteners", "en:sugars", "en:brown-sugars"],
            labels_tags=[],
            **brown_sugar_nutriments,
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


@pytest.fixture
def sample_data(data_ingester):
    data = search_sample()
    data_ingester(data)
    yield data


def hits_attr(data, name):
    """small utility to list attrs"""
    return [product[name] for product in data["hits"]]


def test_search_all(sample_data, test_client):
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


def test_search_sort_by_created_t(sample_data, test_client):
    resp = test_client.get("/search?sort_by=created_t")
    assert resp.status_code == 200
    data = resp.json()
    # all products
    assert data["count"] == 6
    assert len(data["hits"]) == 6
    # no duplicates
    assert len(set(hits_attr(data, "code"))) == 6
    # sorted ok
    created_t = hits_attr(data, "created_t")
    assert sorted(created_t) == created_t

    # reverse sort
    resp = test_client.get("/search?sort_by=-created_t")
    assert resp.status_code == 200
    data = resp.json()
    # all products
    assert data["count"] == 6
    # sorted ok
    created_t = hits_attr(data, "created_t")
    assert sorted(created_t) == list(reversed(created_t))


ALL_CODES = [s["code"] for s in search_sample()]
ORGANIC_CODES = ["3012345670001", "3012345670002", "3012345670005"]
BROWN_SUGAR_CODES = ["3012345670005", "3012345670006"]


def xfail_param(*args):
    return pytest.param(*args, marks=pytest.mark.xfail)


@pytest.mark.parametrize(
    "req,codes",
    [
        ("q=sugar", ALL_CODES),
        ("q=brown", ["3012345670005", "3012345670006"]),
        # this also searches in labels
        ("q=organic", ORGANIC_CODES),
        # synonym of label organic, will work only if we boost phrase
        ("q=organically grown&boost_phrase=1", ORGANIC_CODES),
        # also works for translations
        ("q=bio&langs=fr", ORGANIC_CODES),
        ("q=bio&langs=en,fr", ORGANIC_CODES),
        # with more terms this does not work, yet, see
        xfail_param("q=organically grown plants&boost_phrase=1", ORGANIC_CODES),
        # as phrase
        ('q="organically grown"', ORGANIC_CODES),
        # Note: we need this double escape for simple quote, I'm not sure why…
        ('q="issu de l\\\'agriculture biologique"&langs=fr', ORGANIC_CODES),
        # synonyms on label field
        ('q=labels:"organically grown"', ORGANIC_CODES),
        # search a field
        ("q=product_name:brown sugar", BROWN_SUGAR_CODES),
        ('q=product_name:"brown sugar"', BROWN_SUGAR_CODES),
        ("q=product_name:Sucre roux&langs=fr", BROWN_SUGAR_CODES),
        ('q=product_name:"Sucre roux"&langs=fr', BROWN_SUGAR_CODES),
        # search in multiple fields
        ('q="brown sugar" organic', ["3012345670005"]),
    ],
)
def test_search_full_text(req, codes, sample_data, test_client):
    resp = test_client.get(f"/search?{req}")
    assert resp.status_code == 200
    data = resp.json()
    assert set(hits_attr(data, "code")) == set(codes)


def test_extra_params_rejected(test_client):
    # lang instead of langs
    resp = test_client.get("/search?sort_by=created_t&lang=fr")
    assert resp.status_code == 422
    assert resp.json() == {
        "detail": [
            {
                "type": "extra_forbidden",
                "loc": ["query", "lang"],
                "msg": "Extra inputs are not permitted",
                "input": "fr",
            }
        ]
    }
    resp = test_client.post("/search", json=dict(sort_by="created_t", lang="fr"))
    assert resp.status_code == 422
    assert resp.json() == {
        "detail": [
            {
                "type": "extra_forbidden",
                "loc": ["body", "lang"],
                "msg": "Extra inputs are not permitted",
                "input": "fr",
            }
        ]
    }
