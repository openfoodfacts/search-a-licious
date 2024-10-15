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


def list_of_dict_to_comparable(list_of_dicts):
    return set(tuple(sorted(dict_.items())) for dict_ in list_of_dicts)


def test_simple_charts(sample_data, test_client):
    resp = test_client.get(
        "/search?sort_by=created_t&langs=en&charts=categories,labels,unique_scans_n:completeness"
    )
    assert resp.status_code == 200
    data = resp.json()
    # does not alter search results
    assert data["count"] == 6
    assert set(hits_attr(data, "code")) == set(ALL_CODES)
    # charts are there
    charts = data["charts"]
    assert set(charts.keys()) == set(
        ["categories", "labels", "unique_scans_n:completeness"]
    )
    assert set(c["title"] for c in charts.values()) == set(
        ["categories", "labels", "unique_scans_n x completeness"]
    )
    assert charts["categories"]["data"][0]["values"] == [
        {"category": "en:brown-sugars", "amount": 2},
        {"category": "en:granulated-sugars", "amount": 4},
        {"category": "en:sugars", "amount": 6},
        {"category": "en:sweeteners", "amount": 6},
    ]
    assert charts["labels"]["data"][0]["values"] == [
        {"category": "en:no-lactose", "amount": 2},
        {"category": "en:organic", "amount": 3},
    ]
    assert list_of_dict_to_comparable(
        charts["unique_scans_n:completeness"]["data"][0]["values"]
    ) == list_of_dict_to_comparable(
        [
            {"unique_scans_n": 600, "completeness": 0.5874999999999999},
            {"unique_scans_n": 500, "completeness": 0.5874999999999999},
            {"unique_scans_n": 400, "completeness": 0.5874999999999999},
            {"unique_scans_n": 300, "completeness": 0.5874999999999999},
            {"unique_scans_n": 200, "completeness": 0.5874999999999999},
            {"unique_scans_n": 100, "completeness": 0.5874999999999999},
        ]
    )


def test_charts_bad_fields_fails(test_client):
    resp = test_client.get(
        "/search?sort_by=created_t&langs=en&charts=non_existing_field"
    )
    assert resp.status_code == 422
    assert "Unknown field name in facets/charts" in resp.text
    assert "non_existing_field" in resp.text
    resp = test_client.get("/search?sort_by=created_t&langs=en&charts=unique_scans_n")
    assert resp.status_code == 422
    assert "Non aggregation field name in facets/charts" in resp.text
    assert "unique_scans_n" in resp.text
    resp = test_client.get(
        "/search?sort_by=created_t&langs=en&charts=labels:categories"
    )
    assert resp.status_code == 422
    assert "Non numeric field name" in resp.text
    assert "labels" in resp.text
    assert "categories" in resp.text
    resp = test_client.get(
        "/search?sort_by=created_t&langs=en&charts=non_existing_field:unique_scans_n"
    )
    assert resp.status_code == 422
    assert "Unknown field name" in resp.text
    assert "non_existing_field" in resp.text


def test_multi_lang(sample_data, test_client):
    resp = test_client.get("/search?q=roux&langs=en,fr")
    assert resp.status_code == 200
    data = resp.json()
    assert set(hits_attr(data, "code")) == set(BROWN_SUGAR_CODES)
    resp = test_client.get("/search?q=product_name:roux&langs=en,fr")
    assert resp.status_code == 200
    data = resp.json()
    assert set(hits_attr(data, "code")) == set(BROWN_SUGAR_CODES)


def test_simple_facets(sample_data, test_client):
    resp = test_client.get(
        "/search?sort_by=created_t&langs=en&facets=labels,categories"
    )
    assert resp.status_code == 200
    data = resp.json()
    # does not alter search results
    assert data["count"] == 6
    assert set(hits_attr(data, "code")) == set(ALL_CODES)
    # facets are there
    facets = data["facets"]
    assert set(facets.keys()) == {"labels", "categories"}
    assert list_of_dict_to_comparable(
        facets["labels"]["items"]
    ) == list_of_dict_to_comparable(
        [
            {"key": "en:organic", "name": "Organic", "count": 3, "selected": False},
            {
                "key": "en:no-lactose",
                "name": "No lactose",
                "count": 2,
                "selected": False,
            },
        ]
    )
    assert list_of_dict_to_comparable(
        facets["categories"]["items"]
    ) == list_of_dict_to_comparable(
        [
            {"key": "en:sugars", "name": "Sugars", "count": 6, "selected": False},
            {
                "key": "en:sweeteners",
                "name": "Sweeteners",
                "count": 6,
                "selected": False,
            },
            {
                "key": "en:granulated-sugars",
                "name": "Granulated sugars",
                "count": 4,
                "selected": False,
            },
            {
                "key": "en:brown-sugars",
                "name": "en:brown-sugars",
                "count": 2,
                "selected": False,
            },
        ]
    )


def test_facets_bad_fields_fails(test_client):
    resp = test_client.get(
        "/search?sort_by=created_t&langs=en&facets=non_existing_field"
    )
    assert resp.status_code == 422
    assert "Unknown field name in facets/charts" in resp.text
    assert "non_existing_field" in resp.text
    resp = test_client.get("/search?sort_by=created_t&langs=en&facets=unique_scans_n")
    assert resp.status_code == 422
    assert "Non aggregation field name in facets/charts" in resp.text
    assert "unique_scans_n" in resp.text


def test_pagination(sample_data, test_client):
    resp = test_client.get("/search?sort_by=code&langs=en&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 6
    assert data["page_size"] == 2
    assert data["page_count"] == 3
    assert hits_attr(data, "code") == ALL_CODES[:2]
    resp = test_client.get("/search?sort_by=code&langs=en&page_size=2&page=3")
    assert resp.status_code == 200
    data = resp.json()
    assert hits_attr(data, "code") == ALL_CODES[4:]
    # uneven end
    resp = test_client.get("/search?sort_by=code&langs=en&page_size=5&page=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page_count"] == 2
    assert hits_attr(data, "code") == ALL_CODES[-1:]
    # out of range
    resp = test_client.get("/search?sort_by=code&langs=en&page_size=2&page=20")
    assert resp.status_code == 200
    data = resp.json()
    assert hits_attr(data, "code") == []


def test_debug_infos(sample_data, test_client):
    resp = test_client.get(
        "/search?q=categories:organic&langs=en&facets=labels&debug_info=es_query,lucene_query,aggregations"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data["debug"].keys()) == {"lucene_query", "es_query", "aggregations"}
