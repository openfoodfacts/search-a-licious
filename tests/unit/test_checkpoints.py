from unittest.mock import MagicMock, patch

from app.checkpoints import (
    checkpoint_key,
    get_checkpoint,
    get_last_indexed_timestamp_ms,
    get_updates_state,
    set_checkpoint,
    set_updates_state,
    stream_id_from_timestamp_ms,
    timestamp_ms_from_stream_id,
    updates_state_key,
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


def test_updates_state_key_uses_its_own_prefix():
    """The processing state lives under its own prefix, not with checkpoints"""
    key = updates_state_key("product_updates_off", "off")
    assert key == "searchalicious:updates_state:product_updates_off:off"
    assert key != checkpoint_key("product_updates_off", "off")


def test_set_updates_state_writes_a_single_hash():
    redis_client = MagicMock()
    set_updates_state(redis_client, "stream", "off", "1629878400000-0", 3)
    redis_client.hset.assert_called_once_with(
        "searchalicious:updates_state:stream:off",
        mapping={"last_read_id": "1629878400000-0", "pending_events": 3},
    )


def test_set_updates_state_without_last_read_id():
    """A missing last read ID is stored as an empty string"""
    redis_client = MagicMock()
    set_updates_state(redis_client, "stream", "off", None, 0)
    assert redis_client.hset.call_args.kwargs["mapping"] == {
        "last_read_id": "",
        "pending_events": 0,
    }


def test_get_updates_state():
    redis_client = MagicMock()
    redis_client.hgetall.return_value = {
        "last_read_id": "1629878400000-0",
        "pending_events": "4",
    }
    assert get_updates_state(redis_client, "stream", "off") == {
        "last_read_id": "1629878400000-0",
        "pending_events": 4,
    }
    redis_client.hgetall.assert_called_once_with(
        "searchalicious:updates_state:stream:off"
    )


def test_get_updates_state_absent():
    """No state recorded yet (the daemon never ran)"""
    redis_client = MagicMock()
    redis_client.hgetall.return_value = {}
    assert get_updates_state(redis_client, "stream", "off") is None


def test_get_updates_state_empty_last_read_id():
    redis_client = MagicMock()
    redis_client.hgetall.return_value = {"last_read_id": "", "pending_events": "0"}
    assert get_updates_state(redis_client, "stream", "off") == {
        "last_read_id": None,
        "pending_events": 0,
    }


def test_timestamp_ms_from_stream_id():
    assert timestamp_ms_from_stream_id("1629878400123-0") == 1629878400123
    assert timestamp_ms_from_stream_id("1629878400123-42") == 1629878400123


def test_timestamp_ms_from_stream_id_malformed():
    assert timestamp_ms_from_stream_id("not-an-id") is None
    assert timestamp_ms_from_stream_id("") is None
