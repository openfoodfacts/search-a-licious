"""Natural-language query corpus.

Whatever users type, the query pipeline must either build a query or raise a
`QueryAnalysisError` (HTTP 400), never an unexpected exception (HTTP 500).
Common queries must also be accepted.
"""

import pytest

from app._types import SearchParameters
from app.exceptions import QueryAnalysisError
from app.query import build_search_query

# queries a user can reasonably type, they must give a search
ACCEPTED = [
    "milk",
    "chocolate milk",
    "café",
    "Nestlé",
    "pâté de campagne",
    "L'Oréal",
    "o'neil",
    "what's up",
    "3017620422003",
    "50cl",
    "100% juice",
    "chocolat noir 70%",
    "coca cola 33cl",
    "ben & jerry's",
    "yogurt, natural",
    "fruit (apple)",
    "e150d",
    '"organic milk"',
    "milk AND chocolate",
    "milk OR cheese",
    "milk -sugar",
    "mil*",
    "milk?",
    "milk^2",
    "!milk",
    "-sugar",
    "NOT milk",
]

# queries that should work but are rejected today (HTTP 400), see #253
XFAIL_REJECTED = [
    "coca-cola",
    "sugar-free",
    "7-up",
    "non-gmo",
    "bio/organic",
    "lait demi-écrémé",
    "c++",
]

# queries that are legitimately rejected with a clear error
REJECTED = ["(milk", "milk)", "~milk", '"', "milk:", "*", "a:b:c"]


def _build(q: str, default_filter_query_builder):
    return build_search_query(
        SearchParameters(q=q, langs=["en"], page_size=5, page=1),
        es_query_builder=default_filter_query_builder,
    )


@pytest.mark.parametrize("q", ACCEPTED)
def test_common_queries_are_accepted(q, default_filter_query_builder):
    assert _build(q, default_filter_query_builder).es_query is not None


@pytest.mark.parametrize("q", XFAIL_REJECTED)
@pytest.mark.xfail(
    reason="rejected by the query checker, see #253", raises=QueryAnalysisError
)
def test_hyphenated_and_slashed_queries(q, default_filter_query_builder):
    assert _build(q, default_filter_query_builder).es_query is not None


@pytest.mark.parametrize("q", REJECTED)
def test_invalid_queries_give_a_query_error(q, default_filter_query_builder):
    with pytest.raises(QueryAnalysisError):
        _build(q, default_filter_query_builder)
