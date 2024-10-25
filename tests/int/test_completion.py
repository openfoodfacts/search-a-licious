import pytest


@pytest.mark.parametrize(
    "q,taxonomies,langs,results",
    [
        # simple
        ("organ", "labels", "en", [("en:organic", "Organic", 90)]),
        # no case match
        ("ORGAN", "labels", "en", [("en:organic", "Organic", 90)]),
        # french
        ("biol", "labels", "fr", [("en:organic", "biologique", 90)]),
        # multiple languages
        ("biol", "labels", "en,fr", [("en:organic", "biologique", 90)]),
        # xx added to french
        ("Max H", "labels", "fr", [("en:max-havelaar", "Max Havelaar", 85)]),
        # main for an entry without french
        (
            "Fairtrade/Max H",
            "labels",
            "fr,main",
            [("en:max-havelaar", "Fairtrade/Max Havelaar", 85)],
        ),
        # multiple taxonomies
        (
            "fr",
            "labels,categories",
            "en",
            [
                ("en:organic", "From Organic Agriculture", 90),
                ("en:fr-bio-01", "FR-BIO-01", 88),
                ("en:no-artificial-flavors", "free of artificial flavor", 76),
                (
                    "en:fruits-and-vegetables-based-foods",
                    "Fruits and vegetables based foods",
                    64,
                ),
            ],
        ),
        # different answers
        (
            "b",
            "categories",
            "en",
            [
                ("en:biscuits", "biscuit", 89),
                ("en:beverages", "Beverages", 88),
                ("en:chocolate-biscuits", "Biscuit with chocolate", 79),
                ("en:biscuits-and-cakes", "Biscuits and cakes", 79),
                ("en:sweetened-beverages", "Beverages with added sugar", 78),
            ],
        ),
    ],
)
def test_completion(q, taxonomies, langs, results, test_client, synonyms_created):
    response = test_client.get(
        f"/autocomplete?q={q}&langs={langs}&taxonomy_names={taxonomies}&size=5"
    )
    assert response.status_code == 200
    options = response.json()["options"]
    assert len(options) == len(results)
    # only requested taxonomies
    result_taxonomies = set([option["taxonomy_name"] for option in options])
    assert result_taxonomies <= set(taxonomies.split(","))
    # well sorted
    assert sorted([option["score"] for option in options], reverse=True) == [
        option["score"] for option in options
    ]
    # expected results
    completions = [
        (option["id"], option["text"], int(option["score"])) for option in options
    ]
    assert completions == results
