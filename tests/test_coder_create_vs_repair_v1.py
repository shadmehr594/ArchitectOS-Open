# tests/test_coder_create_vs_repair_v1.py
"""CODER-CREATE-VS-REPAIR-01 — a CREATE request that mentions a bug is not a repair.

Measured 2026-10-26 in project_aff545c4: the user asked for a NEW ``app.py``
whose ``Calculator.on_operator`` contains a deliberate defect. The request
matched the repair vocabulary accidentally —

* "باگ" was treated as a repair ACTION although it is a noun,
* "پیش‌نویس" was treated as an existing-draft TARGET although it named the
  desired OUTPUT ("فقط پیش‌نویس را بساز"),
* "فقط" satisfied the scope restriction,

— so ``_code_repair_turn`` returned True, the repair handler ran first, and it
refused with ``no_pending_proposal`` before any model was called.

The fix is ACTION + TARGET semantics:

* only a repair VERB counts as a repair action;
* a draft word only counts as a target when an EXISTENCE marker sits near it;
* producing a NEW artifact outranks incidental defect vocabulary.

``_code_file_creation_turn`` is NOT given universal precedence: it also returns
True for the genuine repair turn (its generation vocabulary contains
"اصلاح کن"), so the two are separated by the repair predicate, not by order.

Every model call here is scripted. Nothing is written, executed or packaged.
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


# ---------------------------------------------------------------------------
# The EXACT live turns (verbatim, ZWNJ included) — project_aff545c4
# ---------------------------------------------------------------------------

LIVE_CREATE_REQUEST = 'یک فایل Python به نام app.py با کلاس Calculator بساز.\n\nکلاس باید دارای سه متد `__init__`، `on_digit` و `on_operator` باشد.\n\nدر متد `on_operator` عمداً یک باگ قرار بده که با انتخاب یا تعویض عملگر، مقدار عملوند اول صفر شود.\n\nمتدها را به\u200cصورت چندخطی بنویس و سایر قسمت\u200cهای برنامه را سالم نگه دار.\n\nکد منبع را داخل متغیر رشته\u200cای تکرار نکن و هیچ دستور محاسبه یا چاپ SHA-256 داخل فایل قرار نده؛ خود ArchitectOS هش را نمایش می\u200cدهد.\n\nفقط پیش\u200cنویس را بساز و نمایش بده. هیچ فایلی را ذخیره یا اجرا نکن.'

LIVE_REPAIR_REQUEST = 'فقط باگ متد `Calculator.on_operator` را در پیش\u200cنویس فعلی `app.py` اصلاح کن.\n\nهنگام انتخاب یا تغییر عملگر، مقدار عملوند اول باید حفظ شود.\n\nفقط بدنه همین متد را اصلاح کن؛ هیچ تابع، import یا بخش دیگری را تغییر نده.\n\nSHA-256 جدید و diff تغییرات را نمایش بده. فایل را ذخیره یا اجرا نکن.'

CREATE_REQUEST_EN = (
    "Create a new Python file app.py with a Calculator class. "
    "Deliberately put a bug in Calculator.on_operator so the first operand is "
    "reset when the operator changes. Keep the other methods intact. "
    "Only build and show the draft; do not save or execute anything."
)

REPAIR_REQUEST_EN = (
    "Fix only the bug in Calculator.on_operator in the current pending draft "
    "of app.py. Keep everything else unchanged."
)


# ---------------------------------------------------------------------------
# Scripted model + isolation
# ---------------------------------------------------------------------------

BASE_SOURCE = (
    "import tkinter as tk\n"
    "\n"
    "\n"
    "class Calculator:\n"
    "    def __init__(self, root):\n"
    "        self.root = root\n"
    "        self.operand1 = 0\n"
    "        self.operator = None\n"
    "\n"
    "    def on_digit(self, digit):\n"
    "        # digits build the operand\n"
    "        self.operand1 = self.operand1 * 10 + digit\n"
    "\n"
    "    def on_operator(self, op):\n"
    "        # Bug: this resets the first operand\n"
    "        self.operand1 = 0\n"
    "        self.operator = op"
)

REPAIRED_SOURCE = BASE_SOURCE.replace(
    "        # Bug: this resets the first operand\n"
    "        self.operand1 = 0\n",
    "        # keep the first operand across operator changes\n"
    "        if self.operand1 == 0:\n"
    "            self.operand1 = self.operand1\n",
)

HISTORY_SOURCE = "print('history draft')\n"


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _ScriptedCoder:
    """Returns the scripted sources in order and records every prompt."""

    def __init__(self, sources):
        self.sources = list(sources)
        self.calls = []

    def generate(self, prompt, **_kwargs):
        self.calls.append(str(prompt))
        source = self.sources.pop(0) if self.sources else BASE_SOURCE
        return "```python\n%s\n```" % source


class _HistoryStore:
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
                text, context={"session_id": session_id}
            )
    finally:
        session_registry.end()


def _result_text(result):
    return str((result or {}).get("result") or "")


def _isolate(tmp_path, monkeypatch, messages, sources):
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
        _HistoryStore(messages, real_store),
    )

    coder = _ScriptedCoder(sources)
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

    return {"coder": coder, "projects": projects, "stages": stages}


@pytest.fixture()
def runtime(tmp_path, monkeypatch, request):
    digest = hashlib.sha256(request.node.nodeid.encode("utf-8")).hexdigest()[:16]
    session_id = "project_%s" % digest

    context = _isolate(
        tmp_path,
        monkeypatch,
        [
            {"role": "user", "text": "سلام"},
            {"role": "assistant", "text": "سلام! چطور می‌توانم کمک کنم؟"},
        ],
        [BASE_SOURCE, REPAIRED_SOURCE],
    )
    context["session_id"] = session_id

    yield context

    staging.reset_staging()
    session_registry.end()


@pytest.fixture()
def runtime_with_history(tmp_path, monkeypatch):
    context = _isolate(
        tmp_path,
        monkeypatch,
        [
            {"role": "user", "text": "یک فایل app.py بساز."},
            {
                "role": "assistant",
                "text": "پیش‌نمایش:\n```python\n" + HISTORY_SOURCE + "```\n",
            },
        ],
        [BASE_SOURCE],
    )
    context["session_id"] = "project_create_vs_repair_history"

    yield context

    staging.reset_staging()
    session_registry.end()


def _trusted(session_id):
    chat = object.__new__(ChatArchitect)
    chat.context = {
        "trusted_local_authorization": {
            "trusted": True,
            "actor_id": "local_user",
            "session_id": "sess_create_vs_repair",
            "project_id": session_id,
        }
    }
    return chat


def _plain():
    chat = object.__new__(ChatArchitect)
    chat.context = {}
    return chat


# ===========================================================================
# 1. The exact live texts are recorded verbatim
# ===========================================================================

class TestRecordedLiveTurns:
    def test_live_texts_match_the_recorded_conversation(self):
        import json

        path = os.path.join(
            _PROJECT_ROOT,
            "data",
            "projects",
            "project_aff545c4",
            "conversations",
            "chat.json",
        )
        if not os.path.isfile(path):
            pytest.skip("project_aff545c4 conversation data not present")

        with open(path, encoding="utf-8") as handle:
            messages = json.load(handle)["messages"]

        assert messages[0]["text"] == LIVE_CREATE_REQUEST
        assert messages[2]["text"] == LIVE_REPAIR_REQUEST


# ===========================================================================
# 2. ACTION + TARGET semantics
# ===========================================================================

class TestCreateIsNotARepair:
    def test_live_create_request_is_not_a_repair_turn(self):
        """The confirmed defect: this used to return True."""

        assert _plain()._code_repair_turn(LIVE_CREATE_REQUEST) is False

    def test_live_create_request_still_references_a_draft_word(self):
        """The word "پیش‌نویس" is present — it names the OUTPUT, not a target."""

        assert "پیش‌نویس" in LIVE_CREATE_REQUEST
        assert _plain()._existing_draft_reference(LIVE_CREATE_REQUEST) is False

    def test_live_repair_request_is_a_repair_turn(self):
        assert _plain()._code_repair_turn(LIVE_REPAIR_REQUEST) is True

    def test_live_repair_request_names_the_existing_draft(self):
        assert _plain()._existing_draft_reference(LIVE_REPAIR_REQUEST) is True

    def test_both_turns_match_the_creation_predicate(self):
        """Why precedence alone cannot work.

        ``_code_file_creation_turn`` returns True for BOTH turns because its
        generation vocabulary contains «اصلاح کن». Giving creation universal
        precedence would therefore turn every genuine repair into a new file.
        """

        chat = _plain()

        assert chat._code_file_creation_turn(LIVE_CREATE_REQUEST) is True
        assert chat._code_file_creation_turn(LIVE_REPAIR_REQUEST) is True
        # ... and the repair predicate is what separates them.
        assert chat._code_repair_turn(LIVE_CREATE_REQUEST) is False
        assert chat._code_repair_turn(LIVE_REPAIR_REQUEST) is True

    def test_english_create_with_a_deliberate_bug_is_not_a_repair(self):
        assert _plain()._code_repair_turn(CREATE_REQUEST_EN) is False

    def test_english_repair_is_a_repair(self):
        assert _plain()._code_repair_turn(REPAIR_REQUEST_EN) is True

    @pytest.mark.parametrize(
        "text",
        [
            "یک برنامه جدید بساز که عمداً یک باگ داشته باشد (app.py).",
            "یک فایل Python بساز و در آن باگ بگذار (app.py).",
            "Create app.py and deliberately include a bug in the operator.",
            "یک فایل جدید app.py ایجاد کن؛ باگ عمدی در on_operator بگذار.",
        ],
    )
    def test_new_application_mentioning_a_bug_is_creation(self, text):
        assert _plain()._code_repair_turn(text) is False

    @pytest.mark.parametrize(
        "text",
        [
            "این فایل را اصلاح کن",
            "در پیش‌نویس فعلی باگ را اصلاح کن",
            "فایل فعلی را اصلاح کن و بقیه را تغییر نده",
        ],
    )
    def test_ambiguous_turns_are_not_repairs(self, text):
        assert _plain()._code_repair_turn(text) is False

    def test_negations_do_not_change_the_classification(self):
        chat = _plain()

        # "EXE نساز" is a packaging prohibition; it is not a repair and it is
        # not a generation prohibition either.
        assert chat._code_repair_turn("یک برنامه بساز (app.py)؛ EXE نساز.") is False
        assert chat._code_generation_prohibited("یک برنامه بساز (app.py)؛ EXE نساز.") is False
        # The live CREATE forbids writing and executing, not generating.
        assert chat._code_generation_prohibited(LIVE_CREATE_REQUEST) is False
        assert chat._staging_action_turn(LIVE_CREATE_REQUEST) is False
        assert chat._code_history_reuse_turn(LIVE_CREATE_REQUEST) is False


# ===========================================================================
# 3. End-to-end through the chat pipeline
# ===========================================================================

class TestLiveCreateReachesCoder:
    def test_coder_called_exactly_once(self, runtime):
        _turn(LIVE_CREATE_REQUEST, runtime["session_id"])

        assert len(runtime["coder"].calls) == 1

    def test_stages_a_new_app_draft_with_digest(self, runtime):
        result = _turn(LIVE_CREATE_REQUEST, runtime["session_id"])
        text = _result_text(result)

        assert len(runtime["stages"]) == 1
        proposal = staging.pending_proposal(runtime["session_id"])
        assert proposal["filename"] == "app.py"
        assert proposal["status"] == "awaiting_approval"
        assert proposal["origin"] == "coder_model"
        assert proposal["content"] == BASE_SOURCE
        assert proposal["digest"] == _sha(BASE_SOURCE)
        assert "SHA-256" in text
        assert "no_pending_proposal" not in text
        assert "no_images_in_session" not in text

    def test_nothing_is_saved_or_executed(self, runtime):
        _turn(LIVE_CREATE_REQUEST, runtime["session_id"])

        assert not list(runtime["projects"].rglob("app.py"))
        assert not list(runtime["projects"].rglob("*.py"))


class TestSubsequentRepairReachesSurgicalRepair:
    def test_create_then_repair_completes(self, runtime):
        session_id = runtime["session_id"]
        chat = _trusted(session_id)

        created = chat._authorized_code_file_creation(
            LIVE_CREATE_REQUEST, session_id
        )
        assert "SHA-256" in created
        assert len(runtime["coder"].calls) == 1

        first = staging.pending_proposal(session_id)
        assert first["content"] == BASE_SOURCE

        repaired = chat._authorized_code_repair(LIVE_REPAIR_REQUEST, session_id)

        assert len(runtime["coder"].calls) == 2
        assert "FAILED BEHAVIOUR" in runtime["coder"].calls[1]
        assert "no_pending_proposal" not in repaired
        assert "اصلاح شد" in repaired

        live = staging.pending_proposal(session_id)
        assert live["content"] == REPAIRED_SOURCE
        assert live["digest"] == _sha(REPAIRED_SOURCE)
        assert live["digest"] != first["digest"]
        assert live["repair"]["target"] == "Calculator.on_operator"
        assert live["repair"]["representation"] == "spliced_body"
        assert not list(runtime["projects"].rglob("app.py"))

    def test_repair_without_a_pending_draft_refuses_without_inference(self, runtime):
        session_id = runtime["session_id"]
        chat = _trusted(session_id)

        message = chat._authorized_code_repair(LIVE_REPAIR_REQUEST, session_id)

        assert "no_pending_proposal" in message
        assert runtime["coder"].calls == []
        assert staging.pending_proposal(session_id) is None


class TestPendingGuardPreserved:
    def test_new_creation_with_a_pending_draft_is_blocked_without_inference(
        self, runtime
    ):
        session_id = runtime["session_id"]
        chat = _trusted(session_id)

        chat._authorized_code_file_creation(LIVE_CREATE_REQUEST, session_id)
        assert len(runtime["coder"].calls) == 1
        before = staging.pending_proposal(session_id)

        message = chat._authorized_code_file_creation(
            LIVE_CREATE_REQUEST, session_id
        )

        assert "در انتظار تأیید شماست" in message
        assert len(runtime["coder"].calls) == 1, "no inference may be spent"
        after = staging.pending_proposal(session_id)
        assert after["digest"] == before["digest"]


# ===========================================================================
# 4. Preserved routes
# ===========================================================================

class TestPreservedRoutes:
    def test_history_reuse_does_not_generate(self, runtime_with_history):
        text = (
            "همان کد قبلی فایل app.py را که در همین گفت‌وگو نمایش داده بودی، "
            "بدون تغییر از تاریخچه همین پروژه بازیابی کن و برای ذخیره پیشنهاد "
            "بده. کد جدید تولید نکن. فقط پیش‌نویس را با SHA-256 نمایش بده."
        )

        _turn(text, runtime_with_history["session_id"])

        assert runtime_with_history["coder"].calls == []
        proposal = staging.pending_proposal(runtime_with_history["session_id"])
        assert proposal["origin"] == "conversation_history"
        assert proposal["content"] == HISTORY_SOURCE.rstrip("\n")

    def test_previous_image_stays_in_the_image_route(self, runtime):
        result = _turn("تصویر اول را تحلیل کن", runtime["session_id"])

        assert "no_images_in_session" in _result_text(result)
        assert runtime["coder"].calls == []
        assert runtime["stages"] == []

    def test_approval_turn_is_neither_create_nor_repair(self, runtime):
        chat = _plain()

        for text in (
            "تأیید می‌کنم، همین فایل را ذخیره کن",
            "رد کن",
        ):
            assert chat._code_repair_turn(text) is False
            assert chat._code_history_reuse_turn(text) is False

    def test_rejection_still_resolves(self, runtime):
        session_id = runtime["session_id"]

        staging.stage_code_file(
            project_id=session_id,
            filename="app.py",
            content=BASE_SOURCE,
            origin="seed",
        )

        message = _plain()._authorized_code_file_approval("رد کن", session_id)

        assert "رد شد" in message
        assert staging.pending_proposal(session_id) is None

    def test_existing_creation_request_still_works(self, runtime):
        result = _turn("یک برنامه جدید بساز (فایل app.py).", runtime["session_id"])

        assert len(runtime["coder"].calls) == 1
        assert "SHA-256" in _result_text(result)
        assert staging.pending_proposal(runtime["session_id"]) is not None
