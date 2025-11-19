from tests.cli_utils import runner_invoke


def test_import_taxonomies(test_off_config, es_connection):
    result = runner_invoke("import-taxonomies")
    assert result.exit_code == 0
    assert "Import time" in result.stderr
    assert "Synonyms generation time" in result.stderr
    # assert we got the index with the right alias
    aliases = es_connection.indices.get_alias(index="test_off_taxonomy")
    assert len(aliases) == 1
    index_name = list(aliases.keys())[0]
    assert index_name.startswith("test_off_taxonomy-")
    assert aliases[index_name]["aliases"] == {"test_off_taxonomy": {}}
    # and the right number of entries, 33 categories and 20 labels
    assert es_connection.count(index="test_off_taxonomy")["count"] == 20 + 33
    # assert synonyms sets where created with the right number of items
    result = es_connection.synonyms.get_synonyms_sets(size=1000)
    assert result["count"] == 6
    assert sorted((r["synonyms_set"], r["count"]) for r in result["results"]) == [
        ("test_off-categories-en-0", 33),
        ("test_off-categories-fr-0", 33),
        ("test_off-categories-main-0", 33),
        ("test_off-labels-en-0", 20),
        ("test_off-labels-fr-0", 20),
        ("test_off-labels-main-0", 20),
    ]
    # with right format
    result = es_connection.synonyms.get_synonym_rule(
        set_id="test_off-categories-en-0", rule_id="en:sweetened-beverages"
    )
    assert result["synonyms"] == (
        "beverages with added sugar,sugared beverages,sweetened beverages => en:sweetened-beverages"
    )
