import hashlib
import json
import tempfile

import factory

from app._import import (
    get_alias,
    perform_refresh_synonyms,
    perform_taxonomy_import,
    run_items_import,
    update_alias,
)


class Nutriments(factory.DictFactory):
    fat_100g = 0
    energy_kcal_100g = 400
    proteins_100g = 0
    saturated_fat_100g = 0
    salt_100g = 0
    carbohydrates_100g = 100
    sugars_100g = 100
    sodium_100g = 0

    class Meta:
        # Ensure dict field uses hyphens not underscores.
        rename = {
            "energy_kcal_100g": "energy-kcal_100g",
            "saturated_fat_100g": "saturated-fat_100g",
        }


class Product(factory.DictFactory):
    code = factory.Sequence(lambda n: f"30123457{n:05d}")
    categories_tags = ["en:sweeteners", "en:sugars", "en:granulated-sugars"]
    labels_tags = ["en:no-lactose"]
    unique_scans_n = 15
    nova_groups = "2"
    last_modified_t = 1700525044
    created_t = 1537090000
    completeness = 0.5874999999999999
    product_name_en = "Granulated sugar"
    product_name_fr = "Sucre semoule"
    lc = "en"
    product_name = factory.LazyAttribute(
        lambda o: getattr(o, "product_name_" + getattr(o, "lc"))
    )
    nutriments = factory.SubFactory(Nutriments)


# we keep track of ingested,
# associating data to a sha256 hash with index name
INGESTED_DATA: dict[str, str] = {}


def ingest_data(data, index_name, index_config, es_connection, read_only=True):
    """Ingest test data into ES

    Try to re-use existing index if possible
    """
    data_sha256 = (
        index_name + hashlib.sha256(json.dumps(data).encode("utf-8")).hexdigest()
    )
    if data_sha256 not in INGESTED_DATA or not _index_exists(
        es_connection, INGESTED_DATA[data_sha256]
    ):
        # ingest data
        with tempfile.NamedTemporaryFile("w+t", suffix=".jsonl") as f:
            f.write("\n".join(json.dumps(d) for d in data))
            f.flush()
            num_errors = run_items_import(
                f.name,
                1,
                index_config,
                skip_updates=True,
                partial=False,
            )
            if num_errors:
                raise RuntimeError(f"{num_errors} errors while ingesting data")
        # remember the alias for later use
        INGESTED_DATA[data_sha256] = get_alias(es_connection, index_name)
    real_index = INGESTED_DATA[data_sha256]
    if not read_only:
        # clone the index because we will modify it
        es_connection.indices.clone(
            source=real_index,
            target=real_index + "-clone",
            wait_for_completion=True,
        )
        real_index = real_index + "-clone"
    # now just update the alias to point to the known index
    update_alias(es_connection, real_index, index_name)
    return real_index


INGESTED_TAXONOMY: dict[str, str] = {}


def _index_exists(es_connection, name):
    return es_connection.indices.exists(index=name)


def ingest_taxonomies(index_id, index_config, es_connection):
    """Ingest taxonomies into ES"""
    if index_id not in INGESTED_TAXONOMY or not _index_exists(
        es_connection, INGESTED_TAXONOMY[index_id]
    ):
        perform_taxonomy_import(index_config)
        perform_refresh_synonyms(
            index_id,
            index_config,
        )
        INGESTED_TAXONOMY[index_id] = get_alias(
            es_connection, index_config.taxonomy.index.name
        )
    else:
        # just update the alias to point to the good index
        update_alias(
            es_connection, INGESTED_TAXONOMY[index_id], index_config.taxonomy.index.name
        )


def save_state(index_id, index_config, es_connection):
    """Save state in a particular index in ES,
    so that even between test run, we minimize the number of ingestion
    """
    es_connection.index(
        index="test-" + index_id,
        id="state",
        document={
            "ingested_taxonomies": INGESTED_TAXONOMY,
            "ingested_data": INGESTED_DATA,
        },
    )


def load_state(index_id, index_config, es_connection):
    state_idx = "test-" + index_id
    if es_connection.exists(index=state_idx, id="state"):
        state = es_connection.get(index=state_idx, id="state")["_source"]
        INGESTED_DATA.update(state["ingested_data"])
        INGESTED_TAXONOMY.update(state["ingested_taxonomies"])


def delete_es_indices(es_connection):
    """Do a full cleanup of ES, including deleting all indexes"""
    for index in es_connection.indices.get(index="*", expand_wildcards="all"):
        if index.startswith(".") and not index.startswith("test-"):
            # skip special indexes
            continue
        es_connection.indices.delete(index=index)
