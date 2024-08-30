from pathlib import Path
from typing import Any

import orjson
import pytest
from luqum.parser import parser

from app._types import QueryAnalysis, SearchParameters
from app.config import IndexConfig
from app.es_query_builder import FullTextQueryBuilder
from app.exceptions import QueryAnalysisError
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
    "id_,q,langs,size,page,sort_by,facets,boost_phrase",
    [
        ("simple_full_text_query", "flocons d'avoine", {"fr"}, 10, 1, None, None, True),
        (
            "simple_full_text_query_facets",
            "flocons d'avoine",
            {"fr"},
            10,
            1,
            None,
            ["brands", "labels", "nutrition_grades", "owner"],
            True,
        ),
        # sort by descending number of scan count
        (
            "sort_by_query",
            "flocons d'avoine",
            {"fr"},
            10,
            1,
            "-unique_scans_n",
            None,
            True,
        ),
        # we change number of results (25 instead of 10) and request page 2
        (
            "simple_filter_query",
            'countries:"en:italy"',
            {"en"},
            25,
            2,
            None,
            None,
            True,
        ),
        (
            "complex_query",
            'bacon de boeuf (countries:italy AND (categories:"en:beef" AND '
            "(nutriments.salt_100g:[2 TO *] OR nutriments.salt_100g:[0 TO 0.05])))",
            {"en"},
            25,
            2,
            None,
            None,
            True,
        ),
        (
            "empty_query_with_sort_by",
            None,
            {"en"},
            25,
            2,
            "unique_scans_n",
            None,
            True,
        ),
        (
            "empty_query_with_sort_by_and_facets",
            None,
            {"en"},
            25,
            2,
            "unique_scans_n",
            ["brands", "categories", "nutrition_grades", "lang"],
            True,
        ),
        (
            "open_range",
            "(unique_scans_n:>2 AND unique_scans_n:<3) OR unique_scans_n:>=10",
            {"en"},
            25,
            2,
            None,
            None,
            True,
        ),
        (
            # it should be ok for now, until we implement subfields
            "non_existing_subfield",
            "Milk AND nutriments:(nonexisting:>=3)",
            {"en"},
            25,
            2,
            None,
            None,
            True,
        ),
        (
            # * in a phrase is legit, it does not have the wildcard meaning
            "wildcard_in_phrase_is_legit",
            'Milk AND "*" AND categories:"*"',
            {"en"},
            25,
            2,
            None,
            None,
            True,
        ),
        # TODO
        # - test scripts sorting
        # - test ranges and OPen ranges
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
    boost_phrase: bool,
    # fixtures
    update_results: bool,
    default_config: IndexConfig,
    default_filter_query_builder: FullTextQueryBuilder,
):
    params = SearchParameters(
        q=q,
        langs=langs,
        page_size=size,
        page=page,
        sort_by=sort_by,
        facets=facets,
        boost_phrase=boost_phrase,
    )
    query = build_search_query(
        params,
        es_query_builder=default_filter_query_builder,
    )

    if update_results:
        dump_json(
            DATA_DIR / f"{id_}.json", query._dict_dump(), option=orjson.OPT_INDENT_2
        )

    expected_result = load_elasticsearch_query_result(id_)
    assert query._dict_dump() == expected_result


@pytest.mark.parametrize(
    "specific_params, error_msg",
    [
        # non existing field
        ({"q": "nonexisting:Milk"}, "field 'nonexisting' not found in index config"),
        # non existing field inside more complex request
        (
            {"q": "Milk AND (categories:en:Whole OR (nonexisting:Whole)^2)"},
            "field 'nonexisting' not found in index config",
        ),
        # wildcard alone
        (
            {"q": "Milk OR (Cream AND *)"},
            "Free wildcards are not allowed in full text queries",
        ),
        # unparsable request
        # missing closing bracket or parenthesis
        ({"q": "completeness:[2 TO 22"}, "Request could not be analyzed by luqum"),
        ({"q": "(Milk OR Cream"}, "Request could not be analyzed by luqum"),
        # And and OR on same level
        (
            {"q": "Milk OR Cream AND Coffee"},
            "Request could not be transformed by luqum",
        ),
    ],
)
def test_build_search_query_failure(
    specific_params: dict[str, Any],
    error_msg: str,
    default_config: IndexConfig,
    default_filter_query_builder: FullTextQueryBuilder,
):
    # base search params
    params = {
        "q": "Milk",
        "langs": ["fr", "en"],
        "page_size": 5,
        "page": 1,
        "sort_by": None,
        "facets": None,
        "boost_phrase": True,
    }
    params.update(specific_params)
    with pytest.raises((QueryAnalysisError, ValueError)) as exc_info:
        build_search_query(
            SearchParameters(**params),
            es_query_builder=default_filter_query_builder,
        )
    assert error_msg in str(exc_info.value)
