"""SENT_MESSAGE_EDIT_V1 — deterministic contract tests.

Covers the storage/identity/prefix layer that the revision endpoint
depends on. No GPU, no network, no ChatArchitect, no Ollama: every test
uses a temp path so the real project workspace is never touched.

The live endpoint behaviour is covered by
`runs/ui_interaction_v1/test_feature_a.py` against the real UI.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.conversation_memory import ConversationMemory  # noqa: E402
from core.project.conversation_store_v1 import ConversationStore  # noqa: E402


def _store(tmp_path, monkeypatch):
    store = ConversationStore()
    monkeypatch.setattr(
        store, "path", lambda project_id: str(tmp_path / ("%s.json" % project_id))
    )
    return store


# ==========================================================
# IDENTITY
# ==========================================================

def test_sequenced_message_uses_its_turn_seq():
    store = ConversationStore()
    messages = [{"role": "user", "text": "a", "turn_seq": 7}]
    assert store.message_ref(messages, 0) == "seq:7"


def test_identical_text_produces_distinct_legacy_refs():
    """Two messages with the SAME text must never share an identity."""

    store = ConversationStore()
    messages = [
        {"role": "user", "text": "same text"},
        {"role": "assistant", "text": "ok"},
        {"role": "user", "text": "same text"},
    ]

    first = store.message_ref(messages, 0)
    second = store.message_ref(messages, 2)

    assert first != second
    assert first.startswith("legacy:") and second.startswith("legacy:")


def test_legacy_ref_is_not_an_array_index():
    store = ConversationStore()
    messages = [{"role": "user", "text": "hello"}]
    ref = store.message_ref(messages, 0)
    assert ref != "0" and not ref.isdigit()


def test_legacy_ref_survives_the_retention_cap():
    """Dropping an OLDER message must not change a newer message's ref.

    This is the property an array index does not have.
    """

    store = ConversationStore()
    messages = [
        {"role": "user", "text": "first"},
        {"role": "assistant", "text": "reply"},
        {"role": "user", "text": "second"},
    ]
    ref_before = store.message_ref(messages, 2)

    trimmed = messages[1:]           # simulate the 100-message cap
    ref_after = store.message_ref(trimmed, 1)

    assert ref_before == ref_after


def test_resolve_ref_round_trips_both_kinds():
    store = ConversationStore()
    messages = [
        {"role": "user", "text": "legacy one"},
        {"role": "assistant", "text": "legacy reply"},
        {"role": "user", "text": "sequenced", "turn_seq": 9},
    ]

    for index in range(len(messages)):
        ref = store.message_ref(messages, index)
        assert store.resolve_ref(messages, ref) == index


def test_resolve_unknown_ref_returns_none():
    store = ConversationStore()
    assert store.resolve_ref([{"role": "user", "text": "x"}], "seq:999") is None
    assert store.resolve_ref([], "legacy:abc") is None


# ==========================================================
# PREFIX
# ==========================================================

def test_prefix_stops_before_the_target():
    store = ConversationStore()
    messages = [
        {"role": "user", "text": "u1"},
        {"role": "assistant", "text": "a1"},
        {"role": "user", "text": "u2"},
        {"role": "assistant", "text": "a2"},
    ]

    assert store.active_prefix(messages, 0) == []
    assert store.active_prefix(messages, 2) == [
        {"role": "user", "text": "u1"},
        {"role": "assistant", "text": "a1"},
    ]


def test_prefix_excludes_superseded_entries():
    store = ConversationStore()
    messages = [
        {"role": "user", "text": "u1"},
        {"role": "assistant", "text": "a1", "superseded_by": 10},
        {"role": "user", "text": "u2"},
    ]

    prefix = store.active_prefix(messages, 2)
    assert [item["text"] for item in prefix] == ["u1"]


# ==========================================================
# APPEND / SUPERSEDE / NONCE
# ==========================================================

def test_append_turn_assigns_monotonic_sequences(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)

    _p, first = store.append_turn("proj", "user", "one")
    _p, second = store.append_turn("proj", "assistant", "two")
    payload, third = store.append_turn("proj", "user", "three")

    assert (first, second, third) == (1, 2, 3)
    assert payload["next_turn_seq"] == 4
    assert [m["turn_seq"] for m in payload["messages"]] == [1, 2, 3]


def test_append_turn_preserves_revision_metadata(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)

    payload, seq = store.append_turn(
        "proj", "user", "revised",
        attachments=[{"url": "/artifacts/a.png", "kind": "image"}],
        extra={"revises": {"ref": "seq:1", "text": "original"}},
    )

    stored = payload["messages"][-1]
    assert stored["turn_seq"] == seq
    assert stored["revises"]["text"] == "original"
    assert stored["attachments"][0]["url"] == "/artifacts/a.png"


def test_supersede_marks_only_the_replaced_range(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)

    for role, text in [("user", "u1"), ("assistant", "a1"), ("user", "u2")]:
        store.append_turn("proj", role, text)

    original_len = 3

    # the revision appends two new messages, then marks the old range
    store.append_turn("proj", "user", "revised")
    store.append_turn("proj", "assistant", "new reply")
    payload = store.mark_superseded("proj", 0, 4, to_index=original_len)

    messages = payload["messages"]
    assert all(m.get("superseded_by") == 4 for m in messages[:3])
    # the NEW revision messages must stay active
    assert messages[3].get("superseded_by") is None
    assert messages[4].get("superseded_by") is None


def test_nonce_is_recorded(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    payload = store.set_last_revision_nonce("proj", "abc-123")
    assert payload["last_revision_nonce"] == "abc-123"
    assert store.load("proj")["last_revision_nonce"] == "abc-123"


def test_append_turn_does_not_drop_unknown_payload_keys(tmp_path, monkeypatch):
    """`save()` rebuilds the payload; `append_turn` must not."""

    store = _store(tmp_path, monkeypatch)
    store.append_turn("proj", "user", "one")

    raw = json.load(open(store.path("proj"), encoding="utf-8"))
    raw["custom_key"] = "keep me"
    json.dump(raw, open(store.path("proj"), "w", encoding="utf-8"))

    payload, _seq = store.append_turn("proj", "user", "two")
    assert payload.get("custom_key") == "keep me"


# ==========================================================
# IN-PROCESS MEMORY
# ==========================================================

def test_replace_session_rebuilds_only_that_session():
    memory = ConversationMemory()
    memory.add("p1 turn", "user", session_id="p1")
    memory.add("p1 reply", "assistant", session_id="p1")
    memory.add("p2 turn", "user", session_id="p2")

    added = memory.replace_session("p1", [
        {"role": "user", "text": "kept"},
    ])

    assert added == 1
    p1 = memory.history(20, session_id="p1")
    p2 = memory.history(20, session_id="p2")

    assert [item["message"] for item in p1] == ["kept"]
    assert [item["message"] for item in p2] == ["p2 turn"]


def test_replace_session_with_empty_prefix_clears_only_that_session():
    memory = ConversationMemory()
    memory.add("p1 turn", "user", session_id="p1")
    memory.add("p2 turn", "user", session_id="p2")

    memory.replace_session("p1", [])

    assert memory.history(20, session_id="p1") == []
    assert len(memory.history(20, session_id="p2")) == 1


def test_prefix_seeded_into_memory_is_exactly_the_prefix():
    """The model must see the prefix, never the downstream branch."""

    memory = ConversationMemory()
    for role, text in [("user", "u1"), ("assistant", "a1"),
                       ("user", "u2"), ("assistant", "a2")]:
        memory.add(text, role, session_id="p1")

    prefix = [
        {"role": "user", "text": "u1"},
        {"role": "assistant", "text": "a1"},
    ]
    memory.replace_session("p1", prefix)

    history = memory.history(20, session_id="p1")
    assert [item["message"] for item in history] == ["u1", "a1"]
