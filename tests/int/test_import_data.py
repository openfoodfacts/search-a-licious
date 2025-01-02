from tests.cli_utils import runner_invoke
from tests.int import helpers


def test_import_data(test_off_config, es_connection, synonyms_created):
    helpers.TestDocumentFetcher.clean_calls()
    helpers.TestDocumentPreprocessor.clean_calls()
    # Important note: we use multiprocessing which is not compatible with pytest logging
    # So you may loose information about errors
    result = runner_invoke(
        "import", "/opt/search/tests/int/data/test_off_data.jsonl", "--skip-updates"
    )
    assert result.exit_code == 0
    assert "Import time" in result.stderr
    # no fetch
    fetcher_calls = helpers.TestDocumentFetcher.get_calls()
    assert len(fetcher_calls) == 0
    # pre-processor was called for each document
    pre_processor_calls = helpers.TestDocumentPreprocessor.get_calls()
    assert len(pre_processor_calls) == 9
    assert set(item["code"] for item in pre_processor_calls) == set(
        f"3012345767890{i}" for i in range(1, 10)
    )
    # assert we got the index with the right alias
    aliases = es_connection.indices.get_alias(index="test_off")
    assert len(aliases) == 1
    index_name = list(aliases.keys())[0]
    assert index_name.startswith("test_off-")
    assert aliases[index_name]["aliases"] == {"test_off": {}}
    # and the right number of entries
    assert es_connection.count(index="test_off")["count"] == 9
    # test on one entry
    document = es_connection.get(index="test_off", id="30123457678901")["_source"]
    last_index_1 = document.pop("last_indexed_datetime")
    assert last_index_1
    assert document == {
        "code": "30123457678901",
        "product_name": {
            "main": "Granulated sugar",
            "en": "Granulated sugar",
            "fr": "Sucre semoule",
        },
        "categories": ["en:sweeteners", "en:sugars", "en:granulated-sugars"],
        "labels": ["en:no-lactose"],
        "unique_scans_n": 15,
        "nova_groups": "2",
        "last_modified_t": 1700525044,
        "created_t": 1537090000,
        "nutriments": {
            "fat_100g": 0.0,
            "energy-kcal_100g": 400.0,
            "proteins_100g": 0.0,
            "saturated-fat_100g": 0.0,
            "salt_100g": 0.0,
            "carbohydrates_100g": 100.0,
            "sugars_100g": 100.0,
            "sodium_100g": 0.0,
        },
        "completeness": 0.5874999999999999,
    }

    # we now import data again, to verify it creates a new index
    old_index_name = index_name
    result = runner_invoke(
        "import", "/opt/search/tests/int/data/test_off_data.jsonl", "--skip-updates"
    )
    assert result.exit_code == 0
    # assert we got the index with the right alias
    aliases = es_connection.indices.get_alias(index="test_off")
    assert len(aliases) == 1
    index_name = list(aliases.keys())[0]
    assert index_name != old_index_name
    # entries are there
    assert es_connection.count(index="test_off")["count"] == 9

    # test in place update
    helpers.TestDocumentPreprocessor.clean_calls()
    old_index_name = index_name
    result = runner_invoke(
        "import",
        "/opt/search/tests/int/data/test_off_data_update.jsonl",
        "--partial",
        "--skip-updates",
    )
    assert result.exit_code == 0
    assert "Import time" in result.stderr
    # pre-processor was called for each document
    pre_processor_calls = helpers.TestDocumentPreprocessor.get_calls()
    assert len(pre_processor_calls) == 2
    # alias is still the same
    aliases = es_connection.indices.get_alias(index="test_off")
    assert len(aliases) == 1
    index_name = list(aliases.keys())[0]
    assert index_name == old_index_name
    # old and new entries are there
    assert es_connection.count(index="test_off")["count"] == 10
    # test our modified one entry
    document = es_connection.get(index="test_off", id="30123457678901")["_source"]
    assert document.pop("last_indexed_datetime") > last_index_1
    assert document == {
        "code": "30123457678901",
        "product_name": {
            "main": "Granulated sugar 2",
            "en": "Granulated sugar 2",
            "fr": "Sucre semoule 2",
        },
        "categories": ["en:sweeteners", "en:sugars"],
        "unique_scans_n": 18,
        "nova_groups": "2",
        "last_modified_t": 1700545044,
        "created_t": 1537090000,
        "nutriments": {
            "fat_100g": 0.0,
            "energy-kcal_100g": 400.0,
            "proteins_100g": 0.0,
            "saturated-fat_100g": 0.0,
            "salt_100g": 0.1,
            "carbohydrates_100g": 100.0,
            "sugars_100g": 100.0,
            "sodium_100g": 0.001,
        },
        "completeness": 0.5874999999999999,
    }
    # our new document is there
    assert es_connection.get(index="test_off", id="30123457678910")["_source"]


def test_cleanup_indexes(test_off_config, es_connection):
    # clean ES first
    for index_name in es_connection.indices.get(index="*").keys():
        es_connection.indices.delete(index=index_name)
    # create some indices corresponding to test_off, with last aliased
    es_connection.indices.create(index="test_off-2024-05-25")
    es_connection.indices.create(index="test_off-2024-06-25")
    es_connection.indices.create(index="test_off-2024-07-25", aliases={"test_off": {}})
    # same for taxonomies
    es_connection.indices.create(index="test_off_taxonomy-2024-05-25")
    es_connection.indices.create(index="test_off_taxonomy-2024-06-25")
    es_connection.indices.create(
        index="test_off_taxonomy-2024-07-25", aliases={"test_off_taxonomy": {}}
    )
    # and some unrelated indexes
    es_connection.indices.create(index="something-else-2024-05-25")
    es_connection.indices.create(
        index="something-else-2024-07-25", aliases={"something-else": {}}
    )

    # run the cleanup
    result = runner_invoke("cleanup-indexes")
    assert result.exit_code == 0
    # assert we got the index with the right alias, and other indexes untouched
    aliases = es_connection.indices.get_alias(index="*")
    assert dict(aliases) == {
        # only aliases where kept
        "test_off_taxonomy-2024-07-25": {"aliases": {"test_off_taxonomy": {}}},
        "test_off-2024-07-25": {"aliases": {"test_off": {}}},
        # other untouched
        "something-else-2024-05-25": {"aliases": {}},
        "something-else-2024-07-25": {"aliases": {"something-else": {}}},
    }
