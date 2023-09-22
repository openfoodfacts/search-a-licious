import pytest
from luqum.elasticsearch import ElasticsearchQueryBuilder
from luqum.parser import parser

from app.query import UnknownOperationRemover, parse_lucene_dsl_query
from app.types import JSONType


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
    ],
)
def test_parse_lucene_dsl_query(
    q: str, expected_filter_clauses: list[JSONType], expected_remaining_terms: str
):
    query_builder = ElasticsearchQueryBuilder(
        default_operator=ElasticsearchQueryBuilder.MUST,
        not_analyzed_fields=["states_tags", "labels_tags"],
    )
    filter_clauses, remaining_terms = parse_lucene_dsl_query(q, query_builder)
    assert filter_clauses == expected_filter_clauses
    assert remaining_terms == expected_remaining_terms
