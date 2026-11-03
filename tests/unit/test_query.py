from typing import Any

import pytest
from luqum.parser import parser

from app._types import JSONType, QueryAnalysis, SearchParameters
from app.config import IndexConfig
from app.es_query_builder import FullTextQueryBuilder
from app.exceptions import QueryAnalysisError
from app.query import boost_phrases, build_search_query, resolve_unknown_operation


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
        ("simple_full_text_query", "flocons d'avoine", ["fr"], 10, 1, None, None, True),
        (
            "simple_full_text_query_facets",
            "flocons d'avoine",
            ["fr"],
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
            ["fr"],
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
            ["en"],
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
            ["en"],
            25,
            2,
            None,
            None,
            True,
        ),
        (
            "empty_query_with_sort_by",
            None,
            ["en"],
            25,
            2,
            "unique_scans_n",
            None,
            True,
        ),
        (
            "empty_query_with_sort_by_and_facets",
            None,
            ["en"],
            25,
            2,
            "unique_scans_n",
            ["brands", "categories", "nutrition_grades", "lang"],
            True,
        ),
        (
            "open_range",
            "(unique_scans_n:>2 AND unique_scans_n:<3) OR unique_scans_n:>=10",
            ["en"],
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
            ["en"],
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
            ["en"],
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
    langs: list[str],
    size: int,
    page: int,
    sort_by: str | None,
    facets: list[str] | None,
    boost_phrase: bool,
    # fixtures
    load_expected_result,
    default_config: IndexConfig,
    default_filter_query_builder: FullTextQueryBuilder,
    query_builder_cache_is_empty: None,
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
    data = query._dict_dump()

    expected_result = load_expected_result(id_, data)
    assert data == expected_result


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
    params: JSONType = {
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


def test_filter_by_langs_adds_filter(
    default_config: IndexConfig,
    default_filter_query_builder: FullTextQueryBuilder,
):
    params = SearchParameters(
        q="Apfel",
        langs=["de"],
        filter_by_langs=True,
        page_size=10,
        page=1,
    )
    query = build_search_query(params, es_query_builder=default_filter_query_builder)
    es_dict = query.es_query.to_dict()
    filter_clauses = es_dict["query"]["bool"]["filter"]
    assert any(
        clause.get("terms", {}).get("languages_codes") == ["de"]
        for clause in filter_clauses
    )


def test_filter_by_langs_disabled_has_no_filter(
    default_config: IndexConfig,
    default_filter_query_builder: FullTextQueryBuilder,
):
    params = SearchParameters(
        q="Apfel",
        langs=["de"],
        filter_by_langs=False,
        page_size=10,
        page=1,
    )
    query = build_search_query(params, es_query_builder=default_filter_query_builder)
    es_dict = query.es_query.to_dict()
    bool_clause = es_dict.get("query", {}).get("bool", {})
    assert "filter" not in bool_clause


def test_filter_by_langs_excludes_main(
    default_config: IndexConfig,
    default_filter_query_builder: FullTextQueryBuilder,
):
    params = SearchParameters(
        q="Milk",
        langs=["fr", "main"],
        filter_by_langs=True,
        page_size=10,
        page=1,
    )
    query = build_search_query(params, es_query_builder=default_filter_query_builder)
    es_dict = query.es_query.to_dict()
    filter_clauses = es_dict["query"]["bool"]["filter"]
    terms_values = None
    for clause in filter_clauses:
        if "terms" in clause and "languages_codes" in clause["terms"]:
            terms_values = clause["terms"]["languages_codes"]
    assert terms_values is not None
    assert "main" not in terms_values
    assert "fr" in terms_values


def test_filter_by_langs_only_main_skips_filter(
    default_config: IndexConfig,
    default_filter_query_builder: FullTextQueryBuilder,
):
    params = SearchParameters(
        q="Milk",
        langs=["main"],
        filter_by_langs=True,
        page_size=10,
        page=1,
    )
    query = build_search_query(params, es_query_builder=default_filter_query_builder)
    es_dict = query.es_query.to_dict()
    bool_clause = es_dict.get("query", {}).get("bool", {})
    assert "filter" not in bool_clause


def test_filter_by_langs_missing_field_raises(
    default_config: IndexConfig,
    default_filter_query_builder: FullTextQueryBuilder,
):
    import types

    from app.exceptions import QueryCheckError
    from app.query import build_es_query

    fields_no_lang_codes = {
        k: v for k, v in default_config.fields.items() if k != "languages_codes"
    }
    fake_index_config = types.SimpleNamespace(
        index=default_config.index,
        fields=fields_no_lang_codes,
        scripts=None,
    )
    fake_params = types.SimpleNamespace(
        langs=["de"],
        filter_by_langs=True,
        facets=None,
        charts=None,
        sort_by=None,
        page_size=10,
        page=1,
        index_config=fake_index_config,
        valid_index_id="off",
        uses_sort_script=False,
        sign_sort_by=("+", None),
    )

    analysis = QueryAnalysis(text_query="Apfel")

    with pytest.raises(QueryCheckError) as exc_info:
        build_es_query(analysis, fake_params, default_filter_query_builder)
    assert "languages_codes" in str(exc_info.value)
