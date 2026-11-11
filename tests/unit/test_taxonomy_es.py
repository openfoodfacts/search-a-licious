import cachetools
import elastic_transport
import pytest

from app import search, taxonomy_es
from app.taxonomy_es import get_taxonomy_names

CHOCOLATES = ("en:chocolates", "categories")
MILK = ("en:milk", "categories")
ITEMS = [CHOCOLATES, MILK]

KNOWN = {
    CHOCOLATES: {"en": "Chocolates", "fr": "Chocolats"},
    MILK: {"en": "Milk"},
    # an id asked without language prefix, found with the entry of a language
    ("milk", "categories"): {"en": "Milk"},
}


class FakeFetch:
    """A stand-in for the search in the taxonomy index.

    It records the items that were searched for, in each search.
    """

    def __init__(self):
        self.searches: list[list[tuple[str, str]]] = []
        self.fail_with: Exception | None = None

    def __call__(self, items, config):
        self.searches.append(list(items))
        if self.fail_with is not None:
            raise self.fail_with
        return {item: KNOWN[item] for item in items if item in KNOWN}


@pytest.fixture
def fetch(monkeypatch):
    fake = FakeFetch()
    monkeypatch.setattr(taxonomy_es, "_fetch_taxonomy_names", fake)
    return fake


def test_names_are_found(default_config, fetch):
    assert get_taxonomy_names(ITEMS, default_config) == {
        CHOCOLATES: KNOWN[CHOCOLATES],
        MILK: KNOWN[MILK],
    }
    assert fetch.searches == [ITEMS]


def test_names_are_not_searched_again(default_config, fetch):
    first = get_taxonomy_names(ITEMS, default_config)
    second = get_taxonomy_names(ITEMS, default_config)
    assert second == first
    # one search for both calls
    assert fetch.searches == [ITEMS]


def test_only_the_missing_names_are_searched(default_config, fetch):
    get_taxonomy_names([CHOCOLATES], default_config)
    names = get_taxonomy_names(ITEMS, default_config)
    assert set(names) == set(ITEMS)
    # the second search is only for the value not seen before
    assert fetch.searches == [[CHOCOLATES], [MILK]]


def test_repeated_items_are_searched_once(default_config, fetch):
    get_taxonomy_names(ITEMS + ITEMS, default_config)
    assert fetch.searches == [ITEMS]


def test_id_without_language_prefix_is_cached_as_asked(default_config, fetch):
    items = [("milk", "categories")]
    expected = {("milk", "categories"): {"en": "Milk"}}
    assert get_taxonomy_names(items, default_config) == expected
    assert get_taxonomy_names(items, default_config) == expected
    assert fetch.searches == [items]


def test_unknown_names_are_not_searched_again(default_config, fetch):
    """Many brands are in no taxonomy: searching for them each time is a waste"""
    items = [("xx:unknown-brand", "brands")]
    assert get_taxonomy_names(items, default_config) == {}
    assert get_taxonomy_names(items, default_config) == {}
    assert fetch.searches == [items]


def test_failed_lookup_is_not_cached(default_config, fetch):
    fetch.fail_with = elastic_transport.ConnectionTimeout("timeout")
    with pytest.raises(elastic_transport.ConnectionTimeout):
        get_taxonomy_names(ITEMS, default_config)
    # Elasticsearch is back: the names are searched for again
    fetch.fail_with = None
    assert set(get_taxonomy_names(ITEMS, default_config)) == set(ITEMS)
    assert fetch.searches == [ITEMS, ITEMS]


def test_names_expire(default_config, fetch, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(
        taxonomy_es,
        "_NAMES_CACHE",
        cachetools.TTLCache(maxsize=100, ttl=600, timer=lambda: now[0]),
    )
    get_taxonomy_names(ITEMS, default_config)
    now[0] += 599
    get_taxonomy_names(ITEMS, default_config)
    assert fetch.searches == [ITEMS]
    # the taxonomies may have been imported again by now
    now[0] += 2
    get_taxonomy_names(ITEMS, default_config)
    assert fetch.searches == [ITEMS, ITEMS]


def test_cache_is_bounded(default_config, fetch, monkeypatch):
    monkeypatch.setattr(
        taxonomy_es, "_NAMES_CACHE", cachetools.TTLCache(maxsize=2, ttl=600)
    )
    for i in range(5):
        get_taxonomy_names([(f"xx:brand-{i}", "brands")], default_config)
    assert len(taxonomy_es._NAMES_CACHE) == 2


def test_cache_is_kept_per_taxonomy_index(default_config, fetch):
    get_taxonomy_names(ITEMS, default_config)
    other = default_config.model_copy(deep=True)
    other.taxonomy.index.name = "another_taxonomy"
    get_taxonomy_names(ITEMS, other)
    assert fetch.searches == [ITEMS, ITEMS]


def test_runtime_cache_invalidation_clears_names(default_config, fetch):
    get_taxonomy_names(ITEMS, default_config)
    search.invalidate_runtime_caches()
    get_taxonomy_names(ITEMS, default_config)
    assert fetch.searches == [ITEMS, ITEMS]
