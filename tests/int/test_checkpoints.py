"""Integration tests of the checkpoint helpers against a real Elasticsearch."""

import pytest

from app.checkpoints import get_last_indexed_timestamp_ms

LAST_MODIFIED_FIELD = "last_modified_t"
INDEX_NAME = "test-last-indexed-timestamp"


@pytest.fixture
def timestamp_index(es_connection):
    """Create a small index storing last modification dates, and clean it up"""
    es_connection.indices.delete(index=INDEX_NAME, ignore_unavailable=True)
    es_connection.indices.create(
        index=INDEX_NAME,
        mappings={"properties": {LAST_MODIFIED_FIELD: {"type": "date"}}},
    )
    yield INDEX_NAME
    es_connection.indices.delete(index=INDEX_NAME, ignore_unavailable=True)


def _index_documents(es_connection, documents: list[dict]) -> None:
    for i, document in enumerate(documents):
        es_connection.index(index=INDEX_NAME, id=str(i), document=document)
    es_connection.indices.refresh(index=INDEX_NAME)


def test_get_last_indexed_timestamp_ms_empty_index(es_connection, timestamp_index):
    """An empty index has no timestamp"""
    assert (
        get_last_indexed_timestamp_ms(
            es_connection, timestamp_index, LAST_MODIFIED_FIELD
        )
        is None
    )


def test_get_last_indexed_timestamp_ms_returns_newest_document(
    es_connection, timestamp_index
):
    """The newest date is returned, in milliseconds"""
    _index_documents(
        es_connection,
        [
            {LAST_MODIFIED_FIELD: 1600000000},
            {LAST_MODIFIED_FIELD: 1700525044},
            {LAST_MODIFIED_FIELD: 1682531455},
        ],
    )

    assert (
        get_last_indexed_timestamp_ms(
            es_connection, timestamp_index, LAST_MODIFIED_FIELD
        )
        == 1700525044000
    )


def test_get_last_indexed_timestamp_ms_ignores_dates_in_the_future(
    es_connection, timestamp_index
):
    """An erroneous future date must not be used as the catch-up position"""
    _index_documents(
        es_connection,
        [
            {LAST_MODIFIED_FIELD: 1700525044},
            # in the future: the newest date, but it must be ignored
            {LAST_MODIFIED_FIELD: "2999-01-01T00:00:00Z"},
            {LAST_MODIFIED_FIELD: 1682531455},
        ],
    )

    assert (
        get_last_indexed_timestamp_ms(
            es_connection, timestamp_index, LAST_MODIFIED_FIELD
        )
        == 1700525044000
    )


def test_get_last_indexed_timestamp_ms_only_future_dates(
    es_connection, timestamp_index
):
    """An index with only future dates is considered empty"""
    _index_documents(
        es_connection,
        [
            {LAST_MODIFIED_FIELD: "2999-01-01T00:00:00Z"},
            {LAST_MODIFIED_FIELD: "2998-01-01T00:00:00Z"},
        ],
    )

    assert (
        get_last_indexed_timestamp_ms(
            es_connection, timestamp_index, LAST_MODIFIED_FIELD
        )
        is None
    )


def test_get_last_indexed_timestamp_ms_ignores_documents_without_date(
    es_connection, timestamp_index
):
    """Documents without the date field are not taken into account"""
    _index_documents(
        es_connection,
        [
            {"code": "no-date"},
            {LAST_MODIFIED_FIELD: 1600000000},
        ],
    )

    assert (
        get_last_indexed_timestamp_ms(
            es_connection, timestamp_index, LAST_MODIFIED_FIELD
        )
        == 1600000000000
    )
