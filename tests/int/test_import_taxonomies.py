import glob

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
    # assert synonyms files gets generated
    assert sorted(glob.glob("/opt/search/synonyms/*/*")) == [
        "/opt/search/synonyms/categories/en.txt",
        "/opt/search/synonyms/categories/fr.txt",
        "/opt/search/synonyms/categories/main.txt",
        "/opt/search/synonyms/labels/en.txt",
        "/opt/search/synonyms/labels/fr.txt",
        "/opt/search/synonyms/labels/main.txt",
    ]
    # with right format
    assert (
        "beverages with added sugar,sugared beverages,sweetened beverages => en:sweetened-beverages\n"
        in open("/opt/search/synonyms/categories/en.txt")
    )
