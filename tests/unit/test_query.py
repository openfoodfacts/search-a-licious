from pathlib import Path

import orjson
import pytest
from luqum.parser import parser

from app._types import QueryAnalysis, SearchParameters
from app.config import IndexConfig
from app.es_query_builder import FullTextQueryBuilder
from app.query import add_smart_words, boost_phrases, build_search_query
from app.utils.io import dump_json, load_json

DATA_DIR = Path(__file__).parent / "data"


def load_elasticsearch_query_result(id_: str):
    return load_json(DATA_DIR / f"{id_}.json")


def test_boost_phrases_none():
    # luqum_tree is None
    analysis = QueryAnalysis()
    analysis = boost_phrases(analysis, 3.0)
    assert analysis.luqum_tree is None


@pytest.mark.parametrize(
    "query,boost,expected",
    [
        ("Milk", "2.1", "Milk"),
        ("Whole OR Milk", "2.1", 'Whole OR Milk OR "Whole Milk"^2.1'),
        (
            "Whole OR Milk OR Cream",
            "2.1",
            'Whole OR Milk OR Cream OR "Whole Milk Cream"^2.1',
        ),
        # no boost on AND and UnknownOperation
        ("Whole AND Milk", "2.1", "Whole AND Milk"),
        ("Whole Milk", "2.1", "Whole Milk"),
        # mix things
        (
            'Whole OR Milk OR "complete sentence" OR foo OR spam',
            "2.1",
            'Whole OR Milk OR "complete sentence" OR foo OR spam OR "Whole Milk"^2.1 OR "foo spam"^2.1',
        ),
        # inside search field expressions --> untouched
        ("test:(Whole OR Milk)", "2.1", "test:(Whole OR Milk)"),
        ("Cream OR test:(Whole OR Milk)", "2.1", "Cream OR test:(Whole OR Milk)"),
        # complexe expression
        (
            "Cream AND (spam OR NOT (Whole OR Milk)^3)",
            "2.1",
            'Cream AND (spam OR NOT (Whole OR Milk OR "Whole Milk"^2.1)^3)',
        ),
    ],
)
def test_boost_phrases(query: str, boost: str, expected: str):
    luqum_tree = parser.parse(query)
    analysis = QueryAnalysis(luqum_tree=luqum_tree)
    analysis = boost_phrases(analysis, boost)
    assert str(analysis.luqum_tree) == expected


def test_add_smart_words_none():
    # luqum_tree is None
    analysis = QueryAnalysis()
    analysis = add_smart_words(analysis)
    assert analysis.luqum_tree is None


@pytest.mark.parametrize(
    "query,expected",
    [
        ("Milk", "Milk"),
        ("Milk Foam", "(Milk OR Foam)"),
        # correctly group
        ("Milk Foam Cream foo:spam", "(Milk OR Foam OR Cream) AND foo:spam"),
        (
            'Milk "Heavy Foam" Cream foo:spam',
            'Milk AND "Heavy Foam" AND Cream AND foo:spam',
        ),
        ('Milk Cream "Heavy Foam"', '(Milk OR Cream) AND "Heavy Foam"'),
        (
            "Milk Foam foo:spam Creamy Cheese",
            "(Milk OR Foam) AND foo:spam AND (Creamy OR Cheese)",
        ),
        # deep inside
        ("foo:(spam:(Milk Foam)^2)", "foo:(spam:((Milk OR Foam))^2)"),
    ],
)
def test_add_smart_words(query: str, expected: str):
    luqum_tree = parser.parse(query)
    analysis = QueryAnalysis(luqum_tree=luqum_tree)
    analysis = add_smart_words(analysis)
    assert str(analysis.luqum_tree) == expected


@pytest.mark.parametrize(
    "id_,q,langs,size,page,sort_by,facets",
    [
        ("simple_full_text_query", "flocons d'avoine", {"fr"}, 10, 1, None, None),
        (
            "simple_full_text_query_facets",
            "flocons d'avoine",
            {"fr"},
            10,
            1,
            None,
            ["brands_tags", "labels_tags", "nutrition_grades", "owner"],
        ),
        # sort by descending number of scan count
        ("sort_by_query", "flocons d'avoine", {"fr"}, 10, 1, "-unique_scans_n", None),
        # we change number of results (25 instead of 10) and request page 2
        ("simple_filter_query", 'countries_tags:"en:italy"', {"en"}, 25, 2, None, None),
        (
            "complex_query",
            'bacon de boeuf (countries_tags:"en:italy" AND (categories_tags:"en:beef" AND '
            "(nutriments.salt_100g:[2 TO *] OR nutriments.salt_100g:[0 TO 0.05])))",
            {"en"},
            25,
            2,
            None,
            None,
        ),
        (
            "non_existing_filter_field",
            "non_existing_field:value",
            {"en"},
            25,
            2,
            None,
            None,
        ),
        (
            "empty_query_with_sort_by",
            None,
            {"en"},
            25,
            2,
            "unique_scans_n",
            None,
        ),
        (
            "empty_query_with_sort_by_and_facets",
            None,
            {"en"},
            25,
            2,
            "unique_scans_n",
            ["brands_tags", "categories_tags", "nutrition_grades", "lang"],
        ),
    ],
)
def test_build_search_query(
    # parameters
    id_: str,
    q: str,
    langs: set[str],
    size: int,
    page: int,
    sort_by: str | None,
    facets: list[str] | None,
    # fixtures
    update_results: bool,
    default_config: IndexConfig,
    default_filter_query_builder: FullTextQueryBuilder,
):
    query = build_search_query(
        SearchParameters(
            q=q,
            langs=langs,
            page_size=size,
            page=page,
            sort_by=sort_by,
            facets=facets,
        ),
        es_query_builder=default_filter_query_builder,
    )

    if update_results:
        dump_json(
            DATA_DIR / f"{id_}.json", query._dict_dump(), option=orjson.OPT_INDENT_2
        )

    expected_result = load_elasticsearch_query_result(id_)
    assert query._dict_dump() == expected_result
