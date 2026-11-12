from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from luqum.parser import parser

from app._types import (
    JSONType,
    PostChartSearchParameters,
    QueryAnalysis,
    ScatterChart,
    SearchParameters,
)
from app.config import ANALYZER_LANG_MAPPING, Config, IndexConfig
from app.es_query_builder import FullTextQueryBuilder
from app.exceptions import QueryAnalysisError
from app.query import (
    add_languages_suffix,
    boost_phrases,
    build_search_query,
    parse_query,
    resolve_unknown_operation,
)
from app.query_transformers import QueryCheck


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
            "(nutriments.fat_100g:[2 TO *] OR nutriments.fat_100g:[0 TO 0.05])))",
            ["en"],
            25,
            2,
            None,
            None,
            True,
        ),
        (
            # a valid nested sub-field must not be rejected
            "nested_subfield_group",
            "nutriments:(fat_100g:>=3)",
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
        # non existing sub-field
        (
            # goes past a leaf field
            {"q": "nutriments.fat_100g.x:value"},
            "field 'nutriments.fat_100g.x' not found in index config",
        ),
        # a language suffix is not valid under a field without lang sub-fields
        (
            {"q": "nutriments.fat_100g.en:1"},
            "field 'nutriments.fat_100g.en' not found in index config",
        ),
        # a language code alone is not a field
        ({"q": "en:foo"}, "field 'en' not found in index config"),
        (
            {"q": "Milk AND nutriments:(nonexisting:>=3)"},
            "field 'nutriments.nonexisting' not found in index config",
        ),
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


def test_parse_query_is_thread_safe():
    """The PLY lexer is stateful: parsing concurrently must give the same trees
    as parsing sequentially."""
    long_queries = [
        " OR ".join(
            f'(categories:"en:cat{i}" AND brands:brand{i}) OR product_name:foo{i}'
            for i in range(start, start + 10)
        )
        for start in (0, 100)
    ]
    expected = {q: str(parse_query(q).luqum_tree) for q in long_queries}

    def parse(q):
        try:
            return q, str(parse_query(q).luqum_tree)
        except Exception as e:  # a race can raise parse errors
            return q, repr(e)

    # several rounds, so that a race is practically certain to show up
    with ThreadPoolExecutor(max_workers=16) as executor:
        for _ in range(3):
            results = list(executor.map(parse, long_queries * 400))
            wrong = [(q, r) for q, r in results if r != expected[q]]
            assert not wrong, f"{len(wrong)} of {len(results)} parses are wrong"


def test_add_languages_suffix_ignores_unsupported_langs(default_config: IndexConfig):
    analysis = QueryAnalysis(luqum_tree=parser.parse("categories:organic"))
    analysis = add_languages_suffix(analysis, ["en", "not_a_lang"], default_config)
    assert "categories.en" in str(analysis.luqum_tree)
    assert "not_a_lang" not in str(analysis.luqum_tree)


def test_query_check_accepts_lang_suffix_on_nested_taxonomy(
    default_config: IndexConfig,
):
    # the index generates `packagings.material.<lang>` sub-fields
    checker = QueryCheck(index_config=default_config, zeal=1)
    assert not checker.errors(parser.parse("packagings.material.en:plastic"))


@pytest.mark.parametrize("q", ["-sugar", "NOT milk", "milk -sugar"])
def test_query_check_accepts_negation(q: str, default_config: IndexConfig):
    # a top-level negation used to raise an IndexError (HTTP 500)
    checker = QueryCheck(index_config=default_config, zeal=1)
    assert not checker.errors(parser.parse(q))


@pytest.mark.parametrize("q", ["milk", "categories:organic"])
def test_add_languages_suffix_keeps_query_without_supported_langs(
    q: str, default_config: IndexConfig
):
    analysis = QueryAnalysis(luqum_tree=parser.parse(q))
    analysis = add_languages_suffix(analysis, ["not_a_lang"], default_config)
    assert str(analysis.luqum_tree) == q


@pytest.mark.parametrize("q", ["", " ", "   ", "\t", "\n", " \n\t "])
def test_blank_query_is_no_query(q, default_config, default_filter_query_builder):
    """A query with only spaces is like no query (it used to be a parsing error)"""
    analysis = build_search_query(
        SearchParameters(q=q, langs=["en"], page_size=5, page=1),
        es_query_builder=default_filter_query_builder,
    )
    assert analysis.luqum_tree is None
    assert analysis.es_query.to_dict().get("query") is None


@pytest.mark.parametrize("lang", ["cs", "sk", "uk"])
def test_czech_slovak_ukrainian_are_searched(
    lang, default_config, default_filter_query_builder
):
    """Those languages used to be silently dropped from `langs`"""
    analysis = build_search_query(
        SearchParameters(q="water", langs=[lang, "en"], page_size=5, page=1),
        es_query_builder=default_filter_query_builder,
    )
    fields = analysis.es_query.to_dict()["query"]["multi_match"]["fields"]
    assert f"product_name.{lang}" in fields
    assert "product_name.en" in fields


def test_prod_config_supports_czech_slovak_ukrainian():
    conf = Config.from_yaml(Path("data/config/openfoodfacts.yml"))
    assert {"cs", "sk", "uk"} <= conf.indices["off"].supported_langs_set
    # `cs` has a Czech analyzer, the other ones use the standard one
    assert ANALYZER_LANG_MAPPING["cs"] == "czech"


def test_query_check_accepts_hyphenated_field_names(default_config: IndexConfig):
    # nutrient fields are named like `energy-kcal_100g`
    checker = QueryCheck(index_config=default_config, zeal=1)
    q = "nutriments.energy-kcal_100g:[* TO 100]"
    assert not checker.errors(parser.parse(q))


def test_query_check_rejects_unknown_hyphenated_field(default_config: IndexConfig):
    checker = QueryCheck(index_config=default_config, zeal=1)
    errors = checker.errors(parser.parse("nutriments.not-a-field_100g:[* TO 100]"))
    assert "not found in index config" in str(errors)


def test_build_chart_query(
    default_config: IndexConfig,
    default_filter_query_builder: FullTextQueryBuilder,
):
    charts = [
        ScatterChart(x="nutriments.fat_100g", y="completeness"),
        ScatterChart(x="scans_n", y="completeness"),
    ]
    params = PostChartSearchParameters(
        q="milk", charts=charts, max_entries=7, sort_by="-scans_n"
    )
    es_query = build_search_query(
        params, es_query_builder=default_filter_query_builder
    )._dict_dump()["es_query"]
    assert es_query["size"] == 7
    assert es_query["from"] == 0
    assert es_query["_source"] == ["completeness", "nutriments.fat_100g", "scans_n"]
    assert "aggs" not in es_query
    assert es_query["sort"] == [{"scans_n": {"order": "desc"}}]
    should = [
        f["bool"]["should"]
        for f in es_query["query"]["bool"]["filter"]
        if "should" in f.get("bool", {})
    ]
    assert should == [
        [
            {"bool": {"filter": [{"exists": {"field": x}}, {"exists": {"field": y}}]}}
            for x, y in [
                ("nutriments.fat_100g", "completeness"),
                ("scans_n", "completeness"),
            ]
        ]
    ]


def test_build_chart_query_sort_script(
    default_config: IndexConfig,
    default_filter_query_builder: FullTextQueryBuilder,
):
    params = PostChartSearchParameters(
        charts=[ScatterChart(x="scans_n", y="completeness")],
        sort_by="personal_score",
        sort_params={"environmental_score": 1, "nutri_score": 1, "nova_group": 1},
    )
    es_query = build_search_query(
        params, es_query_builder=default_filter_query_builder
    )._dict_dump()["es_query"]
    assert "_script" in es_query["sort"][0]
