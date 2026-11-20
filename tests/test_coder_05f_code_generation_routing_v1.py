# tests/test_coder_05f_code_generation_routing_v1.py
"""
CODER-05F — Code-generation request misrouted as staging action.

Focused regression for the defect measured 2026-10-25 in project_f043688f:
a creation request containing both generation verbs ("تولید کن", "نسخه جدید")
and a save/approval mention ("قبل از ذخیرهٔ فایل تأیید جداگانهٔ من را بگیر")
was intercepted by the approval handler because ``staged_file_action``
matched "تأیید" as an approval. The handler answered "no pending proposal"
and the coder was never called.

Safety requirement: a generation turn MUST win over a staging action.
"""
from __future__ import annotations

import ast
import inspect
import json
import os
import sys
import textwrap

# Ensure project root is on path so ``core`` imports resolve.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from core.chat.chat_architect import ChatArchitect
from core.chat.code_file_staging_v1 import staged_file_action
import core.cognition.intent_engine as IE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chat() -> ChatArchitect:
    """Return a ChatArchitect instance with a minimal context."""
    chat = object.__new__(ChatArchitect)
    chat.context = {}
    return chat


def _load_real_failing_request() -> str:
    """Load the exact 1 379-character failing request from chat.json."""
    path = os.path.join(
        _PROJECT_ROOT,
        "data",
        "projects",
        "project_f043688f",
        "conversations",
        "chat.json",
    )
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["messages"][22]["text"]


# ---------------------------------------------------------------------------
# Real-world data — the exact failing request from project_f043688f message 22
# ---------------------------------------------------------------------------

_REAL_FAILING_REQUEST: str = _load_real_failing_request()


# ---------------------------------------------------------------------------
# 1. Generation must win over staging action
# ---------------------------------------------------------------------------

class TestCodeGenerationTurn:
    """
    ``_code_generation_turn`` must recognise explicit production verbs
    combined with a programming signal.
    """

    @pytest.mark.parametrize(
        "text,expected",
        [
            # The real 1 379-char request contains .py and generation verbs.
            (_REAL_FAILING_REQUEST, True),
            # Synthetic: generation verb + .py extension
            (
                "یک نسخه جدید و کامل تولید کن. فایل app.py."
                " قبل از ذخیرهٔ فایل تأیید جداگانهٔ من را بگیر.",
                True,
            ),
            # Negatives — no generation verb
            ("رد کن", False),
            ("تأیید می‌کنم، همین فایل را ذخیره کن", False),
            ("سلام، حالت چطوره؟", False),
            ("این فایل app.py چیست؟", False),
            ("یک ویلای دو طبقه بساز", False),  # architectural, not code_file
            # Generation verb but NO programming signal -> not a code turn
            ("یک نسخه جدید بساز", False),
            ("", False),
        ],
    )
    def test_code_generation_turn(self, text: str, expected: bool) -> None:
        chat = _make_chat()
        assert chat._code_generation_turn(text) is expected


class TestStagingActionTurn:
    """
    ``_staging_action_turn`` must return False for ANY generation request,
    even when the text also contains approval vocabulary.
    """

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("رد کن", True),
            ("این فایل را رد کن", True),
            ("تأیید می‌کنم", True),
            ("تأیید می‌کنم، همین فایل را ذخیره کن", True),
            # Must NOT match generation requests (real + synthetic)
            (_REAL_FAILING_REQUEST, False),
            (
                "نسخه اصلاح‌شده را تولید کن؛ فعلاً ذخیره نکن"
                " و app.py را بساز.",
                False,
            ),
            (
                "یک برنامه جدید بساز و قبل از ذخیره تأیید من را بگیر"
                " (فایل calculator.py).",
                False,
            ),
            (
                "تأیید می‌کنم و یک نسخه جدید هم تولید کن (main.py).",
                False,
            ),
            # Plain chat
            ("سلام", False),
        ],
    )
    def test_staging_action_turn(self, text: str, expected: bool) -> None:
        chat = _make_chat()
        assert chat._staging_action_turn(text) is expected


class TestCodeFileCreationTurn:
    """
    ``_code_file_creation_turn`` must remain true for creation/regeneration
    requests even when they also mention future approval.
    """

    @pytest.mark.parametrize(
        "text,expected",
        [
            (_REAL_FAILING_REQUEST, True),
            (
                "یک برنامه جدید بساز و قبل از ذخیره تأیید من را بگیر"
                " (فایل app.py).",
                True,
            ),
            (
                "نسخه اصلاح‌شده را تولید کن؛ فعلاً ذخیره نکن"
                " و app.py را بساز.",
                True,
            ),
            # Negatives
            ("رد کن", False),
            ("تأیید می‌کنم، همین فایل را ذخیره کن", False),
            ("سلام", False),
            ("این فایل app.py چیست؟", False),
            ("یک ویلای دو طبقه بساز", False),
            # Creation verb but no programming signal -> not code_file
            ("یک نسخه جدید بساز", False),
        ],
    )
    def test_code_file_creation_turn(self, text: str, expected: bool) -> None:
        chat = _make_chat()
        assert chat._code_file_creation_turn(text) is expected


# ---------------------------------------------------------------------------
# 2. The boundary gate must open for the real failing request
# ---------------------------------------------------------------------------

class TestBoundaryGate:
    """
    The three-part gate in ``_handle_internal`` must open when any of the
    predicates is true.
    """

    def test_real_failing_request_opens_gate(self) -> None:
        chat = _make_chat()
        assert chat._staging_action_turn(_REAL_FAILING_REQUEST) is False
        assert chat._code_file_creation_turn(_REAL_FAILING_REQUEST) is True
        # Therefore the gate (intent==code/capability OR staging OR creation)
        # would open because creation is true.

    def test_standalone_reject_opens_gate(self) -> None:
        chat = _make_chat()
        assert chat._staging_action_turn("رد کن") is True

    def test_approval_turn_opens_gate(self) -> None:
        chat = _make_chat()
        assert chat._staging_action_turn(
            "تأیید می‌کنم، همین فایل را ذخیره کن"
        ) is True


# ---------------------------------------------------------------------------
# 3. Approval handler must refuse generation turns
# ---------------------------------------------------------------------------

class TestApprovalHandlerSafety:
    """
    ``_authorized_code_file_approval`` must return None (i.e. skip) when
    ``_code_generation_turn`` is true, preventing a creation request from
    accidentally approving a pending proposal.
    """

    def test_generation_turn_skips_approval(self) -> None:
        chat = _make_chat()
        # We cannot call the real approval handler without a full project
        # context, but we can assert the predicate it relies on.
        assert chat._code_generation_turn(_REAL_FAILING_REQUEST) is True
        # Because the handler begins with:
        #   if self._code_generation_turn(text): return None
        # the turn would exit before any staged-file operation.


# ---------------------------------------------------------------------------
# 4. Intent-engine programming classifier consistency
# ---------------------------------------------------------------------------

class TestProgrammingRequestKind:
    """
    The underlying classifier must label the long failing request as
    ``code_file`` because it contains ``.py``.
    """

    def test_real_failing_request_is_code_file(self) -> None:
        assert IE._programming_request_kind(_REAL_FAILING_REQUEST) == "code_file"

    def test_architectural_request_is_not_code_file(self) -> None:
        assert IE._programming_request_kind("یک ویلای دو طبقه بساز") != "code_file"


# ---------------------------------------------------------------------------
# 5. No false positives on staged_file_action
# ---------------------------------------------------------------------------

class TestStagedFileActionBehaviour:
    """
    ``staged_file_action`` is now ACTION-aware.

    CODER-STAGING-ACTION-SAFETY-01 — this matcher used to be a substring test
    and was ALLOWED to return "approve" for a creation request that merely
    mentioned «تأیید»; the defence lived upstream. It now requires an explicit
    affirmative approval action, so the same turn classifies as ``None`` and
    the upstream guards remain as defence in depth.
    """

    def test_staged_file_action_still_matches_approve(self) -> None:
        assert staged_file_action("تأیید می‌کنم") == "approve"

    def test_staged_file_action_still_matches_reject(self) -> None:
        assert staged_file_action("رد کن") == "reject"

    def test_staged_file_action_on_failing_request_is_not_an_action(self) -> None:
        # The request MENTIONS «بدون تأیید من ذخیره نکن»; it does not approve.
        assert staged_file_action(_REAL_FAILING_REQUEST) is None


# ---------------------------------------------------------------------------
# 6. AST guard — both predicates must remain in the boundary gate
# ---------------------------------------------------------------------------

class TestAstGuard:
    """
    The boundary gate must contain BOTH ``_staging_action_turn`` and
    ``_code_file_creation_turn``. Removing either silently re-opens a
    regression window.
    """

    def test_boundary_gate_contains_both_predicates(self) -> None:
        source = textwrap.dedent(inspect.getsource(ChatArchitect._handle_internal))
        tree = ast.parse(source)

        found_staging = False
        found_creation = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "_staging_action_turn":
                        found_staging = True
                    if node.func.attr == "_code_file_creation_turn":
                        found_creation = True

        assert found_staging, (
            "_staging_action_turn must be present in the boundary gate"
        )
        assert found_creation, (
            "_code_file_creation_turn must be present in the boundary gate"
        )

    def test_approval_handler_contains_generation_guard(self) -> None:
        source = textwrap.dedent(
            inspect.getsource(ChatArchitect._authorized_code_file_approval)
        )
        tree = ast.parse(source)

        # CODER-05F — the guard is ``_code_source_request_turn`` (a strict
        # superset of ``_code_generation_turn``): it also catches CREATE verbs
        # such as "بساز" that the narrower generation predicate misses.
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "_code_source_request_turn":
                        found = True

        assert found, (
            "_code_source_request_turn guard must be present in approval handler"
        )


# ---------------------------------------------------------------------------
# 7. Handler-level behaviour — mocked coder, temporary sandbox, no host writes
# ---------------------------------------------------------------------------

import core.chat.code_file_staging_v1 as _staging

_SESSION = "project_05f_handler"

_FAKE_SOURCE = (
    "import tkinter as tk\n"
    "\n"
    "class Calculator:\n"
    "    def __init__(self, root):\n"
    "        self.root = root\n"
)

_AUTH = {
    "trusted": True,
    "actor_id": "local_user",
    "session_id": "sess_05f_handler",
    "project_id": _SESSION,
}


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """Redirect the project sandbox into a temporary directory.

    Both the staging store and the writer resolve ``<project>/documents``
    through ``project_workspace.subdir``, so one patch isolates BOTH the
    read-only target-existence check and any approved write.
    """
    from core.project.project_workspace_v1 import project_workspace

    documents = tmp_path / "documents"
    documents.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        project_workspace, "subdir", lambda project_id, name: str(documents)
    )
    _staging.reset_staging()
    yield documents
    _staging.reset_staging()


def _handler_chat(extra_context=None):
    """A ChatArchitect whose coder is mocked — no model is ever called."""
    chat = object.__new__(ChatArchitect)
    chat.context = {"trusted_local_authorization": dict(_AUTH)}
    if extra_context:
        chat.context.update(extra_context)

    calls = []

    def fake_coder(self, text):
        calls.append(text)
        return _FAKE_SOURCE

    chat._generate_code_with_coder = fake_coder.__get__(chat, ChatArchitect)
    return chat, calls


def _seed_pending(documents):
    return _staging.stage_code_file(
        project_id=_SESSION,
        filename="app.py",
        content="seed = 1\n",
        documents_root=str(documents),
        origin="seed",
        authorization=dict(_AUTH),
    )


def _written(documents):
    return (documents / "code" / "app.py").exists()


class TestCreationReachesCoder:
    """A creation/regeneration request must reach the coding model."""

    def test_real_failing_request_reaches_coder(self, sandbox) -> None:
        """Item 1 — the exact request from project_f043688f message 22."""

        chat, calls = _handler_chat()

        assert chat._authorized_code_file_approval(
            _REAL_FAILING_REQUEST, _SESSION
        ) is None

        message = chat._authorized_code_file_creation(
            _REAL_FAILING_REQUEST, _SESSION
        )

        assert len(calls) == 1, "the coding model must be called exactly once"

        pending = _staging.pending_proposal(_SESSION)
        assert isinstance(pending, dict)
        assert pending["origin"] == "coder_model"
        assert pending["filename"] == "app.py"
        assert pending["status"] == "awaiting_approval"

        assert "SHA-256" in message
        assert "نحو (syntax): معتبر" in message

        # Item 11 — nothing may be written before approval.
        assert not _written(sandbox)

    def test_creation_request_with_future_approval_reaches_coder(
        self, sandbox
    ) -> None:
        """Item 2 / requirement A."""

        text = (
            "یک برنامه جدید بساز و قبل از ذخیره تأیید من را بگیر "
            "(فایل app.py)."
        )
        chat, calls = _handler_chat()

        assert chat._staging_action_turn(text) is False
        assert chat._authorized_code_file_approval(text, _SESSION) is None

        message = chat._authorized_code_file_creation(text, _SESSION)

        assert len(calls) == 1
        assert isinstance(_staging.pending_proposal(_SESSION), dict)
        assert "SHA-256" in message
        assert not _written(sandbox)

    def test_regeneration_without_save_reaches_coder(self, sandbox) -> None:
        """Item 3 / requirement B."""

        text = "نسخه جدید و کامل تولید کن؛ فعلاً ذخیره نکن (app.py)."
        chat, calls = _handler_chat()

        assert chat._staging_action_turn(text) is False
        assert chat._authorized_code_file_approval(text, _SESSION) is None

        chat._authorized_code_file_creation(text, _SESSION)

        assert len(calls) == 1
        assert isinstance(_staging.pending_proposal(_SESSION), dict)
        assert not _written(sandbox)

    def test_new_request_never_reuses_history_bytes(self, sandbox) -> None:
        """Item 10 (CODER-05C protection) — history is not a substitute."""

        chat, calls = _handler_chat()
        chat._code_from_conversation_history = (
            lambda session_id: "STALE = 'from history'\n"
        )

        chat._authorized_code_file_creation(_REAL_FAILING_REQUEST, _SESSION)

        pending = _staging.pending_proposal(_SESSION)
        assert len(calls) == 1
        assert pending["origin"] == "coder_model"
        assert "STALE" not in pending["content"]

    def test_coder_failure_reports_failure_without_staging(self, sandbox) -> None:
        """Item 10 (requirement I) — no silent substitution on model failure."""

        chat, calls = _handler_chat()
        chat._generate_code_with_coder = (
            lambda text: None
        )
        chat._code_from_conversation_history = (
            lambda session_id: "STALE = 1\n"
        )

        message = chat._authorized_code_file_creation(
            _REAL_FAILING_REQUEST, _SESSION
        )

        assert _staging.pending_proposal(_SESSION) is None
        assert "کد کامل و قابل اتکایی" in message
        assert not _written(sandbox)


class TestStagingActions:
    """Standalone approve/reject must keep working (CODER-05B/05D)."""

    def test_standalone_rejection_with_pending_proposal(self, sandbox) -> None:
        """Item 4 / requirement E / item 12."""

        _seed_pending(sandbox)
        assert isinstance(_staging.pending_proposal(_SESSION), dict)

        chat, calls = _handler_chat()

        assert chat._staging_action_turn("رد کن") is True
        message = chat._authorized_code_file_approval("رد کن", _SESSION)

        assert "رد شد" in message
        assert _staging.pending_proposal(_SESSION) is None
        assert calls == [], "a rejection must never call the coding model"
        assert not _written(sandbox)

    def test_rejection_without_pending_proposal(self, sandbox) -> None:
        """Item 5."""

        chat, calls = _handler_chat()

        message = chat._authorized_code_file_approval("رد کن", _SESSION)

        assert "هیچ پیش‌نویس فایل در انتظار" in message
        assert calls == []
        assert not _written(sandbox)

    def test_explicit_save_approval_writes_under_capability(
        self, sandbox
    ) -> None:
        """Item 6 / requirement F — the existing strict write path."""

        proposal = _seed_pending(sandbox)
        chat, calls = _handler_chat(
            {"approval_capability": proposal["approval_token"]}
        )

        message = chat._authorized_code_file_approval(
            "تأیید می‌کنم، همین فایل را ذخیره کن", _SESSION
        )

        assert "ذخیره شد" in message
        assert _written(sandbox)
        assert calls == []
        assert _staging.pending_proposal(_SESSION) is None

    @pytest.mark.parametrize(
        "text",
        [
            "بدون تأیید من هیچ فایلی ذخیره نکن (app.py).",
            "قبل از ذخیره تأیید من را بگیر (app.py).",
        ],
    )
    def test_approval_words_without_action_do_not_approve(
        self, sandbox, text
    ) -> None:
        """Item 7 / requirement C — mentioning approval is not granting it.

        The capability token IS available, so this proves the guard and not a
        missing token is what prevents the write.
        """

        proposal = _seed_pending(sandbox)
        chat, calls = _handler_chat(
            {"approval_capability": proposal["approval_token"]}
        )

        message = chat._authorized_code_file_approval(text, _SESSION)

        assert "اجازهٔ ذخیره نمی‌دهد" in message
        assert not _written(sandbox)
        assert isinstance(_staging.pending_proposal(_SESSION), dict)
        assert calls == []


class TestConflictProtection:
    """Item 8 / requirement H — a pending proposal is never replaced."""

    def test_creation_request_with_pending_proposal_preserves_conflict(
        self, sandbox
    ) -> None:
        _seed_pending(sandbox)
        chat, calls = _handler_chat()

        message = chat._authorized_code_file_creation(
            _REAL_FAILING_REQUEST, _SESSION
        )

        assert "در انتظار تأیید شماست" in message
        assert calls == [], "no inference may be spent on a discarded result"

        pending = _staging.pending_proposal(_SESSION)
        assert isinstance(pending, dict)
        assert pending["origin"] == "seed", "the original proposal must survive"
        assert not _written(sandbox)


class TestArchitecturalStaysArchitectural:
    """Item 9 — an architectural request must never reach the coder."""

    @pytest.mark.parametrize(
        "text",
        [
            "یک ویلای دو طبقه بساز",
            "پلان را اصلاح کن و نسخه جدید بده",
            "نمای ساختمان را با آجر قرمز دوباره تولید کن",
        ],
    )
    def test_architectural_request_does_not_enter_code_path(
        self, sandbox, text
    ) -> None:
        chat, calls = _handler_chat()

        assert chat._code_source_request_turn(text) is False
        assert chat._code_file_creation_turn(text) is False
        assert chat._staging_action_turn(text) is False
        assert chat._authorized_code_file_approval(text, _SESSION) is None
        assert chat._authorized_code_file_creation(text, _SESSION) is None
        assert calls == []
        assert _staging.pending_proposal(_SESSION) is None
