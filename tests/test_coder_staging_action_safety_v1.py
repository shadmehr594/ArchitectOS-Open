# tests/test_coder_staging_action_safety_v1.py
"""CODER-STAGING-ACTION-SAFETY-01 — a mention is not a command.

Measured 2026-10-26 in project_5893d83b: the user asked for an ISOLATED
behavioural verification of the repaired draft and explicitly forbade saving or
changing the project file. ArchitectOS answered

    پیش‌نویس فایل «app.py» رد شد و هیچ فایلی نوشته نشد.

The turn contained «عدد ۵ را وارد کن» — and «وارد کن» ENDS WITH «رد کن». The
classifier was a substring test, and a second substring copy of the rejection
vocabulary lived in ``chat_architect``, so both paths agreed on the wrong
answer.

Approving or rejecting is a privileged state change. It is now selected ONLY
from an explicit, affirmative, current command:

* whole-word matching (both boundaries) — «وارد کن» / «رد کنم» cannot match,
* quoted spans and functional-verification STATUS phrases are removed first,
* questions, negations and deferred/conditional mentions authorise nothing,
* one classifier (``staged_file_action``) is the only authority.

Nothing here writes a file, runs Docker or packages anything.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

import core.chat.code_file_staging_v1 as staging
import core.chat.project_code_file_writer_v1 as writer
from core.chat.chat_architect import ChatArchitect
from core.chat.code_file_staging_v1 import (
    mentions_approval,
    staged_file_action,
)


# ---------------------------------------------------------------------------
# The EXACT live verification turn (verbatim, ZWNJ included)
# ---------------------------------------------------------------------------

LIVE_VERIFICATION_REQUEST = 'می\u200cخواهم عملکرد پیش\u200cنویس اصلاح\u200cشده `app.py` را بررسی کنی.\n\nSHA-256 نسخه موردنظر:\n`166b54df04bc336d1d7ac904867e1a4a0ed61e9f430ea6df2b7ff5a3a4aa5d34`\n\nبا استفاده از مسیر آزمون ایزوله موجود، رفتار کلاس Calculator را بررسی کن:\n\n1. عدد ۵ را با `on_digit(5)` وارد کن.\n2. عملگر `+` را با `on_operator("+")` انتخاب کن.\n3. بررسی کن مقدار `operand1` همچنان ۵ باشد.\n4. عملگر را با `on_operator("*")` تغییر بده.\n5. بررسی کن مقدار `operand1` همچنان ۵ و عملگر برابر `*` باشد.\n6. عدد ۲ را وارد کن و بررسی کن مقدار `operand2` برابر ۲ شود.\n\nبرای هر مرحله PASS یا FAIL واقعی، مقدار مشاهده\u200cشده و مقدار موردانتظار را گزارش کن.\n\nاگر اجرای ایزوله نیازمند مجوز یا توکن تازه است، ابتدا آن را درخواست کن و تا دریافت مجوز معتبر اجرا نکن.\n\nفایل پروژه را ذخیره یا تغییر نده. هیچ EXE نساز و هیچ نتیجه آزمایش\u200cنشده\u200cای را PASS اعلام نکن.'

#: The repaired digest the live request named (recorded, never reconstructed).
LIVE_REPAIRED_SHA256 = (
    "166b54df04bc336d1d7ac904867e1a4a0ed61e9f430ea6df2b7ff5a3a4aa5d34"
)

PROJECT = "project_staging_action_safety"
ACTOR = "local_user"
SESSION = "sess_staging_action"

AUTH = {
    "trusted": True,
    "actor_id": ACTOR,
    "session_id": SESSION,
    "project_id": PROJECT,
}

SOURCE = (
    "class Calculator:\n"
    "    def __init__(self):\n"
    "        self.operand1 = 0\n"
    "        self.operator = None\n"
    "\n"
    "    def on_operator(self, op):\n"
    "        # Bug: resets the first operand\n"
    "        self.operand1 = 0\n"
    "        self.operator = op\n"
)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _forbidden(label):
    def _raise(*_args, **_kwargs):
        raise AssertionError("unexpected call: " + label)

    return _raise


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """A real in-memory pending proposal with a known digest."""

    from core.project.project_workspace_v1 import project_workspace

    documents = tmp_path / "documents"
    documents.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        project_workspace, "subdir", lambda project_id, name: str(documents)
    )

    monkeypatch.setattr(
        writer, "create_project_code_file", _forbidden("file_write")
    )
    monkeypatch.setattr(subprocess, "run", _forbidden("subprocess.run"))
    monkeypatch.setattr(subprocess, "Popen", _forbidden("subprocess.Popen"))

    staging.reset_staging()

    proposal = staging.stage_code_file(
        project_id=PROJECT,
        filename="app.py",
        content=SOURCE,
        documents_root=str(documents),
        origin="coder_model",
        authorization=dict(AUTH),
    )

    assert proposal["status"] == "awaiting_approval"
    assert proposal["digest"] == _sha(SOURCE)

    yield {"documents": documents, "proposal": proposal}

    staging.reset_staging()


@pytest.fixture()
def writable_sandbox(tmp_path, monkeypatch):
    """Same pending proposal, but the writer is REAL (into a temp directory).

    Only the approval-path test needs an actual write; every other test in this
    module forbids one.
    """

    from core.project.project_workspace_v1 import project_workspace

    documents = tmp_path / "documents"
    documents.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        project_workspace, "subdir", lambda project_id, name: str(documents)
    )
    monkeypatch.setattr(subprocess, "run", _forbidden("subprocess.run"))
    monkeypatch.setattr(subprocess, "Popen", _forbidden("subprocess.Popen"))

    staging.reset_staging()

    proposal = staging.stage_code_file(
        project_id=PROJECT,
        filename="app.py",
        content=SOURCE,
        documents_root=str(documents),
        origin="coder_model",
        authorization=dict(AUTH),
    )

    yield {"documents": documents, "proposal": proposal}

    staging.reset_staging()


def _chat(auth=None, capability=None):
    chat = object.__new__(ChatArchitect)
    chat.context = {"trusted_local_authorization": dict(auth or AUTH)}
    if capability is not None:
        chat.context["approval_capability"] = capability
    return chat


def _snapshot():
    """Everything that must survive a mention unchanged."""

    live = staging._STAGED[PROJECT]
    return {
        "digest": live.get("digest"),
        "revision": live.get("revision"),
        "content": live.get("content"),
        "filename": live.get("filename"),
        "status": live.get("status"),
        "origin": live.get("origin"),
        "capability": dict(live.get("capability") or {}),
        "token": staging._CAPABILITY_TOKENS.get(PROJECT),
        "approval_token": live.get("approval_token"),
    }


def _written(documents):
    return (documents / "code" / "app.py").exists()


# ===========================================================================
# 0. The live turn is recorded verbatim
# ===========================================================================

class TestRecordedLiveTurn:
    def test_literal_matches_the_recorded_conversation(self):
        import json

        path = os.path.join(
            _PROJECT_ROOT,
            "data",
            "projects",
            "project_5893d83b",
            "conversations",
            "chat.json",
        )
        if not os.path.isfile(path):
            pytest.skip("project_5893d83b conversation data not present")

        with open(path, encoding="utf-8") as handle:
            messages = json.load(handle)["messages"]

        assert messages[6]["text"] == LIVE_VERIFICATION_REQUEST
        assert LIVE_REPAIRED_SHA256 in LIVE_VERIFICATION_REQUEST


# ===========================================================================
# 1-5. The exact live request changes nothing
# ===========================================================================

class TestLiveVerificationRequest:
    def test_classifier_does_not_see_an_action(self):
        assert staged_file_action(LIVE_VERIFICATION_REQUEST) is None

    def test_turn_is_not_an_approval_mention(self):
        assert mentions_approval(LIVE_VERIFICATION_REQUEST) is False

    def test_staging_gate_is_not_opened(self):
        assert _chat()._staging_action_turn(LIVE_VERIFICATION_REQUEST) is False

    def test_handler_performs_no_action(self, sandbox):
        before = _snapshot()

        message = _chat()._authorized_code_file_approval(
            LIVE_VERIFICATION_REQUEST, PROJECT
        )

        assert message is None, "a verification request must not be answered"
        assert _snapshot() == before

    def test_pending_state_is_byte_identical_afterwards(self, sandbox):
        proposal = sandbox["proposal"]
        before = _snapshot()

        _chat()._authorized_code_file_approval(
            LIVE_VERIFICATION_REQUEST, PROJECT
        )

        live = staging.pending_proposal(PROJECT)
        assert live is not None
        assert live["digest"] == proposal["digest"]
        assert live["revision"] == before["revision"]
        assert live["content"] == SOURCE
        assert live["filename"] == "app.py"
        assert live["status"] == "awaiting_approval"
        # The capability is neither consumed nor rotated.
        assert _snapshot()["capability"] == before["capability"]
        assert _snapshot()["capability"].get("consumed") in (None, False)
        assert _snapshot()["token"] == before["token"]

    def test_nothing_is_written_executed_or_packaged(self, sandbox):
        _chat()._authorized_code_file_approval(
            LIVE_VERIFICATION_REQUEST, PROJECT
        )

        assert not _written(sandbox["documents"])
        assert not list(sandbox["documents"].rglob("*.py"))
        assert staging.pending_proposal(PROJECT)["writes_performed"] == 0

    def test_the_rejection_reply_is_never_produced(self, sandbox):
        message = _chat()._authorized_code_file_approval(
            LIVE_VERIFICATION_REQUEST, PROJECT
        )

        assert message is None
        assert staging.pending_proposal(PROJECT) is not None


# ===========================================================================
# 6. «رد کن» inside another word is never a rejection
# ===========================================================================

class TestWordBoundary:
    @pytest.mark.parametrize(
        "text,why",
        [
            ("عدد ۵ را وارد کن.", "وارد کن ends with رد کن"),
            ("عدد ۲ را وارد کن و بررسی کن.", "the live step 6"),
            ("مقدار operand1 را وارد کن", "same suffix"),
            ("برای هر مرحله PASS یا FAIL گزارش کن", "report"),
            ("عملگر را انتخاب کن", "select"),
            ("مقدار را بررسی کن", "check"),
            ("تغییر بده", "change"),
            ("رد کنم؟", "first person, interrogative"),
            ("آیا باید پیش‌نویس را رد کنم؟", "question"),
            ("رد نکن", "negated"),
            ("«رد کن» را بررسی کن", "quoted"),
            ("اگر رد کنی چه می‌شود", "conditional"),
        ],
    )
    def test_never_classified_as_rejection(self, text, why):
        assert staged_file_action(text) is None, why

    @pytest.mark.parametrize(
        "text",
        [
            "رد کن",
            "ردش کن",
            "لغو کن",
            "انصراف",
            "پیش‌نویس فعلی فایل app.py را رد کن",
            "reject",
        ],
    )
    def test_explicit_rejections_are_still_recognised(self, text):
        assert staged_file_action(text) == "reject"

    def test_word_boundary_control_pair(self, sandbox):
        """Positive and negative control over the SAME suffix."""

        before = _snapshot()

        assert _chat()._authorized_code_file_approval(
            "عدد ۵ را وارد کن", PROJECT
        ) is None
        assert _snapshot() == before

        rejected = _chat()._authorized_code_file_approval("رد کن", PROJECT)
        assert "رد شد" in rejected
        assert staging.pending_proposal(PROJECT) is None


# ===========================================================================
# 7. Status text never approves
# ===========================================================================

class TestStatusIsNotConsent:
    @pytest.mark.parametrize(
        "text",
        [
            "تأیید عملکردی هنوز انجام نشده؛ اجرا نکن",
            "تأیید عملکردی (functional): اجرا نشده (NOT_RUN)",
            "تأیید عملکردی: اجرا نشده — درستی رفتار برنامه تأیید نشده است",
            "بازبینی ایستا بی‌ایراد است ولی تأیید عملکردی انجام نشده",
            "تأیید نشده",
            "تأییدنشده است",
        ],
    )
    def test_status_phrase_is_not_an_approval(self, text):
        assert staged_file_action(text) != "approve"

    def test_status_text_does_not_write(self, sandbox):
        before = _snapshot()

        message = _chat()._authorized_code_file_approval(
            "تأیید عملکردی هنوز انجام نشده؛ اجرا نکن", PROJECT
        )

        assert "ذخیره شد" not in (message or "")
        assert _snapshot() == before
        assert not _written(sandbox["documents"])


# ===========================================================================
# 8. Explicit rejection still works
# ===========================================================================

class TestExplicitRejectionStillWorks:
    def test_rejection_discards_the_proposal(self, sandbox):
        message = _chat()._authorized_code_file_approval("رد کن", PROJECT)

        assert "رد شد" in message
        assert staging.pending_proposal(PROJECT) is None
        assert not _written(sandbox["documents"])

    def test_named_draft_rejection(self, sandbox):
        message = _chat()._authorized_code_file_approval(
            "پیش‌نویس فعلی فایل app.py را رد کن", PROJECT
        )

        assert "رد شد" in message
        assert staging.pending_proposal(PROJECT) is None


# ===========================================================================
# 9. Explicit approval with a fresh capability still works
# ===========================================================================

class TestExplicitApprovalStillWorks:
    def test_fresh_capability_writes_the_staged_bytes(self, writable_sandbox):
        proposal = writable_sandbox["proposal"]
        capability = staging.public_approval_capability(PROJECT, dict(AUTH))
        assert capability["token"] == proposal["approval_token"]

        message = _chat(capability=capability["token"])._authorized_code_file_approval(
            "تأیید می‌کنم، فایل app.py را ذخیره کن", PROJECT
        )

        assert "ذخیره شد" in message
        written = (writable_sandbox["documents"] / "code" / "app.py").read_text(
            encoding="utf-8"
        )
        assert written == SOURCE
        assert _sha(written) == proposal["digest"]

    @pytest.mark.parametrize("text", ["تأیید می‌کنم", "confirm", "approve and save"])
    def test_approval_forms_classify_as_approve(self, text):
        assert staged_file_action(text) == "approve"

    def test_missing_capability_still_refuses(self, sandbox):
        before = _snapshot()

        message = _chat()._authorized_code_file_approval(
            "تأیید می‌کنم، فایل app.py را ذخیره کن", PROJECT
        )

        assert "ذخیره شد" not in (message or "")
        assert _snapshot() == before
        assert not _written(sandbox["documents"])

    def test_expresses_approval_shares_the_classifier(self):
        from core.chat.code_file_staging_v1 import _expresses_approval

        assert _expresses_approval("تأیید می‌کنم") is True
        assert _expresses_approval("approve and save") is True
        assert _expresses_approval("تأیید عملکردی هنوز انجام نشده") is False
        assert _expresses_approval("تأیید نمی‌کنم") is False
        assert _expresses_approval("بعد از بررسی تأیید می‌کنم") is False
        assert _expresses_approval("عدد ۵ را وارد کن") is False


# ===========================================================================
# 10. Negative / interrogative / quoted / future mentions grant nothing
# ===========================================================================

class TestMentionsGrantNoAuthority:
    @pytest.mark.parametrize(
        "text",
        [
            "تأیید نمی‌کنم",
            "فعلاً ذخیره نکن",
            "بعد از بررسی تأیید می‌کنم",
            "آیا باید پیش‌نویس را رد کنم؟",
            "«رد کن» یعنی چه؟",
            "بدون تأیید من هیچ فایلی ذخیره نکن",
            "قبل از ذخیره تأیید من را بگیر",
            "do not approve",
            "رد نکن",
            "برای هر مرحله PASS یا FAIL گزارش کن",
            LIVE_VERIFICATION_REQUEST,
        ],
    )
    def test_no_state_change_and_no_authority(self, sandbox, text):
        before = _snapshot()

        message = _chat()._authorized_code_file_approval(text, PROJECT)

        # No write, no rejection, no capability consumption.
        assert "ذخیره شد" not in (message or "")
        assert staging.pending_proposal(PROJECT) is not None
        assert _snapshot() == before
        assert not _written(sandbox["documents"])

    def test_withheld_mention_gets_a_truthful_answer(self, sandbox):
        message = _chat()._authorized_code_file_approval(
            "بدون تأیید من هیچ فایلی ذخیره نکن", PROJECT
        )

        assert "اجازهٔ ذخیره نمی‌دهد" in message
        assert staging.pending_proposal(PROJECT) is not None
