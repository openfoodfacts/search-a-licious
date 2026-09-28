from types import SimpleNamespace

import app.search as search


def test_query_builder_cache_invalidation_on_config_change(monkeypatch):
    config_holder = {
        "config": SimpleNamespace(indices={"off": "index_config_v1"})
    }
    builder_calls: list[str] = []

    monkeypatch.setattr(search.config, "get_config", lambda: config_holder["config"])

    def fake_builder(index_config):
        builder_calls.append(index_config)
        return f"builder:{index_config}"

    monkeypatch.setattr(search, "build_elasticsearch_query_builder", fake_builder)

    search.invalidate_runtime_caches()

    first_builder = search.get_es_query_builder("off")
    second_builder = search.get_es_query_builder("off")

    assert first_builder == "builder:index_config_v1"
    assert second_builder == first_builder
    assert builder_calls == ["index_config_v1"]

    config_holder["config"] = SimpleNamespace(indices={"off": "index_config_v2"})
    third_builder = search.get_es_query_builder("off")

    assert third_builder == "builder:index_config_v2"
    assert builder_calls == ["index_config_v1", "index_config_v2"]


def test_result_processor_cache_invalidation_on_config_change(monkeypatch):
    config_holder = {
        "config": SimpleNamespace(indices={"off": "index_config_v1"})
    }
    processor_calls: list[str] = []

    monkeypatch.setattr(search.config, "get_config", lambda: config_holder["config"])

    def fake_processor_loader(index_config):
        processor_calls.append(index_config)
        return f"processor:{index_config}"

    monkeypatch.setattr(search, "load_result_processor", fake_processor_loader)

    search.invalidate_runtime_caches()

    first_processor = search.get_result_processor("off")
    second_processor = search.get_result_processor("off")

    assert first_processor == "processor:index_config_v1"
    assert second_processor == first_processor
    assert processor_calls == ["index_config_v1"]

    config_holder["config"] = SimpleNamespace(indices={"off": "index_config_v2"})
    third_processor = search.get_result_processor("off")

    assert third_processor == "processor:index_config_v2"
    assert processor_calls == ["index_config_v1", "index_config_v2"]