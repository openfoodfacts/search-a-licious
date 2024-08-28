from pathlib import Path

import orjson
import pytest
from luqum.parser import parser

from app._types import QueryAnalysis, SearchParameters
from app.config import IndexConfig
from app.es_query_builder import FullTextQueryBuilder
from app.query import boost_phrases, build_search_query, resolve_unknown_operation
from app.utils.io import dump_json, load_json

DATA_DIR = Path(__file__).parent / "data"


def load_elasticsearch_query_result(id_: str):
    return load_json(DATA_DIR / f"{id_}.json")


def test_boost_phrases_none():
    # luqum_tree is None
    analysis = QueryAnalysis()
    analysis = boost_phrases(analysis, 3.0, 2)
    assert analysis.luqum_tree is None


@pytest.mark.parametrize(
    "query,proximity,expected",
    [
        ("Milk", 3, "Milk"),
        ("Whole Milk", None, '((Whole AND Milk) OR "Whole Milk"^2.1)'),
        ("Whole Milk", 3, '((Whole AND Milk) OR "Whole Milk"~3^2.1)'),
        ("Whole AND Milk", 3, '((Whole AND Milk) OR "Whole Milk"~3^2.1)'),
        (
            "Whole Milk Cream",
            3,
            '((Whole AND Milk AND Cream) OR "Whole Milk Cream"~3^2.1)',
        ),
        # no boost on OR
        ("Whole OR Milk", 3, "Whole OR Milk"),
        # and in search fields expressions
        (
            "Cream AND labels:(Vegan AND Fair-trade)",
            3,
            "Cream AND labels:(Vegan AND Fair-trade)",
        ),
        # mix things
        (
            'Whole Milk "No gluten" Vegetarian Soup',
            3,
            '((Whole AND Milk) OR "Whole Milk"~3^2.1) AND "No gluten" AND ((Vegetarian AND Soup) OR "Vegetarian Soup"~3^2.1)',
        ),
        # complexe expression
        (
            "Cream AND (labels:Vegan OR NOT (Whole AND Milk)^3)",
            3,
            'Cream AND (labels:Vegan OR NOT (((Whole AND Milk) OR "Whole Milk"~3^2.1))^3)',
        ),
    ],
)
def test_boost_phrases(query: str, proximity: int | None, expected: str):
    luqum_tree = parser.parse(query)
    analysis = QueryAnalysis(luqum_tree=luqum_tree)
    # resolve unknown operation
    analysis = resolve_unknown_operation(analysis)
    analysis = boost_phrases(analysis, 2.1, proximity)
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
