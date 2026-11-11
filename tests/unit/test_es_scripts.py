from unittest import mock

import elasticsearch
import pytest

from app import es_scripts
from app.config import ScriptConfig, ScriptType


class FakeElasticsearch:
    """The scripts of an Elasticsearch, and what was done with them"""

    def __init__(self, stored: dict[str, str]):
        self.stored = dict(stored)  # id => source
        self.calls: list[tuple[str, str]] = []  # ("put" or "delete", id)
        self.reject: set[str] = set()  # ids that Elasticsearch refuses to store
        self.cluster = mock.Mock()
        self.cluster.state.side_effect = lambda metric: {
            "metadata": {"stored_scripts": dict(self.stored)}
        }

    def put_script(self, id, script, context):
        self.calls.append(("put", id))
        if id in self.reject:
            raise elasticsearch.ApiError("bad script", mock.MagicMock(status=400), {})
        self.stored[id] = script["source"]

    def delete_script(self, id):
        self.calls.append(("delete", id))
        del self.stored[id]


def _script(source: str) -> ScriptConfig:
    return ScriptConfig(
        lang=ScriptType.painless, source=source, params=None, static_params=None
    )


@pytest.fixture
def es(monkeypatch):
    def use(stored: dict[str, str]) -> FakeElasticsearch:
        fake = FakeElasticsearch(stored)
        monkeypatch.setattr(es_scripts.connection, "current_es_client", lambda: fake)
        return fake

    return use


def _config(default_config, **scripts):
    return default_config.model_copy(
        update={"scripts": {k: _script(v) for k, v in scripts.items()}}
    )


def test_scripts_are_stored(default_config, es):
    fake = es({})
    stats = es_scripts.sync_scripts("off", _config(default_config, a="1", b="2"))
    assert fake.stored == {"off__a": "1", "off__b": "2"}
    assert stats == {"removed": 0, "added": 2}


def test_a_configured_script_is_never_deleted(default_config, es):
    """It used to be deleted then stored again, at each synchronisation"""
    fake = es({"off__a": "old"})
    stats = es_scripts.sync_scripts("off", _config(default_config, a="new"))
    assert fake.stored == {"off__a": "new"}
    assert fake.calls == [("put", "off__a")]
    assert stats == {"removed": 0, "added": 1}


def test_scripts_no_longer_configured_are_removed_after_the_others_are_stored(
    default_config, es
):
    fake = es({"off__old": "x", "off__a": "old"})
    stats = es_scripts.sync_scripts("off", _config(default_config, a="new", b="2"))
    assert fake.stored == {"off__a": "new", "off__b": "2"}
    assert stats == {"removed": 1, "added": 2}
    # the removal comes last
    assert fake.calls[-1] == ("delete", "off__old")
    assert [c for c in fake.calls if c[0] == "put"] == [
        ("put", "off__a"),
        ("put", "off__b"),
    ]


def test_a_script_that_cannot_be_stored_keeps_its_previous_version(
    default_config, es, caplog
):
    fake = es({"off__a": "working"})
    fake.reject = {"off__a"}
    stats = es_scripts.sync_scripts("off", _config(default_config, a="broken"))
    assert fake.stored == {"off__a": "working"}
    assert ("delete", "off__a") not in fake.calls
    assert stats == {"removed": 0, "added": 0}
    assert "Unable to store script a" in caplog.text


def test_scripts_of_other_indexes_are_not_touched(default_config, es):
    fake = es({"other__a": "x"})
    es_scripts.sync_scripts("off", _config(default_config, a="1"))
    # only the prefix of the index is listed by `_list_stored_scripts`
    assert fake.stored["other__a"] == "x"


def test_no_script_configured_removes_the_stored_ones(default_config, es):
    fake = es({"off__a": "1", "off__b": "2"})
    stats = es_scripts.sync_scripts(
        "off", default_config.model_copy(update={"scripts": None})
    )
    assert fake.stored == {}
    assert stats == {"removed": 2, "added": 0}
