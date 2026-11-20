# tests/test_coder_history_reuse_routing_v1.py
"""CODER-HISTORY-REUSE-01 — restoring source that was already displayed.

Measured 2026-10-26 in project_20f920b5 after a restart: the user asked to
bring back the ``app.py`` draft already shown in the conversation and
ArchitectOS answered ``no_images_in_session``.

Four separate defects had to line up:

1. the text-only image-reference boundary skipped only creation turns, so the
   restore request was classified as an image reference;
2. the code-capability gate knew creation, repair and approval — not reuse;
3. ``_authorized_code_file_creation`` demanded creation/generation vocabulary
   before history could be consulted;
4. ``_source_code_from_history_or_coder`` read the substring "جدید" as proof of
   fresh generation, so «کد جدید تولید نکن» *invoked* the coding model.

A restore turn must stage the recovered bytes as a NEW unsaved proposal, with
no model call, no write, no approval and no execution.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import os
import subprocess
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

import app as application
import core.chat.chat_architect as chat_module
import core.chat.code_file_staging_v1 as staging
import core.chat.project_code_file_writer_v1 as writer
import core.project.conversation_store_v1 as store_module
import core.vision.vision_provider_ollama_v1 as provider_module
from core.chat.chat_architect import ChatArchitect
from core.chat.session_registry_v1 import session_registry
from core.llm.llm_gateway import LLMGateway
from core.project.project_workspace_v1 import project_workspace
from core.vision.image_session_v1 import resolve_session_reference


#: The exact live user turn (message 4 of project_20f920b5).
LIVE_RESTORE_REQUEST = (
    "همان کد قبلی فایل app.py را که در همین گفت‌وگو نمایش داده بودی، بدون "
    "تغییر از تاریخچه همین پروژه بازیابی کن و برای ذخیره پیشنهاد بده.\n"
    "\n"
    "کد جدید تولید نکن. فقط پیش‌نویس را همراه با SHA-256 نمایش بده. هیچ فایلی "
    "را روی دیسک ننویس و هیچ کدی را اجرا نکن."
)

LIVE_RESTORE_REQUEST_EN = (
    "Restore the previous app.py code from this project's history unchanged and "
    "propose it for saving.\n"
    "\n"
    "Do not generate new code. Only show the draft with its SHA-256. Do not "
    "write any file to disk and do not execute any code."
)

#: The source the assistant already displayed earlier in the conversation.
#: No trailing newline: the existing extractor strips them, and the restored
#: bytes must match what it returns exactly.
HISTORY_SOURCE = (
    "import tkinter as tk\n"
    "\n"
    "\n"
    "class Calculator:\n"
    "    def __init__(self, root):\n"
    "        self.root = root\n"
    "        self.operand1 = 0\n"
    "        self.operator = None\n"
    "\n"
    "    def on_operator(self, op):\n"
    "        # remember the operator\n"
    "        self.operand1 = 0\n"
    "        self.operator = op"
)

_HISTORY_MESSAGE = (
    "پیش‌نویس فایل «app.py» ساخته شد و هنوز هیچ فایلی نوشته نشده است.\n"
    "SHA-256: 0000000000000000000000000000000000000000000000000000000000000000\n\n"
    "پیش‌نمایش:\n```python\n" + HISTORY_SOURCE + "\n```\n"
)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _RecordedCoder:
    """Records every prompt. A call here is a test failure, not a fallback."""

    def __init__(self):
        self.calls = []

    def generate(self, prompt, **_kwargs):
        self.calls.append(str(prompt))
        return "```python\nGENERATED = True\n```"


class _HistoryStore:
    """A conversation store whose history is fixed by the test.

    Unknown attributes delegate to the real store, so writeback keeps working
    against the isolated projects root.
    """

    def __init__(self, messages, real):
        self._messages = messages
        self._real = real

    def load(self, session_id):
        return {"messages": [dict(item) for item in self._messages]}

    def __getattr__(self, name):
        return getattr(self._real, name)


def _forbidden(label):
    def _raise(*_args, **_kwargs):
        raise AssertionError("unexpected call: " + label)

    return _raise


def _turn(text, session_id):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return application.chat.handle(
                text,
                context={"session_id": session_id},
            )
    finally:
        session_registry.end()


def _result_text(result):
    return str((result or {}).get("result") or "")


@pytest.fixture()
def runtime(tmp_path, monkeypatch, request):
    projects = tmp_path / "projects"
    trash = tmp_path / "trash"
    projects.mkdir()
    trash.mkdir()
    monkeypatch.setattr(project_workspace, "projects_root", str(projects))
    monkeypatch.setattr(project_workspace, "trash_root", str(trash))

    real_store = store_module.conversation_store
    monkeypatch.setattr(
        store_module,
        "conversation_store",
        _HistoryStore(
            [
                {"role": "user", "text": "یک فایل app.py بساز."},
                {"role": "assistant", "text": _HISTORY_MESSAGE},
            ],
            real_store,
        ),
    )

    coder = _RecordedCoder()
    monkeypatch.setattr(chat_module, "coder_gateway", lambda: coder)
    monkeypatch.setattr(LLMGateway, "generate", _forbidden("general_llm"))
    monkeypatch.setattr(
        provider_module.OllamaVisionProvider, "analyze", _forbidden("vision")
    )
    monkeypatch.setattr(
        provider_module.OllamaVisualObserver, "observe", _forbidden("observer")
    )
    monkeypatch.setattr(
        provider_module.OllamaTextNormalizer,
        "normalize",
        _forbidden("vision_normalizer"),
    )
    monkeypatch.setattr(
        application.chat.render_runtime, "render", _forbidden("render")
    )
    monkeypatch.setattr(
        writer, "create_project_code_file", _forbidden("file_write")
    )
    monkeypatch.setattr(subprocess, "run", _forbidden("subprocess.run"))
    monkeypatch.setattr(subprocess, "Popen", _forbidden("subprocess.Popen"))

    stages = []
    real_stage = staging.stage_code_file

    def _stage(*args, **kwargs):
        proposal = real_stage(*args, **kwargs)
        stages.append(proposal)
        return proposal

    monkeypatch.setattr(staging, "stage_code_file", _stage)
    staging.reset_staging()

    digest = hashlib.sha256(request.node.nodeid.encode("utf-8")).hexdigest()[:16]
    session_id = "project_%s" % digest

    yield {
        "coder": coder,
        "projects": projects,
        "session_id": session_id,
        "stages": stages,
    }

    staging.reset_staging()
    session_registry.end()


@pytest.fixture()
def empty_history(tmp_path, monkeypatch):
    """The same isolation, but the project has no code in its history."""

    projects = tmp_path / "projects"
    trash = tmp_path / "trash"
    projects.mkdir()
    trash.mkdir()
    monkeypatch.setattr(project_workspace, "projects_root", str(projects))
    monkeypatch.setattr(project_workspace, "trash_root", str(trash))

    real_store = store_module.conversation_store
    monkeypatch.setattr(
        store_module,
        "conversation_store",
        _HistoryStore(
            [
                {"role": "user", "text": "سلام"},
                {"role": "assistant", "text": "سلام! چطور می‌توانم کمک کنم؟"},
            ],
            real_store,
        ),
    )

    coder = _RecordedCoder()
    monkeypatch.setattr(chat_module, "coder_gateway", lambda: coder)
    monkeypatch.setattr(
        writer, "create_project_code_file", _forbidden("file_write")
    )
    staging.reset_staging()

    yield {"coder": coder, "session_id": "project_empty_history", "projects": projects}

    staging.reset_staging()
    session_registry.end()


# ===========================================================================
# 1. The predicate — a restore turn, and only a restore turn
# ===========================================================================

class TestHistoryReusePredicate:
    def test_live_request_is_a_reuse_turn(self):
        chat = object.__new__(ChatArchitect)
        chat.context = {}

        assert chat._code_history_reuse_turn(LIVE_RESTORE_REQUEST) is True

    def test_english_equivalent_is_a_reuse_turn(self):
        chat = object.__new__(ChatArchitect)
        chat.context = {}

        assert chat._code_history_reuse_turn(LIVE_RESTORE_REQUEST_EN) is True

    @pytest.mark.parametrize(
        "text,why",
        [
            ("تصویر قبلی را تحلیل کن", "previous image"),
            ("رندر قبلی رو توضیح بده", "previous render"),
            ("این کد پایتون چه کار می‌کند؟", "ordinary python question"),
            ("یک نسخه جدید و کامل تولید کن (app.py)", "positive new version"),
            ("همان کد قبلی را دوباره تولید کن", "regenerate the old code"),
            ("یک ویلای دو طبقه بساز", "architectural"),
            ("سلام، حالت چطوره؟", "chat"),
            ("", "empty"),
        ],
    )
    def test_non_reuse_turns_are_not_classified_as_reuse(self, text, why):
        chat = object.__new__(ChatArchitect)
        chat.context = {}

        assert chat._code_history_reuse_turn(text) is False, why

    def test_live_request_prohibits_generation(self):
        chat = object.__new__(ChatArchitect)
        chat.context = {}

        assert chat._code_generation_prohibited(LIVE_RESTORE_REQUEST) is True
        assert chat._code_generation_prohibited(
            "یک نسخه جدید و کامل تولید کن (app.py)"
        ) is False


# ===========================================================================
# 2. End-to-end — the live turn restores from history, no inference
# ===========================================================================

class TestLiveRestore:
    def test_no_image_reference_error(self, runtime):
        result = _turn(LIVE_RESTORE_REQUEST, runtime["session_id"])

        assert "no_images_in_session" not in _result_text(result)

    def test_coder_is_never_called(self, runtime):
        _turn(LIVE_RESTORE_REQUEST, runtime["session_id"])

        assert runtime["coder"].calls == [], (
            "the user forbade new generation; the model must not be invoked"
        )

    def test_source_comes_from_the_active_project_history(self, runtime):
        _turn(LIVE_RESTORE_REQUEST, runtime["session_id"])

        assert len(runtime["stages"]) == 1
        assert runtime["stages"][0]["origin"] == "conversation_history"

    def test_staged_source_is_byte_identical_to_the_recovered_source(self, runtime):
        _turn(LIVE_RESTORE_REQUEST, runtime["session_id"])

        proposal = staging.pending_proposal(runtime["session_id"])
        assert proposal["content"] == HISTORY_SOURCE
        assert proposal["digest"] == _sha(HISTORY_SOURCE)

    def test_reply_shows_the_digest_and_writes_nothing(self, runtime):
        result = _turn(LIVE_RESTORE_REQUEST, runtime["session_id"])
        text = _result_text(result)

        assert "SHA-256" in text
        assert _sha(HISTORY_SOURCE) in text
        assert "نوشته نشده" in text
        assert not list(runtime["projects"].rglob("app.py"))

    def test_proposal_is_awaiting_approval(self, runtime):
        _turn(LIVE_RESTORE_REQUEST, runtime["session_id"])

        proposal = staging.pending_proposal(runtime["session_id"])
        assert proposal["status"] == "awaiting_approval"
        assert proposal["filename"] == "app.py"

    def test_english_equivalent_restores_the_same_source(self, runtime):
        _turn(LIVE_RESTORE_REQUEST_EN, runtime["session_id"])

        assert runtime["coder"].calls == []
        proposal = staging.pending_proposal(runtime["session_id"])
        assert proposal["content"] == HISTORY_SOURCE
        assert proposal["origin"] == "conversation_history"

    def test_trusted_authorization_binds_the_restored_proposal(self, runtime):
        """The restore goes through the existing trusted staging path."""

        session_id = runtime["session_id"]
        authorization = {
            "trusted": True,
            "actor_id": "local_user",
            "session_id": "sess_history",
            "project_id": session_id,
        }

        chat = object.__new__(ChatArchitect)
        chat.context = {"trusted_local_authorization": authorization}

        message = chat._authorized_code_file_creation(LIVE_RESTORE_REQUEST, session_id)

        assert "SHA-256" in message
        assert runtime["coder"].calls == []

        proposal = staging.pending_proposal(session_id)
        assert proposal["content"] == HISTORY_SOURCE
        assert proposal["authorization_binding"] == {
            "actor_id": "local_user",
            "session_id": "sess_history",
            "project_id": session_id,
        }
        # A bound proposal exposes no token, and nothing was written.
        assert proposal["approval_token"] is None
        assert not list(runtime["projects"].rglob("app.py"))


class TestNoHistoricalSource:
    def test_reports_the_truth_without_calling_the_model(self, empty_history):
        result = _turn(LIVE_RESTORE_REQUEST, empty_history["session_id"])
        text = _result_text(result)

        assert "no_images_in_session" not in text
        assert "تاریخچهٔ همین پروژه کد پایتونی پیدا نشد" in text
        assert empty_history["coder"].calls == []
        assert staging.pending_proposal(empty_history["session_id"]) is None
        assert not list(empty_history["projects"].rglob("*.py"))


# ===========================================================================
# 3. Boundaries — no approval, no rejection, no overwrite
# ===========================================================================

class TestNoAccidentalApproval:
    def test_restore_never_approves_a_pending_proposal(self, runtime):
        session_id = runtime["session_id"]

        seeded = staging.stage_code_file(
            project_id=session_id,
            filename="app.py",
            content="seed = 1\n",
            origin="seed",
        )
        assert seeded["status"] == "awaiting_approval"

        chat = object.__new__(ChatArchitect)
        chat.context = {}

        # The reuse turn is not an approval turn at all.
        assert chat._code_history_reuse_turn(LIVE_RESTORE_REQUEST) is True
        assert chat._authorized_code_file_approval(
            LIVE_RESTORE_REQUEST, session_id
        ) is None

        # And the pending proposal is untouched, not approved, not overwritten.
        live = staging.pending_proposal(session_id)
        assert live["content"] == "seed = 1\n"
        assert live["origin"] == "seed"
        assert not list(runtime["projects"].rglob("app.py"))

    def test_restore_does_not_silently_replace_a_pending_proposal(self, runtime):
        session_id = runtime["session_id"]

        staging.stage_code_file(
            project_id=session_id,
            filename="app.py",
            content="seed = 1\n",
            origin="seed",
        )

        chat = object.__new__(ChatArchitect)
        chat.context = {}

        message = chat._authorized_code_file_creation(LIVE_RESTORE_REQUEST, session_id)

        assert "در انتظار تأیید شماست" in message
        assert staging.pending_proposal(session_id)["content"] == "seed = 1\n"
        assert runtime["coder"].calls == []


class TestImageBoundaryUnchanged:
    def test_previous_image_still_reaches_the_image_resolver(self, runtime):
        result = _turn("تصویر اول را تحلیل کن", runtime["session_id"])

        assert "no_images_in_session" in _result_text(result)
        assert runtime["coder"].calls == []
        assert runtime["stages"] == []

    def test_previous_render_question_is_not_a_code_reuse_turn(self):
        chat = object.__new__(ChatArchitect)
        chat.context = {}

        assert chat._code_history_reuse_turn("رندر قبلی رو توضیح بده") is False

    def test_resolver_still_reports_no_images_for_a_restore_like_phrase(self):
        """The predicate — not a weakened resolver — is what protects the turn."""

        reference = resolve_session_reference(
            "project_history_reuse_diagnostic",
            "تصویر قبلی را بازیابی کن",
        )
        assert reference["status"] == "unresolved"
        assert reference["reason"] == "no_images_in_session"


# ===========================================================================
# 4. Negative generation wording
# ===========================================================================

class TestGenerationProhibition:
    def test_negative_wording_alone_does_not_invoke_the_coder(self, runtime):
        session_id = runtime["session_id"]

        chat = object.__new__(ChatArchitect)
        chat.context = {}

        text = "کد جدید تولید نکن."

        source, origin = chat._source_code_from_history_or_coder(
            text, session_id, "app.py"
        )

        assert source is None
        assert origin is None
        assert runtime["coder"].calls == []

    def test_positive_new_version_still_reaches_the_coder(self, runtime):
        session_id = runtime["session_id"]

        chat = object.__new__(ChatArchitect)
        chat.context = {}

        source, origin = chat._source_code_from_history_or_coder(
            "یک نسخه جدید و کامل تولید کن (app.py).", session_id, "app.py"
        )

        assert origin == "coder_model"
        assert source is not None
        assert len(runtime["coder"].calls) == 1

    @pytest.mark.parametrize(
        "text,why",
        [
            ("برنامه را اجرا نکن و EXE نساز.", "packaging prohibition"),
            ("هیچ فایلی را روی دیسک ننویس و هیچ کدی را اجرا نکن.", "write prohibition"),
            ("کد را اجرا نکن.", "execution prohibition"),
            ("بدون تأیید من فایل را ذخیره نکن.", "save prohibition"),
        ],
    )
    def test_non_generation_prohibitions_are_not_generation_prohibitions(
        self, text, why
    ):
        """A prohibition on packaging/writing/running is not one on generating.

        Measured 2026-10-26: the real build request in project_f043688f ends
        with «EXE نساز»; a bare "نساز" marker read that as "do not generate"
        and stopped the coding model from ever being called.
        """

        chat = object.__new__(ChatArchitect)
        chat.context = {}

        assert chat._code_generation_prohibited(text) is False, why

    def test_packaging_prohibition_does_not_block_generation(self, runtime):
        session_id = runtime["session_id"]

        chat = object.__new__(ChatArchitect)
        chat.context = {}

        text = (
            "یک برنامه جدید بساز (فایل app.py)؛ اجرا نکن و EXE نساز."
        )

        source, origin = chat._source_code_from_history_or_coder(
            text, session_id, "app.py"
        )

        assert origin == "coder_model"
        assert source is not None
        assert len(runtime["coder"].calls) == 1



# ===========================================================================
# 5. Existing paths unaffected
# ===========================================================================

class TestExistingPathsUnaffected:
    def test_creation_still_calls_the_coder_once(self, runtime):
        result = _turn("یک برنامه جدید بساز (فایل app.py).", runtime["session_id"])

        assert len(runtime["coder"].calls) == 1
        assert len(runtime["stages"]) == 1
        assert "SHA-256" in _result_text(result)
        assert staging.pending_proposal(runtime["session_id"])["origin"] == "coder_model"

    def test_repair_predicate_is_unchanged(self):
        chat = object.__new__(ChatArchitect)
        chat.context = {}

        repair = (
            "فقط باگ متد on_operator را در پیش‌نویس فعلی اصلاح کن و بقیه را "
            "تغییر نده."
        )

        assert chat._code_repair_turn(repair) is True
        assert chat._code_history_reuse_turn(repair) is False

    def test_approval_and_rejection_still_resolve(self, runtime):
        session_id = runtime["session_id"]

        chat = object.__new__(ChatArchitect)
        chat.context = {}

        assert chat._code_history_reuse_turn(
            "تأیید می‌کنم، همین فایل را ذخیره کن"
        ) is False
        assert chat._code_history_reuse_turn("رد کن") is False

        assert chat._authorized_code_file_approval("رد کن", session_id) is not None
