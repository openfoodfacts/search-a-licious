from pathlib import Path

import orjson
import pytest
from luqum.elasticsearch import ElasticsearchQueryBuilder

from app._types import JSONType
from app.config import IndexConfig
from app.query import build_search_query, decompose_query, parse_query
from app.utils.io import dump_json, load_json

DATA_DIR = Path(__file__).parent / "data"


def load_elasticsearch_query_result(id_: str):
    return load_json(DATA_DIR / f"{id_}.json")


@pytest.mark.parametrize(
    "q,expected_filter_query,expected_fulltext",
    [
        # single term
        (
            "word",
            None,
            "word",
        ),
        (
            'word1 (states_tags:"en:france" OR states_tags:"en:germany") word2 labels_tags:"en:organic" word3',
            {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "should": [
                                    {"term": {"states_tags": {"value": "en:france"}}},
                                    {"term": {"states_tags": {"value": "en:germany"}}},
                                ]
                            }
                        },
                        {"term": {"labels_tags": {"value": "en:organic"}}},
                    ]
                },
            },
            "word1 word2 word3",
        ),
        # only non-filter keywords
        (
            "word1 word2",
            None,
            "word1 word2",
        ),
        (
            'states_tags:"en:spain"',
            {"bool": {"must": [{"term": {"states_tags": {"value": "en:spain"}}}]}},
            "",
        ),
        (
            "nutriments.salt_100g:[2 TO *]",
            {"bool": {"must": [{"range": {"nutriments.salt_100g": {"gte": "2"}}}]}},
            "",
        ),
        (
            "non_existing_field:value",
            {
                "bool": {
                    "must": [
                        {
                            "match": {
                                "non_existing_field": {
                                    "query": "value",
                                    "zero_terms_query": "all",
                                }
                            }
                        }
                    ]
                }
            },
            "",
        ),
    ],
)
def test_decompose_query(
    q: str, expected_filter_query: list[JSONType], expected_fulltext: str
):
    query_builder = ElasticsearchQueryBuilder(
        default_operator=ElasticsearchQueryBuilder.MUST,
        not_analyzed_fields=["states_tags", "labels_tags", "countries_tags"],
        object_fields=["nutriments", "nutriments.salt_100g"],
    )
    analysis = parse_query(q)
    analysis = decompose_query(analysis, filter_query_builder=query_builder)
    assert analysis.filter_query == expected_filter_query
    assert analysis.fulltext == expected_fulltext


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
    id_: str,
    q: str,
    langs: set[str],
    size: int,
    page: int,
    sort_by: str | None,
    facets: list[str] | None,
    update_results: bool,
    default_config: IndexConfig,
    default_filter_query_builder: ElasticsearchQueryBuilder,
):
    query = build_search_query(
        q=q,
        langs=langs,
        size=size,
        page=page,
        config=default_config,
        filter_query_builder=default_filter_query_builder,
        sort_by=sort_by,
        facets=facets,
    )

    if update_results:
        dump_json(
            DATA_DIR / f"{id_}.json", query._dict_dump(), option=orjson.OPT_INDENT_2
        )

    expected_result = load_elasticsearch_query_result(id_)
    assert query._dict_dump() == expected_result
