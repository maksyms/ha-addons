import json
from lib.sync_state import SyncState


def test_get_returns_empty_dict_for_unknown_adapter(tmp_state_file):
    state = SyncState(tmp_state_file)
    assert state.get("readwise") == {}


def test_save_and_get_roundtrip(tmp_state_file):
    state = SyncState(tmp_state_file)
    state.save("readwise", {"last_updated": "2026-04-11T03:00:00Z", "cursor": "abc"})
    result = state.get("readwise")
    assert result == {"last_updated": "2026-04-11T03:00:00Z", "cursor": "abc"}


def test_save_preserves_other_adapters(tmp_state_file):
    state = SyncState(tmp_state_file)
    state.save("readwise", {"last": "2026-04-11"})
    state.save("raindrop", {"last": "2026-04-10"})
    assert state.get("readwise") == {"last": "2026-04-11"}
    assert state.get("raindrop") == {"last": "2026-04-10"}


def test_save_overwrites_adapter_state(tmp_state_file):
    state = SyncState(tmp_state_file)
    state.save("readwise", {"cursor": "abc"})
    state.save("readwise", {"cursor": "def", "extra": True})
    assert state.get("readwise") == {"cursor": "def", "extra": True}


def test_persists_across_instances(tmp_state_file):
    state1 = SyncState(tmp_state_file)
    state1.save("readwise", {"cursor": "abc"})

    state2 = SyncState(tmp_state_file)
    assert state2.get("readwise") == {"cursor": "abc"}


def test_handles_corrupted_file(tmp_state_file):
    with open(tmp_state_file, "w") as f:
        f.write("not json{{{")
    state = SyncState(tmp_state_file)
    assert state.get("readwise") == {}
