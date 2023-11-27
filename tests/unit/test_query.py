from pathlib import Path

import orjson
import pytest
from luqum.elasticsearch import ElasticsearchQueryBuilder
from luqum.parser import parser

from app._types import JSONType
from app.config import Config
from app.query import (
    UnknownOperationRemover,
    build_search_query,
    parse_lucene_dsl_query,
)
from app.utils.io import dump_json, load_json

DATA_DIR = Path(__file__).parent / "data"


def load_elasticsearch_query_result(id_: str):
    return load_json(DATA_DIR / f"{id_}.json")


class TestUnknownOperationRemover:
    @pytest.mark.parametrize(
        "query,expected",
        [
            ('word1 states_tags:"en:france" word2', 'states_tags:"en:france"'),
            (
                '(states_tags:"en:france" OR states_tags:"en:germany") word2 word3',
                '(states_tags:"en:france" OR states_tags:"en:germany")',
            ),
            (
                'word1 (states_tags:"en:france" word2) word3 labels_tags:"en:organic"',
                '(states_tags:"en:france" ) labels_tags:"en:organic"',
            ),
            # We shouldn't change the tree if there is a single filter
            (
                'categories_tags:"en:textured-soy-protein"',
                'categories_tags:"en:textured-soy-protein"',
            ),
        ],
    )
    def test_transform(self, query: str, expected: str):
        luqum_tree = parser.parse(query)
        new_tree = UnknownOperationRemover().visit(luqum_tree)
        assert str(new_tree).strip(" ") == expected


@pytest.mark.parametrize(
    "q,expected_filter_clauses,expected_remaining_terms",
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
            {"term": {"states_tags": {"value": "en:spain"}}},
            "",
        ),
        (
            "nutriments.salt_100g:[2 TO *]",
            {"range": {"nutriments.salt_100g": {"gte": "2"}}},
            "",
        ),
        (
            "non_existing_field:value",
            {
                "match": {
                    "non_existing_field": {"query": "value", "zero_terms_query": "none"}
                }
            },
            "",
        ),
    ],
)
def test_parse_lucene_dsl_query(
    q: str, expected_filter_clauses: list[JSONType], expected_remaining_terms: str
):
    query_builder = ElasticsearchQueryBuilder(
        default_operator=ElasticsearchQueryBuilder.MUST,
        not_analyzed_fields=["states_tags", "labels_tags", "countries_tags"],
        object_fields=["nutriments", "nutriments.salt_100g"],
    )
    filter_clauses, remaining_terms = parse_lucene_dsl_query(q, query_builder)
    assert filter_clauses == expected_filter_clauses
    assert remaining_terms == expected_remaining_terms


@pytest.mark.parametrize(
    "id_,q,langs,size,page,sort_by",
    [
        ("simple_full_text_query", "flocons d'avoine", {"fr"}, 10, 1, None),
        # sort by descending number of scan count
        ("sort_by_query", "flocons d'avoine", {"fr"}, 10, 1, "-unique_scans_n"),
        # we change number of results (25 instead of 10) and request page 2
        ("simple_filter_query", 'countries_tags:"en:italy"', {"en"}, 25, 2, None),
        (
            "complex_query",
            'bacon de boeuf (countries_tags:"en:italy" AND (categories_tags:"en:beef" AND '
            "(nutriments.salt_100g:[2 TO *] OR nutriments.salt_100g:[0 TO 0.05])))",
            {"en"},
            25,
            2,
            None,
        ),
        (
            "non_existing_filter_field",
            "non_existing_field:value",
            {"en"},
            25,
            2,
            None,
        ),
        (
            "empty_query_with_sort_by",
            None,
            {"en"},
            25,
            2,
            "unique_scans_n",
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
    update_results: bool,
    default_config: Config,
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
    )

    if update_results:
        dump_json(DATA_DIR / f"{id_}.json", query.to_dict(), option=orjson.OPT_INDENT_2)

    expected_result = load_elasticsearch_query_result(id_)
    assert query.to_dict() == expected_result
