import pytest

from app import es_scripts
from app.config import ScriptConfig, ScriptType

INDEX_ID = "test_off"
PREFIX = es_scripts.get_script_prefix(INDEX_ID)


def _config(index_config, **sources):
    return index_config.model_copy(
        update={
            "scripts": {
                name: ScriptConfig(
                    lang=ScriptType.painless,
                    source=source,
                    params=None,
                    static_params=None,
                )
                for name, source in sources.items()
            }
        }
    )


def _stored_ids(es) -> set[str]:
    scripts = es.cluster.state(metric="metadata")["metadata"].get("stored_scripts")
    return {id_ for id_ in (scripts or {}) if id_.startswith(PREFIX)}


def _source(es, name: str) -> str:
    return es.get_script(id=es_scripts.get_script_id(INDEX_ID, name))["script"][
        "source"
    ]


@pytest.fixture(autouse=True)
def no_script(es_connection):
    """Start and end without the scripts of this test index"""
    for id_ in _stored_ids(es_connection):
        es_connection.delete_script(id=id_)
    yield
    for id_ in _stored_ids(es_connection):
        es_connection.delete_script(id=id_)


def test_sync_scripts_stores_replaces_and_removes(index_config, es_connection):
    stats = es_scripts.sync_scripts(
        INDEX_ID, _config(index_config, a="return 1.0;", b="return 2.0;")
    )
    assert stats == {"removed": 0, "added": 2}
    assert _source(es_connection, "a") == "return 1.0;"

    # a is changed, b is no longer configured, c is new
    stats = es_scripts.sync_scripts(
        INDEX_ID, _config(index_config, a="return 3.0;", c="return 4.0;")
    )
    assert stats == {"removed": 1, "added": 2}
    assert _source(es_connection, "a") == "return 3.0;"
    assert _stored_ids(es_connection) == {PREFIX + "a", PREFIX + "c"}

    # nothing changes the second time
    stats = es_scripts.sync_scripts(
        INDEX_ID, _config(index_config, a="return 3.0;", c="return 4.0;")
    )
    assert stats == {"removed": 0, "added": 2}


def test_sync_scripts_keeps_the_previous_version_of_a_rejected_script(
    index_config, es_connection
):
    """It used to delete the working script before trying to store the new one"""
    es_scripts.sync_scripts(INDEX_ID, _config(index_config, a="return 1.0;"))
    # Elasticsearch refuses this one (it does not compile)
    stats = es_scripts.sync_scripts(INDEX_ID, _config(index_config, a="return (;"))
    assert stats == {"removed": 0, "added": 0}
    assert _source(es_connection, "a") == "return 1.0;"
