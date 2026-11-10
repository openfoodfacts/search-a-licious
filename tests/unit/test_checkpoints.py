from unittest.mock import MagicMock, patch

from app.checkpoints import (
    checkpoint_key,
    get_checkpoint,
    get_last_indexed_timestamp_ms,
    set_checkpoint,
    stream_id_from_timestamp_ms,
)


def test_checkpoint_key_includes_stream_and_index():
    """The key is scoped by both the stream and the index (alias)"""
    assert (
        checkpoint_key("product_updates_off", "off")
        == "searchalicious:checkpoint:product_updates_off:off"
    )
    # the same stream consumed for another index has its own checkpoint
    assert (
        checkpoint_key("product_updates_off", "off-staging")
        == "searchalicious:checkpoint:product_updates_off:off-staging"
    )


def test_get_checkpoint_returns_none_when_absent():
    redis_client = MagicMock()
    redis_client.get.return_value = None
    assert get_checkpoint(redis_client, "stream", "off") is None
    redis_client.get.assert_called_once_with("searchalicious:checkpoint:stream:off")


def test_set_checkpoint():
    redis_client = MagicMock()
    set_checkpoint(redis_client, "stream", "off", "1629878400000-0")
    redis_client.set.assert_called_once_with(
        "searchalicious:checkpoint:stream:off", "1629878400000-0"
    )


def test_get_last_indexed_timestamp_ms():
    """The timestamp of the newest document is returned in milliseconds"""
    search_result = MagicMock()
    search_result.to_dict.return_value = {"last_modified": 1629878400.123}

    with patch("app.checkpoints.Search") as search:
        search.return_value.sort.return_value.extra.return_value.execute.return_value = [
            search_result
        ]
        timestamp_ms = get_last_indexed_timestamp_ms(
            MagicMock(), "off", "last_modified"
        )

    assert timestamp_ms == 1629878400123


def test_get_last_indexed_timestamp_ms_empty_index():
    """An empty index has no timestamp"""
    with patch("app.checkpoints.Search") as search:
        search.return_value.sort.return_value.extra.return_value.execute.return_value = (
            []
        )
        assert (
            get_last_indexed_timestamp_ms(MagicMock(), "off", "last_modified") is None
        )


def test_stream_id_from_timestamp_ms():
    """We start at sequence 0, so events of the same millisecond are replayed"""
    assert stream_id_from_timestamp_ms(1629878400123) == "1629878400123-0"
