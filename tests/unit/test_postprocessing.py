from types import SimpleNamespace

from app.postprocessing import process_taxonomy_completion_response


def _option(id_, taxonomy_name, score, **names):
    return SimpleNamespace(
        text=names.get("en", id_),
        _score=score,
        _source={
            "id": id_,
            "taxonomy_name": taxonomy_name,
            "name": SimpleNamespace(**names),
        },
    )


def _response(**options_by_lang):
    """A response of Elasticsearch with a suggester per language"""
    return SimpleNamespace(
        took=3,
        timed_out=False,
        suggest=SimpleNamespace(
            **{
                f"taxonomy_suggest_{lang}": [SimpleNamespace(options=options)]
                for lang, options in options_by_lang.items()
            }
        ),
    )


def test_options_of_different_taxonomies_with_the_same_id_are_kept():
    """`en:peanuts` is both an allergen and a category"""
    response = _response(
        en=[
            _option("en:peanuts", "allergens", 4.0, en="Peanuts"),
            _option("en:peanuts", "categories", 3.0, en="Peanuts"),
        ]
    )
    options = process_taxonomy_completion_response(response, "pea", ["en"])["options"]
    assert [(o["id"], o["taxonomy_name"]) for o in options] == [
        ("en:peanuts", "allergens"),
        ("en:peanuts", "categories"),
    ]


def test_same_entry_found_in_several_languages_is_merged():
    response = _response(
        en=[_option("en:milk", "categories", 5.0, en="Milk", fr="Lait")],
        fr=[_option("en:milk", "categories", 4.0, en="Milk", fr="Lait")],
    )
    options = process_taxonomy_completion_response(response, "mi", ["fr", "en"])[
        "options"
    ]
    assert len(options) == 1
    assert options[0]["id"] == "en:milk"
    # the name is in the first language asked
    assert options[0]["name"] == "Lait"


def test_options_are_sorted_by_score():
    response = _response(
        en=[
            _option("en:a", "categories", 1.0, en="A"),
            _option("en:b", "categories", 9.0, en="B"),
        ]
    )
    options = process_taxonomy_completion_response(response, "x", ["en"])["options"]
    assert [o["id"] for o in options] == ["en:b", "en:a"]
