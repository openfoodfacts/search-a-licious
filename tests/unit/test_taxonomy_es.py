import cachetools
import elastic_transport
import pytest

from app import search, taxonomy_es
from app.taxonomy_es import get_taxonomy_names

CHOCOLATES = ("en:chocolates", "categories")
MILK = ("en:milk", "categories")
NO_PREFIX = ("milk", "categories")
UNKNOWN = ("xx:unknown-brand", "brands")
ITEMS = [CHOCOLATES, MILK]

NAMES = {CHOCOLATES: {"en": "Chocolates"}, MILK: {"en": "Milk"}}


class FakeFetch:
    """Replaces the search in the taxonomy index, and records what was asked"""

    def __init__(self):
        self.searches = []
        self.fail_with = None
        # called while "Elasticsearch is searching"
        self.meanwhile = None

    def __call__(self, items, config):
        self.searches.append(list(items))
        if self.meanwhile:
            self.meanwhile()
        if self.fail_with:
            raise self.fail_with
        return {item: NAMES[item] for item in items if item in NAMES}


@pytest.fixture
def fetch(monkeypatch):
    fake = FakeFetch()
    monkeypatch.setattr(taxonomy_es, "_fetch_taxonomy_names", fake)
    return fake


def test_names_are_not_searched_again(default_config, fetch):
    items = ITEMS + [UNKNOWN]
    for _ in range(2):
        assert get_taxonomy_names(items, default_config) == NAMES
    # one search for both calls, the unknown item included
    assert fetch.searches == [items]


def test_only_the_missing_names_are_searched(default_config, fetch):
    get_taxonomy_names([CHOCOLATES], default_config)
    assert get_taxonomy_names(ITEMS, default_config) == NAMES
    assert fetch.searches == [[CHOCOLATES], [MILK]]


def test_failed_lookup_is_not_cached(default_config, fetch):
    fetch.fail_with = elastic_transport.ConnectionTimeout("timeout")
    with pytest.raises(elastic_transport.ConnectionTimeout):
        get_taxonomy_names(ITEMS, default_config)
    fetch.fail_with = None
    assert get_taxonomy_names(ITEMS, default_config) == NAMES
    assert fetch.searches == [ITEMS, ITEMS]


def test_absence_is_not_cached_next_to_an_id_without_language_prefix(
    default_config, fetch
):
    """Such an id matches many entries, which can leave another item out"""
    items = [NO_PREFIX, UNKNOWN]
    get_taxonomy_names(items, default_config)
    get_taxonomy_names(items, default_config)
    assert fetch.searches == [items, items]


def test_names_expire(default_config, fetch, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(
        taxonomy_es,
        "_NAMES_CACHE",
        cachetools.TTLCache(maxsize=100, ttl=3600, timer=lambda: now[0]),
    )
    get_taxonomy_names(ITEMS, default_config)
    now[0] += 3599
    get_taxonomy_names(ITEMS, default_config)
    assert len(fetch.searches) == 1
    now[0] += 2
    get_taxonomy_names(ITEMS, default_config)
    assert len(fetch.searches) == 2


def test_names_are_kept_per_taxonomy_index(default_config, fetch):
    get_taxonomy_names(ITEMS, default_config)
    other = default_config.model_copy(deep=True)
    other.taxonomy.index.name = "another_taxonomy"
    get_taxonomy_names(ITEMS, other)
    assert len(fetch.searches) == 2


def test_invalidating_the_runtime_caches_clears_the_names(default_config, fetch):
    get_taxonomy_names(ITEMS, default_config)
    search.invalidate_runtime_caches()
    get_taxonomy_names(ITEMS, default_config)
    assert len(fetch.searches) == 2


def test_lookup_started_before_a_clear_does_not_fill_the_cache(default_config, fetch):
    """What it found may be outdated: it is returned, but not kept"""
    fetch.meanwhile = taxonomy_es.clear_taxonomy_names_cache
    assert get_taxonomy_names(ITEMS, default_config) == NAMES
    fetch.meanwhile = None
    get_taxonomy_names(ITEMS, default_config)
    assert len(fetch.searches) == 2
