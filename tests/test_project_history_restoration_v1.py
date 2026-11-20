# -*- coding: utf-8 -*-
"""CHAT-02C — PROJECT HISTORY RESTORATION V1.

The reported symptom was "Restored 6 messages …" with almost no bubbles.
The stored data was never lost: `recovery_summary()` reported only the COUNT
and `loadConversation()` deliberately rendered a status row instead of the
history. These tests lock down both halves of the repair:

* the read-only transcript projection (`ProjectSession.transcript`) and its
  API field — faithful, project-scoped, and provably non-writing;
* the frontend restore path, which must render the stored turns through the
  same `messageNode` used for a live turn.

No test touches real project data: every storage test runs against a
temporary root and restores the workspace root afterwards.
"""

import json
import os
from pathlib import Path

import pytest

from core.project.conversation_store_v1 import conversation_store
from core.project.project_session_v1 import project_session
from core.project.project_workspace_v1 import project_workspace

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "ui" / "static" / "app.js"
API_PY = ROOT / "core" / "project" / "project_api_v1.py"


def _source(path):
    lines = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0]
        lines.append(line)
    return "\n".join(lines)


@pytest.fixture()
def temp_projects(monkeypatch):
    """Point the shared workspace at a temporary projects root.

    Uses a gitignored directory inside the repo: the system pytest tmp dir is
    not writable on this machine (WinError 5).
    """
    import shutil
    import uuid

    root = ROOT / ".pytest_tmp" / "history_restoration" / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(project_workspace, "projects_root", str(root))
    monkeypatch.setattr(project_workspace, "trash_root", str(root / "_trash"))
    os.makedirs(project_workspace.trash_root, exist_ok=True)
    try:
        yield root
    finally:
        shutil.rmtree(str(root), ignore_errors=True)


def _write_chat(root, project_id, messages):
    pdir = os.path.join(str(root), project_id, "conversations")
    os.makedirs(pdir, exist_ok=True)
    payload = {
        "contract": "ConversationStoreV1",
        "version": "1.0",
        "project_id": project_id,
        "updated_at": 1.0,
        "message_count": len(messages),
        "messages": messages,
        "ui": {},
    }
    path = os.path.join(pdir, "chat.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    return path


SIX = [
    {"role": "user", "text": "q1", "attachments": []},
    {"role": "assistant", "text": "a1", "attachments": []},
    {"role": "user", "text": "q2", "attachments": []},
    {"role": "assistant", "text": "a2", "attachments": []},
    {"role": "user", "text": "q3", "attachments": []},
    {"role": "assistant", "text": "a3", "attachments": []},
]


# ==========================================================
# A/B/C/M. TRANSCRIPT IS FAITHFUL, ORDERED AND PROJECT-SCOPED
# ==========================================================

def test_six_stored_messages_are_all_returned_in_order(temp_projects):
    _write_chat(temp_projects, "project_six", SIX)
    out = project_session.transcript("project_six")
    assert len(out) == 6
    assert [e["role"] for e in out] == [
        "user", "assistant", "user", "assistant", "user", "assistant"]
    assert [e["text"] for e in out] == ["q1", "a1", "q2", "a2", "q3", "a3"]


def test_many_messages_keep_order(temp_projects):
    many = [{"role": "user" if i % 2 == 0 else "assistant",
             "text": "m%d" % i, "attachments": []} for i in range(40)]
    _write_chat(temp_projects, "project_many", many)
    out = project_session.transcript("project_many")
    assert [e["text"] for e in out] == ["m%d" % i for i in range(40)]


def test_transcript_is_strictly_project_scoped(temp_projects):
    _write_chat(temp_projects, "project_A", SIX)
    _write_chat(temp_projects, "project_B", [
        {"role": "user", "text": "B-only", "attachments": []}])
    a = [e["text"] for e in project_session.transcript("project_A")]
    b = [e["text"] for e in project_session.transcript("project_B")]
    assert a == ["q1", "a1", "q2", "a2", "q3", "a3"]
    assert b == ["B-only"]
    assert "B-only" not in a


def test_image_only_turns_are_returned_with_their_attachment(temp_projects):
    _write_chat(temp_projects, "project_img", [
        {"role": "user", "text": "", "attachments": [
            {"kind": "image", "display_name": "shot.png",
             "url": "/artifacts/user_media/shot.png", "status": "ready"}]},
        {"role": "assistant", "text": "ok", "attachments": []},
    ])
    out = project_session.transcript("project_img")
    assert len(out) == 2
    assert out[0]["text"] == ""
    # CHAT-02C.2 — attachments survive the public allowlist with their
    # display fields intact (an invented `asset_id` is not part of it).
    assert out[0]["attachments"][0]["kind"] == "image"
    assert out[0]["attachments"][0]["display_name"] == "shot.png"
    assert out[0]["attachments"][0]["url"] == "/artifacts/user_media/shot.png"


def test_unknown_roles_are_skipped_not_guessed(temp_projects):
    _write_chat(temp_projects, "project_odd", [
        {"role": "user", "text": "keep", "attachments": []},
        {"role": "system", "text": "drop", "attachments": []},
        {"text": "no role", "attachments": []},
        "not-a-dict",
        {"role": "assistant", "text": "keep2", "attachments": []},
    ])
    out = project_session.transcript("project_odd")
    assert [e["text"] for e in out] == ["keep", "keep2"]


def test_missing_or_empty_project_returns_empty_without_fabrication(temp_projects):
    assert project_session.transcript("project_does_not_exist") == []
    _write_chat(temp_projects, "project_empty", [])
    assert project_session.transcript("project_empty") == []


# ==========================================================
# DATA SAFETY — THE PROJECTION MUST NOT WRITE
# ==========================================================

def test_transcript_never_modifies_stored_data(temp_projects):
    path = _write_chat(temp_projects, "project_ro", SIX)
    before = Path(path).read_bytes()
    before_mtime = os.path.getmtime(path)

    project_session.transcript("project_ro")
    project_session.transcript("project_ro")

    assert Path(path).read_bytes() == before, "transcript() rewrote chat.json"
    assert os.path.getmtime(path) == before_mtime, "transcript() touched mtime"


def test_reading_a_transcript_writes_no_file_and_creates_no_project(temp_projects):
    """A read must not create a project, a manifest, or a conversation file.

    `project_workspace.subdir()` creates the `conversations/` DIRECTORY on
    demand (pre-existing behaviour shared by every reader), so the assertion
    is about FILES: none may appear, and no manifest may be created.
    """
    project_session.transcript("project_absent")

    pdir = os.path.join(str(temp_projects), "project_absent")
    created = []
    for dirpath, _dirs, names in os.walk(pdir):
        created.extend(names)

    assert created == [], "reading created files: %s" % created
    assert not os.path.exists(os.path.join(pdir, "project.json"))


def test_repeated_reads_do_not_duplicate_messages(temp_projects):
    _write_chat(temp_projects, "project_dup", SIX)
    first = project_session.transcript("project_dup")
    second = project_session.transcript("project_dup")
    assert first == second
    assert len(second) == 6


# ==========================================================
# API SURFACE
# ==========================================================

def test_project_detail_route_exposes_the_transcript():
    src = _source(API_PY)
    assert '"transcript": project_session.transcript(project_id)' in src


def test_recovery_summary_still_reports_the_count():
    """The count field the workspace already relied on is untouched."""
    src = _source(ROOT / "core" / "project" / "project_session_v1.py")
    assert '"message_count": chat.get("message_count")' in src


# ==========================================================
# FRONTEND RESTORE PATH
# ==========================================================

def test_load_conversation_renders_the_stored_turns():
    src = _source(APP_JS)
    start = src.index("async function loadConversation")
    end = src.index("function ", start + 10)
    body = src[start:end]
    assert "data.transcript" in body
    assert "messageNode(role, text, attachments)" in body


def test_load_conversation_no_longer_claims_history_is_not_rendered():
    src = APP_JS.read_text(encoding="utf-8")
    assert "History is NOT rendered here" not in src


def test_load_conversation_skips_only_entries_with_nothing_to_show():
    src = _source(APP_JS)
    start = src.index("async function loadConversation")
    end = src.index("function ", start + 10)
    body = src[start:end]
    # CHAT-02C.2 — an entry with neither text NOR an attachment is skipped
    # (never an empty bubble); an image-only entry is now KEPT.
    assert "if (!text.trim() && !attachments.length) return;" in body
    assert "!role" in body


def test_empty_project_still_shows_the_empty_state():
    src = _source(APP_JS)
    start = src.index("async function loadConversation")
    end = src.index("function ", start + 10)
    body = src[start:end]
    assert "chatEmpty" in body


def test_restore_failure_is_reported_as_failure_not_success():
    src = _source(APP_JS)
    start = src.index("async function loadConversation")
    end = src.index("function ", start + 10)
    body = src[start:end]
    assert "could not be loaded" in body
    assert "status-failed" in body


def test_restored_turns_use_the_same_renderer_as_live_turns():
    """RTL/Markdown from CHAT-02B must apply to restored history too."""
    src = _source(APP_JS)
    assert 'if (role === "assistant")' in src
    assert "bubble.appendChild(renderRichText(body))" in src


# ==========================================================
# CHAT-02 SESSION ISOLATION IS NOT WEAKENED
# ==========================================================

def test_session_scoping_is_still_in_place():
    src = _source(ROOT / "core" / "memory" / "conversation_memory.py")
    assert "session_id" in src
    assert "def history" in src


def test_chat_architect_still_passes_the_session_id():
    src = _source(ROOT / "core" / "chat" / "chat_architect.py")
    assert src.count("session_id=session_id") >= 2


# ==========================================================
# OPT-IN LIVE ACCEPTANCE (needs the running stack)
# ==========================================================

LIVE = os.environ.get("ARCHITECTOS_LIVE_CHAT_TESTS") == "1"


@pytest.mark.skipif(not LIVE, reason="set ARCHITECTOS_LIVE_CHAT_TESTS=1 with the stack running")
class TestLiveHistoryRestoration:

    PROJECT = os.environ.get("ARCHITECTOS_LIVE_PROJECT", "")

    def _get(self, project_id):
        import requests
        s = requests.Session()
        s.trust_env = False
        return s.get("http://127.0.0.1:3000/api/projects/" + project_id,
                     timeout=10800).json()

    def test_api_transcript_matches_the_stored_count(self):
        if not self.PROJECT:
            pytest.skip("set ARCHITECTOS_LIVE_PROJECT")
        data = self._get(self.PROJECT)
        transcript = data.get("transcript") or []
        assert isinstance(transcript, list)
        assert len(transcript) == (data.get("recovery") or {}).get("message_count")
        assert all(e.get("role") in ("user", "assistant") for e in transcript)
