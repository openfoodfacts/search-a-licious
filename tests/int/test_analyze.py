"""Some tests on analyzer

Those are placed as integration test because we want to test against Elasticsearch
from the analyzers built by search-a-licious

For explanations on what we our testing here,
see https://openfoodfacts.github.io/search-a-licious/users/explain-taxonomies
"""

import unittest.mock

import pytest

from app.utils.analyzers import (
    get_taxonomy_indexing_analyzer,
    get_taxonomy_search_analyzer,
)


def _tokens(result):
    return [part["token"] for part in result["tokens"]]


def test_taxonomy_indexing_analyzer(es_connection, data_ingester):
    # create the index, with synonyms
    data_ingester([])
    index_en = get_taxonomy_indexing_analyzer("labels", "en").to_dict()
    index_fr = get_taxonomy_indexing_analyzer("labels", "fr").to_dict()
    # no change for simple entries
    result = es_connection.indices.analyze(
        index="test_off",
        analyzer=index_en,
        text="en:organic",
    )
    assert _tokens(result) == ["en:organic"]

    # the hyphen is replaced by underscore
    result = es_connection.indices.analyze(
        index="test_off",
        analyzer=index_en,
        text="en:organic-farming_2",
    )
    assert _tokens(result) == ["en:organic_farming_2"]
    # whatever the language
    result = es_connection.indices.analyze(
        index="test_off",
        analyzer=index_fr,
        text="en:organic-farming_2",
    )
    assert _tokens(result) == ["en:organic_farming_2"]


def test_taxonomy_search_analyzer_with_synonyms(
    es_connection, index_config, data_ingester
):
    # create the index, with synonyms
    data_ingester([])
    search_en = get_taxonomy_search_analyzer(
        index_config, "labels", "en", True
    ).to_dict()
    search_fr = get_taxonomy_search_analyzer(
        index_config, "labels", "fr", True
    ).to_dict()
    # bare term is not changed, but hyphen is replaced by underscore
    for analyzer in [search_en, search_fr]:
        result = es_connection.indices.analyze(
            index="test_off",
            analyzer=analyzer,
            text="en:organic-farming_2",
        )
        assert _tokens(result) == ["en:organic_farming_2"]

    # synonym is replaced by the synonym
    result = es_connection.indices.analyze(
        index="test_off",
        analyzer=search_en,
        text="organically grown plants",
    )
    assert "en:organic" in _tokens(result)
    # with hyphen to underscore
    result = es_connection.indices.analyze(
        index="test_off",
        analyzer=search_en,
        text="european leaf",
    )
    assert _tokens(result) == ["en:eu_organic"]
    # french synonyms
    result = es_connection.indices.analyze(
        index="test_off",
        analyzer=search_fr,
        text="feuille bio",
    )
    assert _tokens(result) == ["en:eu_organic"]
    # quote handling
    result = es_connection.indices.analyze(
        index="test_off",
        analyzer=search_fr,
        text="l'agriculture",
    )
    assert _tokens(result) == ["l", "agriculture"]
    result = es_connection.indices.analyze(
        index="test_off",
        analyzer=search_fr,
        text="issue de l'agriculture biologique",
    )
    assert _tokens(result) == ["en:organic"]


@pytest.mark.xfail(reason="Because of the way we create indexes it does not work yet")
def test_taxonomy_search_analyzer_without_synonyms(
    es_connection, index_config, data_ingester
):
    def get_taxonomy_search_analyzer_no_synonyms(
        config, taxonomy: str, lang: str, with_synonyms: bool
    ):
        return get_taxonomy_search_analyzer(
            config, taxonomy, lang, False
        )  # force no synonyms

    # mock get_taxonomy_search_analyzer
    patcher = unittest.mock.patch(
        "app.indexing.get_taxonomy_search_analyzer",
        new=get_taxonomy_search_analyzer_no_synonyms,
    )
    with patcher:
        # create the index, without synonyms
        data_ingester([])
    search_en = get_taxonomy_search_analyzer(
        index_config, "labels", "en", False
    ).to_dict()
    search_fr = get_taxonomy_search_analyzer(
        index_config, "labels", "fr", False
    ).to_dict()
    # bare term is not changed, but hyphen is replaced by underscore
    for analyzer in [search_en, search_fr]:
        result = es_connection.indices.analyze(
            index="test_off",
            analyzer=analyzer,
            text="en:organic-farming_2",
        )
        assert _tokens(result) == ["en:organic_farming_2"]

    # synonym is not replaced by the synonym
    result = es_connection.indices.analyze(
        index="test_off",
        analyzer=search_en,
        text="organically grown plants",
    )
    assert "en:organic" not in _tokens(result)
    # french synonyms
    result = es_connection.indices.analyze(
        index="test_off",
        analyzer=search_fr,
        text="feuille bio",
    )
    assert _tokens(result) == ["feuille", "bio"]


@pytest.mark.xfail(reason="No stop words support yet")
def test_taxonomy_search_analyzer_stopwords(index_config, es_connection, data_ingester):
    # create the index, with synonyms
    data_ingester([])
    search_fr = get_taxonomy_search_analyzer(
        index_config, "labels", "fr", True
    ).to_dict()

    # simple stop words taken into account
    result = es_connection.indices.analyze(
        index="test_off",
        analyzer=search_fr,
        # en ignored as well as "de l'" in target synonym
        text="issue en agriculture biologique",
    )
    assert _tokens(result) == ["en:eu_organic"]
