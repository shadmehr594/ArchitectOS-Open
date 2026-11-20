# tests/test_coder_repair_pending_v1.py
"""CODER-REPAIR-01 — trusted repair of the PENDING proposal.

The defect: ``_authorized_code_file_creation`` correctly refuses to replace a
proposal that is awaiting approval, so a draft the user could SEE was broken
had no repair path at all. The only options were approve the broken bytes or
reject and regenerate the whole file.

The repair branch is trusted, scoped and non-authoritative:

  * the base is the server-owned pending proposal (never history, never a
    browser-supplied source);
  * the base is bound by project + actor + session + digest + REVISION;
  * the candidate must change EXACTLY ONE function BODY, its declaration must
    survive intact, and every byte outside that span must be identical —
    decided by the server from the bytes it received, never by the model;
  * a missing / malformed static review fails CLOSED;
  * every refusal leaves the original proposal untouched;
  * a successful replacement issues a NEW capability for the NEW digest, so
    the old save approval cannot write the new bytes, and no execution,
    packaging or consent authority is granted.

Nothing in this module runs Docker, imports a model-generated file, writes a
project file, or calls a real model. The real project conversation is only ever
READ, and only through a fixture that skips when the data is absent.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import sys
import textwrap
import threading

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from core.chat.chat_architect import ChatArchitect
import core.chat.code_file_staging_v1 as staging
from core.chat.code_file_staging_v1 import (
    infer_changed_scope,
    repair_base,
    replace_staged_file,
    resolve_named_targets,
)
from core.execution import draft_verification_v1 as dv


PROJECT = "project_repair_tests"
ACTOR = "local_user"
SESSION = "sess_repair"

AUTH = {
    "trusted": True,
    "actor_id": ACTOR,
    "session_id": SESSION,
    "project_id": PROJECT,
}


# ---------------------------------------------------------------------------
# Fixtures — a calculator draft whose ``on_operator`` loses the first operand
# ---------------------------------------------------------------------------

BASE_SOURCE = (
    "import tkinter as tk\n"
    "\n"
    "\n"
    "class Calculator:\n"
    "    def __init__(self, root):\n"
    "        self.root = root\n"
    "        self.result = 0\n"
    "        self.current = \"\"\n"
    "        self.pending = None\n"
    "\n"
    "    def on_operator(self, operator):\n"
    "        self.result = 0\n"
    "        self.pending = operator\n"
    "\n"
    "    def on_digit(self, digit):\n"
    "        self.current = self.current + digit\n"
    "\n"
    "    def build_layout(self):\n"
    "        tk.Label(self.root, text=\"0\").pack()\n"
    "\n"
    "    def on_key(self, event):\n"
    "        return self.on_digit(event.char)\n"
)

#: Only ``Calculator.on_operator`` differs.
REPAIRED_SOURCE = BASE_SOURCE.replace(
    "        self.result = 0\n"
    "        self.pending = operator\n",
    "        if self.pending is None:\n"
    "            self.result = float(self.current or 0)\n"
    "        self.pending = operator\n",
)

#: The flagship user turn — no function is named, so the server infers scope.
REPAIR_TEXT_EN = (
    "Fix only the operator replacement bug in the current pending calculator "
    "draft. Keep everything else unchanged."
)

REPAIR_TEXT_FA = (
    "فقط باگ جایگزینی عملگر را در پیش‌نویس فعلی ماشین‌حساب اصلاح کن. "
    "بقیهٔ موارد را تغییر نده."
)

#: The same turn with an explicit target, so scope can only be NARROWED.
REPAIR_TEXT_NAMED = (
    "باگ متد on_operator را در پیش‌نویس فعلی اصلاح کن و بقیه را تغییر نده."
)

#: A LONG Persian GENERATION request, embedded so this module is portable.
#:
#: It deliberately satisfies the first three conditions of
#: ``_code_repair_turn`` — a repair verb ("اصلاح"), a draft reference
#: ("پیش‌نویس") and a restriction ("فقط") — while still asking for a complete
#: new version. Only the whole-artifact vocabulary keeps it out of the repair
#: branch, which is exactly the conjunction the predicate exists for.
LONG_PERSIAN_GENERATION_REQUEST = (
    "ماشین‌حساب Tkinter قبلی از نظر منطق محاسبات اشتباه بود. "
    "یک نسخه جدید و کامل تولید کن.\n\n"
    "**ایراد اصلی که حتماً باید اصلاح شود:**\n\n"
    "در نسخه قبلی `self.result = 0` بود و هنگام انتخاب اولین عملگر، عدد اول "
    "ذخیره نمی‌شد. بنابراین حتی `5 + 2` نیز اشتباه محاسبه می‌شد.\n\n"
    "برای نسخه جدید:\n\n"
    "۱. وضعیت محاسبه شامل عملوند اول، عملگر انتخاب‌شده، ورودی فعلی و وضعیت "
    "انتظار برای عملوند دوم باشد.\n\n"
    "۲. هنگام اولین انتخاب عملگر، مقدار عدد اول حفظ شود.\n\n"
    "۳. اگر قبل از ورود عدد دوم عملگر را عوض کردم، فقط عملگر تغییر کند؛ "
    "محاسبه انجام نشود.\n\n"
    "۴. هنگام محاسبات زنجیره‌ای، نتیجه میانی به‌عنوان عملوند اول مرحله بعد "
    "حفظ شود.\n\n"
    "۵. دکمه‌های ۰ تا ۹ و چهار عملگر و مساوی و پاک‌کردن در پیش‌نویس فعلی "
    "حاضر باشند و چیدمان تغییر نکند.\n\n"
    "۶. قبل از ذخیرهٔ فایل، تأیید جداگانهٔ من را بگیر و فقط پس از تأیید فایل "
    "app.py را ذخیره کن.\n"
)


@pytest.fixture(scope="module")
def real_project_generation_request():
    """The exact 1 379-character request from project_f043688f, when present.

    Loaded through a FIXTURE, not at import time, so this module stays
    portable: a checkout without the project data still collects and runs every
    other test. The conversation file is only ever read.
    """

    path = os.path.join(
        _PROJECT_ROOT,
        "data",
        "projects",
        "project_f043688f",
        "conversations",
        "chat.json",
    )

    if not os.path.isfile(path):

        pytest.skip("project_f043688f conversation data not present")

    with open(path, encoding="utf-8") as handle:

        return json.load(handle)["messages"][22]["text"]


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """Redirect the project sandbox into a temporary directory."""

    from core.project.project_workspace_v1 import project_workspace

    documents = tmp_path / "documents"
    documents.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        project_workspace, "subdir", lambda project_id, name: str(documents)
    )
    staging.reset_staging()
    yield documents
    staging.reset_staging()


class TestPortability:
    """This module must not depend on the real project data at import time."""

    def test_no_import_time_file_io(self):
        """Nothing at module level may open a file or parse JSON.

        The real conversation is reachable only through
        ``real_project_generation_request``, which skips when the data is
        absent, so a checkout without ``data/projects`` still collects and
        runs everything else.
        """

        tree = ast.parse(inspect.getsource(sys.modules[__name__]))

        for node in tree.body:

            if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.Expr)):
                continue

            for sub in ast.walk(node):

                if not isinstance(sub, ast.Call):
                    continue

                name = getattr(sub.func, "id", None) or getattr(
                    sub.func, "attr", None
                )

                assert name not in ("open", "load", "loads", "read_text"), (
                    "module-level file I/O at import time: %s" % name
                )

    def test_generation_request_literal_is_self_contained(self):
        """The embedded request carries every marker the predicate depends on."""

        text = LONG_PERSIAN_GENERATION_REQUEST

        assert len(text) > 600
        assert "اصلاح" in text            # repair verb
        assert "پیش‌نویس" in text         # pending-draft reference
        assert "فقط" in text              # scope restriction
        assert "نسخه جدید" in text        # whole-artifact signal
        assert "تولید کن" in text         # whole-artifact signal


def _seed_pending(documents, source=BASE_SOURCE, auth=None, origin="coder_model"):
    return staging.stage_code_file(
        project_id=PROJECT,
        filename="app.py",
        content=source,
        documents_root=str(documents),
        origin=origin,
        authorization=dict(auth or AUTH),
    )


def _repair(proposal, candidate, **overrides):
    """Call the store with the MANDATORY compare-and-swap pair.

    Both the digest and the revision are required, so every call here is an
    honest CAS against the proposal that was actually read.
    """

    kwargs = {
        "project_id": PROJECT,
        "candidate": candidate,
        "expected_base_digest": proposal["digest"],
        "expected_revision": proposal["revision"],
        "authorization": dict(AUTH),
    }
    kwargs.update(overrides)
    return replace_staged_file(**kwargs)


def _written(documents):
    return (documents / "code" / "app.py").exists()


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chat(auth=None, capability=None, coder=None):
    """A ChatArchitect whose coder is mocked — no model is ever called."""

    chat = object.__new__(ChatArchitect)
    chat.context = {"trusted_local_authorization": dict(auth or AUTH)}
    if capability is not None:
        chat.context["approval_capability"] = capability

    calls = []

    def _default(text):
        calls.append(text)
        return REPAIRED_SOURCE

    chat._generate_code_with_coder = coder or _default
    return chat, calls


# ===========================================================================
# 1. Routing — ordinary generation stays blocked, explicit repair does not
# ===========================================================================

class TestRepairTurnPredicate:
    """``_code_repair_turn`` is a CONJUNCTION, not a keyword list."""

    @pytest.mark.parametrize(
        "text",
        [
            REPAIR_TEXT_EN,
            REPAIR_TEXT_FA,
            REPAIR_TEXT_NAMED,
            "fix only the bug in the pending draft, keep everything else "
            "unchanged",
        ],
    )
    def test_repair_turns_are_recognised(self, text):
        chat, _calls = _chat()
        assert chat._code_repair_turn(text) is True

    @pytest.mark.parametrize(
        "text,why",
        [
            (LONG_PERSIAN_GENERATION_REQUEST, "long Persian generation request"),
            (
                "یک نسخه جدید و کامل تولید کن و باگ پیش‌نویس را هم اصلاح کن، "
                "بقیه را تغییر نده",
                "generation verb wins over repair vocabulary",
            ),
            (
                "fix the bug in the pending draft and keep everything else "
                "unchanged but write a new version",
                "new version",
            ),
            (
                "پیش‌نویس را از نو بساز و بقیه را تغییر نده",
                "rebuild",
            ),
        ],
    )
    def test_whole_artifact_requests_are_not_repairs(self, text, why):
        chat, _calls = _chat()
        assert chat._code_repair_turn(text) is False, why

    @pytest.mark.parametrize(
        "text,why",
        [
            ("این فایل را اصلاح کن", "no draft reference / no restriction"),
            ("باگ را اصلاح کن", "no draft reference"),
            ("در پیش‌نویس فعلی باگ را اصلاح کن", "no restriction"),
            ("فایل فعلی را اصلاح کن و بقیه را تغییر نده", "ambiguous file"),
            ("تأیید می‌کنم، همین فایل را ذخیره کن", "approval turn"),
            ("رد کن", "rejection turn"),
            ("سلام، حالت چطوره؟", "chat"),
            ("یک ویلای دو طبقه بساز", "architectural"),
            ("", "empty"),
        ],
    )
    def test_ambiguous_turns_do_not_enter_the_repair_branch(self, text, why):
        chat, _calls = _chat()
        assert chat._code_repair_turn(text) is False, why


class TestGenerationStaysBlocked:
    """Item 1 — the pending-proposal guard is unchanged for generation."""

    def test_long_generation_request_is_refused_and_spends_no_inference(
        self, sandbox
    ):
        _seed_pending(sandbox)
        chat, calls = _chat()

        assert chat._authorized_code_repair(
            LONG_PERSIAN_GENERATION_REQUEST, PROJECT
        ) is None

        message = chat._authorized_code_file_creation(
            LONG_PERSIAN_GENERATION_REQUEST, PROJECT
        )

        assert "در انتظار تأیید شماست" in message
        assert calls == [], "no inference may be spent on a refused turn"

        pending = staging.pending_proposal(PROJECT)
        assert pending["origin"] == "coder_model"
        assert pending["digest"] == _sha(BASE_SOURCE)
        assert not _written(sandbox)

    def test_repair_turn_without_a_pending_draft_does_not_generate(
        self, sandbox
    ):
        chat, calls = _chat()

        message = chat._authorized_code_repair(REPAIR_TEXT_EN, PROJECT)

        assert "هیچ پیش‌نویس قابل اصلاحی" in message
        assert calls == []
        assert staging.pending_proposal(PROJECT) is None
        assert not _written(sandbox)


class TestRealProjectRequestStillBlocked:
    """The same assertion against the REAL conversation data, when present."""

    def test_real_request_is_not_a_repair_turn(
        self, real_project_generation_request
    ):
        chat, _calls = _chat()
        assert chat._code_repair_turn(real_project_generation_request) is False

    def test_real_request_stays_blocked_by_the_pending_guard(
        self, sandbox, real_project_generation_request
    ):
        _seed_pending(sandbox)
        chat, calls = _chat()

        assert chat._authorized_code_repair(
            real_project_generation_request, PROJECT
        ) is None

        message = chat._authorized_code_file_creation(
            real_project_generation_request, PROJECT
        )

        assert "در انتظار تأیید شماست" in message
        assert calls == []
        assert staging.pending_proposal(PROJECT)["digest"] == _sha(BASE_SOURCE)
        assert not _written(sandbox)


# ===========================================================================
# 2. The repair reaches the EXISTING coder with the EXACT base
# ===========================================================================

class TestRepairReachesCoder:
    """Items 2 and 4."""

    def test_repair_calls_the_existing_coder_once(self, sandbox):
        _seed_pending(sandbox)
        chat, calls = _chat()

        message = chat._authorized_code_repair(REPAIR_TEXT_EN, PROJECT)

        assert len(calls) == 1, "the existing coder gateway must be used once"
        assert "اصلاح شد" in message
        assert not _written(sandbox)

    def test_prompt_carries_the_authoritative_base_source_and_digest(
        self, sandbox
    ):
        proposal = _seed_pending(sandbox)
        chat, calls = _chat()

        chat._authorized_code_repair(REPAIR_TEXT_EN, PROJECT)

        prompt = calls[0]

        # The EXACT base bytes, not a history reconstruction.
        assert BASE_SOURCE in prompt
        # The digest the repair is bound to.
        assert proposal["digest"] in prompt
        # The failed behaviour and the scope contract travel with the request.
        assert "FAILED BEHAVIOUR" in prompt
        assert "HARD SCOPE RULES" in prompt
        assert "Do not change imports." in prompt
        # The base is never re-derived from conversation history.
        assert "conversation" not in prompt.lower()

    def test_named_target_is_forwarded_to_the_coder(self, sandbox):
        _seed_pending(sandbox)
        chat, calls = _chat()

        chat._authorized_code_repair(REPAIR_TEXT_NAMED, PROJECT)

        assert "Target function/method: Calculator.on_operator" in calls[0]

    def test_named_target_prompt_declares_the_bounded_handoff(self, sandbox):
        _seed_pending(sandbox)
        chat, calls = _chat()

        chat._authorized_code_repair(REPAIR_TEXT_NAMED, PROJECT)

        assert "Only this method's BODY is taken from your answer." in calls[0]

    def test_unnamed_target_prompt_keeps_the_whole_file_contract(self, sandbox):
        _seed_pending(sandbox)
        chat, calls = _chat()

        chat._authorized_code_repair(REPAIR_TEXT_EN, PROJECT)

        assert "Only this method's BODY" not in calls[0]
        assert "Return the COMPLETE corrected file" in calls[0]


# ===========================================================================
# 3. Binding — wrong actor / project / session / digest / revision
# ===========================================================================

class TestRepairBinding:
    """Item 3."""

    @pytest.mark.parametrize(
        "override",
        [
            {"actor_id": "someone_else"},
            {"session_id": "sess_other"},
            {"project_id": "project_other"},
        ],
    )
    def test_wrong_identity_is_refused(self, sandbox, override):
        proposal = _seed_pending(sandbox)
        wrong = dict(AUTH)
        wrong.update(override)

        base = repair_base(PROJECT, wrong)
        assert base["ok"] is False
        assert base["reason"] in (
            "trusted_authorization_required",
            staging.REPAIR_BINDING_MISMATCH,
        )

        outcome = _repair(proposal, REPAIRED_SOURCE, authorization=wrong)
        assert outcome["status"] == "rejected"
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]

    def test_untrusted_authorization_is_refused(self, sandbox):
        _seed_pending(sandbox)

        base = repair_base(PROJECT, {"trusted": False})
        assert base["ok"] is False
        assert base["reason"] == "trusted_authorization_required"

    def test_wrong_base_digest_is_refused(self, sandbox):
        proposal = _seed_pending(sandbox)

        outcome = _repair(
            proposal, REPAIRED_SOURCE, expected_base_digest="0" * 64
        )

        assert outcome["status"] == "rejected"
        assert outcome["reason"] == staging.REPAIR_BASE_CHANGED
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]

    def test_handler_with_wrong_session_never_calls_the_coder(self, sandbox):
        _seed_pending(sandbox)
        wrong = dict(AUTH)
        wrong["session_id"] = "sess_other"
        chat, calls = _chat(auth=wrong)

        message = chat._authorized_code_repair(REPAIR_TEXT_EN, PROJECT)

        # The store, not the handler, owns session binding.
        assert staging.REPAIR_BINDING_MISMATCH in message
        assert calls == []
        assert staging.pending_proposal(PROJECT)["digest"] == _sha(BASE_SOURCE)


# ===========================================================================
# 4. Scope — one method body, nothing else
# ===========================================================================

class TestScopeInference:
    """The server decides the scope from the bytes it received."""

    def test_single_method_change_is_the_scope(self):
        assert infer_changed_scope(BASE_SOURCE, REPAIRED_SOURCE) == (
            "Calculator.on_operator",
            None,
        )

    def test_two_changed_methods_are_ambiguous(self):
        two = REPAIRED_SOURCE.replace(
            "        self.current = self.current + digit\n",
            "        self.current = self.current + digit\n"
            "        self.last = digit\n",
        )
        assert infer_changed_scope(BASE_SOURCE, two) == (
            None,
            staging.REPAIR_MULTI,
        )

    def test_changed_imports_are_refused(self):
        changed = REPAIRED_SOURCE.replace(
            "import tkinter as tk\n", "import tkinter as tk\nimport os\n"
        )
        assert infer_changed_scope(BASE_SOURCE, changed) == (
            None,
            staging.REPAIR_IMPORTS,
        )

    def test_added_method_is_refused(self):
        added = REPAIRED_SOURCE.replace(
            "    def on_key(self, event):",
            "    def extra(self):\n        return 1\n\n    def on_key(self, event):",
        )
        assert infer_changed_scope(BASE_SOURCE, added) == (
            None,
            staging.REPAIR_OUTSIDE,
        )

    def test_module_level_change_is_refused(self):
        changed = REPAIRED_SOURCE + "\nVERSION = 2\n"
        assert infer_changed_scope(BASE_SOURCE, changed) == (
            None,
            staging.REPAIR_OUTSIDE,
        )

    def test_class_attribute_change_is_refused(self):
        changed = REPAIRED_SOURCE.replace(
            "class Calculator:\n", "class Calculator:\n    LIMIT = 9\n"
        )
        assert infer_changed_scope(BASE_SOURCE, changed) == (
            None,
            staging.REPAIR_OUTSIDE,
        )

    def test_no_op_is_refused(self):
        assert infer_changed_scope(BASE_SOURCE, BASE_SOURCE) == (
            None,
            staging.REPAIR_NO_OP,
        )


class TestOutOfScopeBytes:
    """ISSUE 1 — bytes outside the authorised span must be preserved exactly.

    The original implementation compared a normalised skeleton
    (``line.rstrip()`` + ``splitlines``), so a candidate that fixed the target
    method AND touched an unrelated line was accepted. These tests reproduce
    the bypass and prove it is now refused.
    """

    def test_trailing_whitespace_on_an_unrelated_import_is_rejected(self):
        candidate = REPAIRED_SOURCE.replace(
            "import tkinter as tk\n", "import tkinter as tk   \n"
        )
        assert candidate != BASE_SOURCE
        assert infer_changed_scope(BASE_SOURCE, candidate) == (
            None,
            staging.REPAIR_OUTSIDE,
        )

    def test_whole_file_crlf_conversion_is_rejected(self):
        candidate = REPAIRED_SOURCE.replace("\n", "\r\n")
        assert infer_changed_scope(BASE_SOURCE, candidate) == (
            None,
            staging.REPAIR_OUTSIDE,
        )

    def test_crlf_base_with_crlf_candidate_is_accepted(self):
        """The check is about CHANGE, not about line-ending style.

        A CRLF draft stays repairable as long as the candidate keeps CRLF, so
        the byte-exact rule never rejects a file merely for being CRLF.
        """

        base = BASE_SOURCE.replace("\n", "\r\n")
        candidate = REPAIRED_SOURCE.replace("\n", "\r\n")
        assert infer_changed_scope(base, candidate) == (
            "Calculator.on_operator",
            None,
        )

    def test_added_trailing_blank_line_is_rejected(self):
        candidate = REPAIRED_SOURCE + "\n"
        assert infer_changed_scope(BASE_SOURCE, candidate) == (
            None,
            staging.REPAIR_OUTSIDE,
        )

    def test_reformatted_blank_line_outside_the_span_is_rejected(self):
        # Between the import block and the class — outside every function span.
        candidate = REPAIRED_SOURCE.replace(
            "import tkinter as tk\n\n\nclass Calculator:\n",
            "import tkinter as tk\n\n\n\nclass Calculator:\n",
        )
        assert infer_changed_scope(BASE_SOURCE, candidate) == (
            None,
            staging.REPAIR_OUTSIDE,
        )

    def test_blank_line_inside_another_method_is_rejected(self):
        # Inside a DIFFERENT method's span, so two scopes now differ.
        candidate = REPAIRED_SOURCE.replace(
            "        self.current = \"\"\n",
            "        self.current = \"\"\n\n",
        )
        assert infer_changed_scope(BASE_SOURCE, candidate) == (
            None,
            staging.REPAIR_MULTI,
        )

    def test_whitespace_bypass_is_refused_through_the_store(self, sandbox):
        proposal = _seed_pending(sandbox)
        candidate = REPAIRED_SOURCE.replace(
            "import tkinter as tk\n", "import tkinter as tk \n"
        )

        outcome = _repair(proposal, candidate)

        assert outcome["reason"] == staging.REPAIR_OUTSIDE
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]

    def test_crlf_bypass_is_refused_through_the_store(self, sandbox):
        proposal = _seed_pending(sandbox)

        outcome = _repair(proposal, REPAIRED_SOURCE.replace("\n", "\r\n"))

        assert outcome["reason"] == staging.REPAIR_OUTSIDE
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]


class TestSignatureProtection:
    """ISSUE 2 — a body-only repair may not change the declaration."""

    def test_added_parameter_is_rejected(self):
        candidate = REPAIRED_SOURCE.replace(
            "    def on_operator(self, operator):",
            "    def on_operator(self, operator, unexpected=None):",
        )
        assert infer_changed_scope(BASE_SOURCE, candidate) == (
            None,
            staging.REPAIR_SIGNATURE,
        )

    def test_added_default_is_rejected(self):
        candidate = REPAIRED_SOURCE.replace(
            "    def on_operator(self, operator):",
            "    def on_operator(self, operator=0):",
        )
        assert infer_changed_scope(BASE_SOURCE, candidate) == (
            None,
            staging.REPAIR_SIGNATURE,
        )

    def test_added_return_annotation_is_rejected(self):
        candidate = REPAIRED_SOURCE.replace(
            "    def on_operator(self, operator):",
            "    def on_operator(self, operator) -> None:",
        )
        assert infer_changed_scope(BASE_SOURCE, candidate) == (
            None,
            staging.REPAIR_SIGNATURE,
        )

    def test_reformatted_multi_line_declaration_is_rejected(self):
        candidate = REPAIRED_SOURCE.replace(
            "    def on_operator(self, operator):",
            "    def on_operator(\n        self, operator\n    ):",
        )
        assert infer_changed_scope(BASE_SOURCE, candidate) == (
            None,
            staging.REPAIR_SIGNATURE,
        )

    def test_added_decorator_is_rejected(self):
        candidate = REPAIRED_SOURCE.replace(
            "    def on_operator(self, operator):",
            "    @staticmethod\n    def on_operator(self, operator):",
        )
        assert infer_changed_scope(BASE_SOURCE, candidate) == (
            None,
            staging.REPAIR_OUTSIDE,
        )

    def test_one_line_function_body_repair_is_still_allowed(self):
        """The declaration shares its line with the body — must not deadlock."""

        base = "class C:\n    def f(self): return 1\n"
        candidate = "class C:\n    def f(self): return 2\n"
        assert infer_changed_scope(base, candidate) == ("C.f", None)

    def test_signature_change_is_refused_through_the_store(self, sandbox):
        proposal = _seed_pending(sandbox)
        candidate = REPAIRED_SOURCE.replace(
            "    def on_operator(self, operator):",
            "    def on_operator(self, operator, unexpected=None):",
        )

        outcome = _repair(proposal, candidate)

        assert outcome["reason"] == staging.REPAIR_SIGNATURE
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]


class TestScopeEnforcement:
    """Items 5, 6 and 9 — end to end through the store."""

    def test_method_only_repair_is_accepted(self, sandbox):
        proposal = _seed_pending(sandbox)

        outcome = _repair(proposal, REPAIRED_SOURCE)

        assert outcome["status"] == "replaced"
        assert outcome["scope"] == "Calculator.on_operator"
        assert outcome["base_digest"] == proposal["digest"]

    def test_gui_layout_change_alongside_the_fix_is_rejected(self, sandbox):
        proposal = _seed_pending(sandbox)
        candidate = REPAIRED_SOURCE.replace(
            '        tk.Label(self.root, text="0").pack()\n',
            '        tk.Label(self.root, text="0").grid()\n',
        )

        outcome = _repair(proposal, candidate)

        assert outcome["reason"] == staging.REPAIR_MULTI
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]

    def test_unrelated_method_change_is_never_applied(self, sandbox):
        """A named target means ONLY that body may come from the model.

        The model tries to change ``build_layout`` instead of ``on_operator``.
        With the bounded handoff that edit cannot even reach the candidate, so
        the authorised method is unchanged and the repair is refused as a
        no-op — and the GUI line is still the base's ``.pack()``.
        """

        _seed_pending(sandbox)
        chat, _calls = _chat()

        def _wrong_scope(text):
            return REPAIRED_SOURCE.replace(
                '        tk.Label(self.root, text="0").pack()\n',
                '        tk.Label(self.root, text="0").grid()\n',
            ).replace(
                "        if self.pending is None:\n"
                "            self.result = float(self.current or 0)\n"
                "        self.pending = operator\n",
                "        self.result = 0\n"
                "        self.pending = operator\n",
            )

        chat._generate_code_with_coder = _wrong_scope

        message = chat._authorized_code_repair(REPAIR_TEXT_NAMED, PROJECT)

        assert staging.REPAIR_NO_OP in message
        live = staging.pending_proposal(PROJECT)
        assert live["digest"] == _sha(BASE_SOURCE)
        assert ".pack()" in live["content"]
        assert ".grid()" not in live["content"]

    def test_store_rejects_a_candidate_outside_the_named_target(self, sandbox):
        """Store-level protection, independent of the handler's handoff."""

        proposal = _seed_pending(sandbox)
        candidate = BASE_SOURCE.replace(
            '        tk.Label(self.root, text="0").pack()\n',
            '        tk.Label(self.root, text="0").grid()\n',
        )

        outcome = _repair(
            proposal,
            candidate,
            repair={"target": "Calculator.on_operator"},
        )

        assert outcome["reason"] == staging.REPAIR_SCOPE
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]

    def test_keyboard_handler_change_is_rejected(self, sandbox):
        proposal = _seed_pending(sandbox)
        candidate = REPAIRED_SOURCE.replace(
            "        return self.on_digit(event.char)\n",
            "        return self.on_digit(event.keysym)\n",
        )

        outcome = _repair(proposal, candidate)

        assert outcome["reason"] == staging.REPAIR_MULTI

    def test_no_op_candidate_is_rejected(self, sandbox):
        proposal = _seed_pending(sandbox)

        outcome = _repair(proposal, BASE_SOURCE)

        assert outcome["reason"] == staging.REPAIR_NO_OP
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]

    def test_empty_candidate_is_rejected(self, sandbox):
        proposal = _seed_pending(sandbox)

        outcome = _repair(proposal, "   \n")

        assert outcome["reason"] == staging.REPAIR_EMPTY
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]


# ===========================================================================
# 5. Failed candidates preserve the base
# ===========================================================================

class TestCandidateFailurePreservesBase:
    """Items 7 and 8."""

    def test_syntax_failure_preserves_the_base(self, sandbox):
        proposal = _seed_pending(sandbox)
        broken = REPAIRED_SOURCE.replace(
            "        self.pending = operator\n", "        self.pending = (\n"
        )

        outcome = _repair(proposal, broken)

        assert outcome["reason"] == staging.REPAIR_SYNTAX
        assert outcome["syntax_error"]
        live = staging.pending_proposal(PROJECT)
        assert live["digest"] == proposal["digest"]
        assert live["content"] == BASE_SOURCE

    def test_static_review_failure_preserves_the_base(self, sandbox):
        proposal = _seed_pending(sandbox)
        # A mutable default is a STATIC_FAIL finding, but it also changes the
        # declaration, so either refusal is acceptable — the base must survive.
        unsafe = REPAIRED_SOURCE.replace(
            "    def on_operator(self, operator):",
            "    def on_operator(self, operator, extra=[]):",
        )

        outcome = _repair(proposal, unsafe)

        assert outcome["reason"] in (
            staging.REPAIR_STATIC,
            staging.REPAIR_SIGNATURE,
        )
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]

    def test_model_failure_preserves_the_base(self, sandbox):
        _seed_pending(sandbox)
        chat, _calls = _chat(coder=lambda text: None)

        message = chat._authorized_code_repair(REPAIR_TEXT_EN, PROJECT)

        assert "برنگرداند" in message
        live = staging.pending_proposal(PROJECT)
        assert live["digest"] == _sha(BASE_SOURCE)
        assert not _written(sandbox)


class TestStaticReviewFailsClosed:
    """ISSUE 3 — an unavailable or malformed review must not allow a repair.

    ``stage_code_file`` tolerates ``quality=None`` (ordinary staging says
    "review not performed"). A repair claims to have CONFINED a change, so it
    has to prove the review ran; anything else fails closed.
    """

    def _outcome(self, sandbox, monkeypatch, quality):
        proposal = _seed_pending(sandbox)
        monkeypatch.setattr(
            staging, "_quality_block", lambda *args, **kwargs: quality
        )
        return proposal, _repair(proposal, REPAIRED_SOURCE)

    def test_unavailable_review_is_refused(self, sandbox, monkeypatch):
        proposal, outcome = self._outcome(sandbox, monkeypatch, None)

        assert outcome["reason"] == staging.REPAIR_STATIC_UNAVAILABLE
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]

    @pytest.mark.parametrize(
        "quality",
        [
            {},
            {"static_review": None, "findings": [], "syntax": "PASS"},
            {"static_review": "UNKNOWN", "findings": [], "syntax": "PASS"},
            {"static_review": "PASS", "findings": None, "syntax": "PASS"},
            {"static_review": "PASS", "syntax": "PASS"},
            {"static_review": "PASS", "findings": [], "syntax": "FAIL"},
            {"static_review": "PASS", "findings": []},
            "not-a-dict",
            [],
        ],
    )
    def test_malformed_review_is_refused(self, sandbox, monkeypatch, quality):
        proposal, outcome = self._outcome(sandbox, monkeypatch, quality)

        assert outcome["reason"] == staging.REPAIR_STATIC_UNAVAILABLE
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]

    @pytest.mark.parametrize("verdict", ["PASS", "WARN"])
    def test_recognised_non_failing_verdict_is_accepted(
        self, sandbox, monkeypatch, verdict
    ):
        _proposal, outcome = self._outcome(
            sandbox,
            monkeypatch,
            {"static_review": verdict, "findings": [], "syntax": "PASS"},
        )

        assert outcome["status"] == "replaced"
        assert outcome["digest"] == _sha(REPAIRED_SOURCE)

    def test_recognised_fail_verdict_is_refused(self, sandbox, monkeypatch):
        proposal, outcome = self._outcome(
            sandbox,
            monkeypatch,
            {
                "static_review": "FAIL",
                "findings": [{"code": "x"}],
                "syntax": "PASS",
            },
        )

        assert outcome["reason"] == staging.REPAIR_STATIC
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]

    def test_real_review_module_still_accepts_a_clean_repair(self, sandbox):
        """The fail-closed gate must not reject a genuinely clean candidate."""

        proposal = _seed_pending(sandbox)
        outcome = _repair(proposal, REPAIRED_SOURCE)

        assert outcome["status"] == "replaced"

    def test_real_review_fail_inside_the_body_is_refused(self, sandbox):
        """A FAIL finding in the body (no signature change) is a real FAIL.

        ``eval`` is a SEVERITY_FAIL rule, so this exercises ``REPAIR_STATIC``
        through the REAL review module rather than a stubbed verdict.
        """

        proposal = _seed_pending(sandbox)
        candidate = REPAIRED_SOURCE.replace(
            "            self.result = float(self.current or 0)\n",
            "            self.result = eval(self.current)\n",
        )

        outcome = _repair(proposal, candidate)

        assert outcome["reason"] == staging.REPAIR_STATIC
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]


# ===========================================================================
# 6. Concurrency, revision and atomicity
# ===========================================================================

class TestAtomicity:
    """Item 10 — a proposal that changed mid-generation is never repaired."""

    def test_replaced_proposal_is_detected_by_digest(self, sandbox):
        base = repair_base(PROJECT, AUTH)
        assert base["ok"] is False  # nothing staged yet

        proposal = _seed_pending(sandbox)
        snapshot = repair_base(PROJECT, AUTH)
        assert snapshot["ok"] is True

        # Another turn installs a different proposal while "the model runs".
        _seed_pending(
            sandbox, source=BASE_SOURCE.replace("self.result = 0", "self.result = 1")
        )

        outcome = _repair(
            {"digest": snapshot["digest"], "revision": snapshot["revision"]},
            REPAIRED_SOURCE,
        )

        assert outcome["status"] == "rejected"
        assert outcome["reason"] == staging.REPAIR_BASE_CHANGED
        # The concurrent proposal survives untouched.
        live = staging.pending_proposal(PROJECT)
        assert live["digest"] != proposal["digest"]
        assert live["digest"] == _sha(
            BASE_SOURCE.replace("self.result = 0", "self.result = 1")
        )

    def test_same_bytes_but_new_revision_is_still_detected(self, sandbox):
        proposal = _seed_pending(sandbox)
        snapshot = repair_base(PROJECT, AUTH)

        # Re-staging the SAME bytes produces the same digest but a new revision.
        _seed_pending(sandbox)

        outcome = _repair(
            {"digest": snapshot["digest"], "revision": snapshot["revision"]},
            REPAIRED_SOURCE,
        )

        assert outcome["reason"] == staging.REPAIR_BASE_CHANGED
        assert staging.pending_proposal(PROJECT)["revision"] != proposal["revision"]

    def test_consumed_capability_blocks_repair(self, sandbox):
        proposal = _seed_pending(sandbox)
        live = staging._STAGED[PROJECT]
        live["capability"]["consumed"] = True
        staging._STAGED[PROJECT] = live

        outcome = _repair(proposal, REPAIRED_SOURCE)

        assert outcome["reason"] == staging.REPAIR_CONSUMED


class TestMandatoryRevision:
    """ISSUE 4 — the revision is part of the CAS, not an optional extra."""

    def test_repair_without_a_revision_is_refused(self, sandbox):
        proposal = _seed_pending(sandbox)

        outcome = replace_staged_file(
            project_id=PROJECT,
            candidate=REPAIRED_SOURCE,
            expected_base_digest=proposal["digest"],
            authorization=dict(AUTH),
        )

        assert outcome["reason"] == staging.REPAIR_REVISION_REQUIRED
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]

    @pytest.mark.parametrize("revision", [None, "1", 1.0, True, False])
    def test_non_integer_revision_is_refused(self, sandbox, revision):
        proposal = _seed_pending(sandbox)

        outcome = replace_staged_file(
            project_id=PROJECT,
            candidate=REPAIRED_SOURCE,
            expected_base_digest=proposal["digest"],
            expected_revision=revision,
            authorization=dict(AUTH),
        )

        assert outcome["reason"] == staging.REPAIR_REVISION_REQUIRED
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]

    def test_production_handler_passes_the_expected_revision(
        self, sandbox, monkeypatch
    ):
        _seed_pending(sandbox)
        captured = {}
        real = staging.replace_staged_file

        def _spy(**kwargs):
            captured.update(kwargs)
            return real(**kwargs)

        monkeypatch.setattr(staging, "replace_staged_file", _spy)

        chat, _calls = _chat()
        chat._authorized_code_repair(REPAIR_TEXT_EN, PROJECT)

        assert isinstance(captured.get("expected_revision"), int)
        assert captured["expected_revision"] == 1
        assert captured["expected_base_digest"] == _sha(BASE_SOURCE)


class TestStagingWriteAtomicity:
    """ISSUE 4 — the store write must happen INSIDE the staging lock.

    The revision bump was locked but ``_STAGED[project_id] = stored`` was not,
    so two writers could install their proposals out of order: the store could
    end up holding an older revision than ``_REVISIONS`` reports, breaking the
    monotonic identity the repair compare-and-swap relies on.
    """

    def test_store_write_occurs_while_the_lock_is_held(self, sandbox, monkeypatch):
        if not hasattr(staging._STAGING_LOCK, "_is_owned"):

            pytest.skip("RLock._is_owned unavailable on this interpreter")

        writes = []

        class _RecordingStore(dict):

            def __setitem__(self, key, value):

                writes.append(
                    {
                        "key": key,
                        "owned": staging._STAGING_LOCK._is_owned(),
                        "revision": value.get("revision"),
                    }
                )
                super().__setitem__(key, value)

        monkeypatch.setattr(staging, "_STAGED", _RecordingStore())

        _seed_pending(sandbox)

        assert writes, "staging must install a proposal"
        assert all(entry["owned"] for entry in writes), (
            "the store write must happen inside _STAGING_LOCK"
        )

    def test_concurrent_staging_keeps_revision_and_content_consistent(
        self, sandbox
    ):
        workers = 8
        barrier = threading.Barrier(workers)
        errors = []

        def _stage(number):

            try:

                barrier.wait(timeout=10)
                staging.stage_code_file(
                    project_id=PROJECT,
                    filename="app.py",
                    content="value = %d\n" % number,
                    documents_root=str(sandbox),
                    origin="concurrent",
                    authorization=dict(AUTH),
                )

            except Exception as error:  # noqa: BLE001 - reported, not swallowed

                errors.append(error)

        threads = [
            threading.Thread(target=_stage, args=(number,))
            for number in range(workers)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join(timeout=10800)

        assert errors == []

        live = staging.pending_proposal(PROJECT)
        assert live["digest"] == _sha(live["content"])
        # The store must hold the NEWEST write, not an out-of-order one.
        assert live["revision"] == staging._REVISIONS[PROJECT]
        assert live["revision"] == workers

    def test_sequential_staging_keeps_a_consistent_proposal(self, sandbox):
        for number in range(6):

            staging.stage_code_file(
                project_id=PROJECT,
                filename="app.py",
                content="value = %d\n" % number,
                documents_root=str(sandbox),
                origin="sequential",
                authorization=dict(AUTH),
            )

        live = staging.pending_proposal(PROJECT)
        assert live["revision"] == 6
        assert live["revision"] == staging._REVISIONS[PROJECT]
        assert live["digest"] == _sha(live["content"])


# ===========================================================================
# 7. Digest integrity and approval invalidation
# ===========================================================================

class TestStagedDigest:
    """Item 11 — the digest shown is the digest of the staged bytes."""

    def test_candidate_digest_equals_the_staged_bytes(self, sandbox):
        proposal = _seed_pending(sandbox)

        outcome = _repair(proposal, REPAIRED_SOURCE)

        live = staging.pending_proposal(PROJECT)
        assert live["content"] == REPAIRED_SOURCE
        assert live["digest"] == _sha(REPAIRED_SOURCE)
        assert live["digest"] == outcome["digest"]
        assert live["digest"] != proposal["digest"]
        assert live["base_diff"]

    def test_repaired_proposal_carries_repair_provenance(self, sandbox):
        proposal = _seed_pending(sandbox)

        _repair(
            proposal,
            REPAIRED_SOURCE,
            repair={"target": None, "user_request": REPAIR_TEXT_EN},
        )

        live = staging.pending_proposal(PROJECT)
        repair = live["repair"]
        assert repair["base_digest"] == _sha(BASE_SOURCE)
        assert repair["target"] == "Calculator.on_operator"
        assert repair["failure_source"] == "user_reported"
        assert repair["execution_authorized"] is False
        assert repair["packaging_authorized"] is False
        assert repair["writes_performed"] == 0
        assert live["origin"] == "coder_repair"


class TestApprovalInvalidation:
    """Item 12 — the old save approval cannot write the repaired candidate."""

    def test_old_token_cannot_save_the_repaired_candidate(self, sandbox):
        proposal = _seed_pending(sandbox)
        old_token = proposal["approval_token"]
        assert old_token

        outcome = _repair(proposal, REPAIRED_SOURCE)
        assert outcome["status"] == "replaced"

        fresh = staging.public_approval_capability(PROJECT, dict(AUTH))
        assert fresh["token"] != old_token
        assert fresh["digest"] == _sha(REPAIRED_SOURCE)

        # The OLD token is presented, exactly as a stale UI would.
        chat, _calls = _chat(capability=old_token)
        message = chat._authorized_code_file_approval(
            "تأیید می‌کنم، همین فایل را ذخیره کن", PROJECT
        )

        assert "approval_capability_invalid" in message
        assert not _written(sandbox)
        assert staging.pending_proposal(PROJECT)["digest"] == _sha(REPAIRED_SOURCE)

    def test_fresh_token_can_save_the_repaired_candidate(self, sandbox):
        proposal = _seed_pending(sandbox)

        _repair(proposal, REPAIRED_SOURCE)
        fresh = staging.public_approval_capability(PROJECT, dict(AUTH))

        chat, _calls = _chat(capability=fresh["token"])
        message = chat._authorized_code_file_approval(
            "تأیید می‌کنم، همین فایل را ذخیره کن", PROJECT
        )

        assert "ذخیره شد" in message
        assert _written(sandbox)
        assert (sandbox / "code" / "app.py").read_text(encoding="utf-8") == (
            REPAIRED_SOURCE
        )


# ===========================================================================
# 8. No automatic authority
# ===========================================================================

class TestNoAutomaticAuthority:
    """Item 13 — a repair grants nothing beyond a new unsaved draft."""

    def test_repair_never_writes_executes_or_packages(self, sandbox):
        _seed_pending(sandbox)
        chat, _calls = _chat()

        message = chat._authorized_code_repair(REPAIR_TEXT_EN, PROJECT)

        assert not _written(sandbox)
        assert "ذخیره شد" not in message
        assert "اجرا شد" not in message
        live = staging.pending_proposal(PROJECT)
        assert live["status"] == "awaiting_approval"
        assert live["writes_performed"] == 0
        assert live["repair"]["execution_authorized"] is False
        assert live["repair"]["packaging_authorized"] is False
        # The reply must not imply functional success.
        assert "تأیید نشده" in message

    def test_repair_reply_reports_the_new_digest_and_the_diff(self, sandbox):
        _seed_pending(sandbox)
        chat, _calls = _chat()

        message = chat._authorized_code_repair(REPAIR_TEXT_EN, PROJECT)

        assert _sha(REPAIRED_SOURCE) in message
        assert _sha(BASE_SOURCE) in message
        assert "Calculator.on_operator" in message
        assert "@@" in message, "the base-to-candidate diff must be shown"

    def test_handler_has_no_write_execute_or_package_call(self):
        source = textwrap.dedent(
            inspect.getsource(ChatArchitect._authorized_code_repair)
        )
        tree = ast.parse(source)

        forbidden = {
            "approve_staged_file",
            "create_project_code_file",
            "reject_staged_file",
            "run_source",
            "package",
            "subprocess",
            "docker",
        }

        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    called.add(node.func.attr)
                elif isinstance(node.func, ast.Name):
                    called.add(node.func.id)

        assert not (called & forbidden), sorted(called & forbidden)

    def test_dispatch_gate_contains_the_repair_predicate(self):
        source = textwrap.dedent(
            inspect.getsource(ChatArchitect._handle_internal)
        )
        tree = ast.parse(source)

        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "_code_repair_turn":
                    found = True

        assert found, "_code_repair_turn must gate the repair branch"


# ===========================================================================
# 9. Verification consent is digest-bound (items 14 and 15)
# ===========================================================================

def _patch_verified(monkeypatch, actor=ACTOR, session=SESSION):
    import core.runtime.local_authorization_v1 as authz

    def fake(secret, headers, payload, path=None, remote_addr=None, now=None,
             nonce_ledger=None):
        return {"trusted": True, "actor_id": actor, "session_id": session}

    monkeypatch.setattr(authz, "verify_proxy_request", fake)


def _mint(monkeypatch, digest, store=None):
    store = store or dv.DraftVerificationConsent()
    _patch_verified(monkeypatch)
    return store.mint(
        proxy_secret="s" * 48,
        headers={},
        payload={
            "operation": dv.DRAFT_OPERATION,
            "project_id": PROJECT,
            "proposal_id": dv.staged_proposal_id(digest),
            "source_sha256": digest,
            "consent": True,
        },
        path=dv.DRAFT_CONSENT_PATH,
        remote_addr="127.0.0.1",
        nonce_ledger=set(),
        project_id=PROJECT,
    )


SCENARIOS = [{"name": "alpha", "steps": []}, {"name": "beta", "steps": []}]


class _FakeExecutor:
    calls = []
    scenarios = None
    app_digest = None

    def __init__(self):
        self.backend_verified = True

    def run_source(self, source_bytes, source_sha256, resource_limits):
        # ``source_bytes`` is the HARNESS (it embeds the app source and the
        # expected digest); the app digest is reported separately by the
        # service as ``source_sha256``.
        _FakeExecutor.calls.append(
            {
                "digest": source_sha256,
                "sha": hashlib.sha256(source_bytes).hexdigest(),
                "bytes": source_bytes,
            }
        )
        payload = {
            "ok": True,
            "app_sha256": _FakeExecutor.app_digest,
            "harness": "DraftVerificationHarness/1.1",
            "scenario_count": len(_FakeExecutor.scenarios),
            "scenarios": _FakeExecutor.scenarios,
        }
        return {
            "ok": True,
            "reason": None,
            "stdout": dv.RESULT_MARKER + json.dumps(payload) + "\n",
            "stderr": "",
            "source_digest_verified": True,
            "removal_verified": True,
        }


def _service(consent, scenarios):
    _FakeExecutor.calls = []
    _FakeExecutor.scenarios = scenarios
    return dv.DraftVerificationService(
        consent=consent,
        executor_factory=_FakeExecutor,
        opt_in_reader=lambda: True,
    )


def _embedded_app_source(harness):
    """The exact app source the harness embeds (``APP_SOURCE = "..."``).

    The harness stores the source as an escaped Python literal, so a substring
    search against the raw text is meaningless. Decoding the literal is the
    only way to prove WHICH bytes the scenarios would run.
    """

    for node in ast.parse(harness).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "APP_SOURCE":
                    return ast.literal_eval(node.value)
    return None


class TestFreshVerificationConsent:
    """Item 14 — an old consent token cannot verify the repaired candidate."""

    def test_old_consent_cannot_verify_the_repaired_digest(
        self, sandbox, monkeypatch
    ):
        proposal = _seed_pending(sandbox)
        consent = dv.DraftVerificationConsent()
        old = _mint(monkeypatch, proposal["digest"], consent)
        assert old["ok"] is True

        _repair(proposal, REPAIRED_SOURCE)

        _FakeExecutor.app_digest = _sha(REPAIRED_SOURCE)
        result = _service(
            consent, [{"id": "alpha", "status": "PASS", "detail": ""},
                      {"id": "beta", "status": "PASS", "detail": ""}]
        ).verify_draft(
            project_id=PROJECT,
            token=old["token"],
            scenarios=SCENARIOS,
            actor_id=ACTOR,
            session_id=SESSION,
        )

        assert result["ok"] is False
        assert result["reason"] == "draft_capability_digest_mismatch"
        assert _FakeExecutor.calls == [], "no container may run on stale consent"

    def test_fresh_consent_verifies_the_repaired_digest(self, sandbox, monkeypatch):
        proposal = _seed_pending(sandbox)

        _repair(proposal, REPAIRED_SOURCE)

        new_digest = _sha(REPAIRED_SOURCE)
        consent = dv.DraftVerificationConsent()
        fresh = _mint(monkeypatch, new_digest, consent)
        assert fresh["ok"] is True

        _FakeExecutor.app_digest = new_digest
        result = _service(
            consent, [{"id": "alpha", "status": "PASS", "detail": ""},
                      {"id": "beta", "status": "PASS", "detail": ""}]
        ).verify_draft(
            project_id=PROJECT,
            token=fresh["token"],
            scenarios=SCENARIOS,
            actor_id=ACTOR,
            session_id=SESSION,
        )

        assert result["ok"] is True
        assert result["functional"] == dv.FUNCTIONAL_PASS
        assert len(_FakeExecutor.calls) == 1
        # The run is bound to the REPAIRED digest ...
        assert result["source_sha256"] == new_digest
        # ... and the harness it executed embeds the REPAIRED bytes.
        harness = _FakeExecutor.calls[0]["bytes"].decode("utf-8")
        embedded = _embedded_app_source(harness)
        assert embedded == REPAIRED_SOURCE
        assert _sha(embedded) == new_digest
        # The harness digest and the app digest are separate values.
        assert result["harness_sha256"] != result["source_sha256"]


class TestScenariosStillRunAndCanFail:
    """Item 15 — the existing scenarios keep working and can still fail."""

    def test_a_failing_scenario_reports_functional_failure(
        self, sandbox, monkeypatch
    ):
        proposal = _seed_pending(sandbox)

        _repair(proposal, REPAIRED_SOURCE)

        new_digest = _sha(REPAIRED_SOURCE)
        consent = dv.DraftVerificationConsent()
        fresh = _mint(monkeypatch, new_digest, consent)

        _FakeExecutor.app_digest = new_digest
        result = _service(
            consent,
            [
                {"id": "alpha", "status": "PASS", "detail": ""},
                {"id": "beta", "status": "FAIL", "detail": "operator lost"},
            ],
        ).verify_draft(
            project_id=PROJECT,
            token=fresh["token"],
            scenarios=SCENARIOS,
            actor_id=ACTOR,
            session_id=SESSION,
        )

        assert result["ok"] is True
        assert result["functional"] == dv.FUNCTIONAL_FAIL
        assert result["functional"] != dv.FUNCTIONAL_PASS
        # The scenarios that reported FAIL ran against the REPAIRED bytes.
        assert _embedded_app_source(
            _FakeExecutor.calls[0]["bytes"].decode("utf-8")
        ) == REPAIRED_SOURCE
        # Verification never saves anything.
        assert not _written(sandbox)


# ===========================================================================
# 10. Existing workflows do not regress (item 16)
# ===========================================================================

class TestExistingWorkflows:
    """Item 16 — creation, save and rejection are unchanged."""

    def test_creation_without_a_pending_proposal_still_stages(self, sandbox):
        chat, calls = _chat()

        message = chat._authorized_code_file_creation(
            "یک برنامه جدید بساز (فایل app.py).", PROJECT
        )

        assert len(calls) == 1
        assert "SHA-256" in message
        assert staging.pending_proposal(PROJECT)["origin"] == "coder_model"
        assert not _written(sandbox)

    def test_rejection_still_works(self, sandbox):
        _seed_pending(sandbox)
        chat, calls = _chat()

        message = chat._authorized_code_file_approval("رد کن", PROJECT)

        assert "رد شد" in message
        assert staging.pending_proposal(PROJECT) is None
        assert calls == []

    def test_approval_turn_is_not_a_repair_turn(self, sandbox):
        _seed_pending(sandbox)
        chat, calls = _chat()

        text = "تأیید می‌کنم، همین فایل را ذخیره کن"

        assert chat._code_repair_turn(text) is False
        assert chat._authorized_code_repair(text, PROJECT) is None
        assert calls == []

    def test_architectural_request_never_enters_the_repair_branch(self, sandbox):
        _seed_pending(sandbox)
        chat, calls = _chat()

        for text in (
            "یک ویلای دو طبقه بساز",
            "پلان را اصلاح کن و نسخه جدید بده",
            "نمای ساختمان را با آجر قرمز دوباره تولید کن",
        ):
            assert chat._code_repair_turn(text) is False
            assert chat._authorized_code_repair(text, PROJECT) is None

        assert calls == []
        assert staging.pending_proposal(PROJECT)["digest"] == _sha(BASE_SOURCE)


# ===========================================================================
# 11. LIVE-STRUCTURE fixture (project_20f920b5, base 6c459f6c…)
#
# The draft that failed live on 2026-10-26 had these structural properties,
# reproduced here so the regression is portable and self-contained:
#   * a class ``Calculator`` with a buggy ``on_operator``;
#   * an initial COMMENT on the first line of ``on_operator``'s body;
#   * ``import hashlib``;
#   * a module-level ``source_code`` string literal duplicating the source;
#   * a module-level ``print(hashlib.sha256(...))``.
#
# The real draft is 44 lines; this fixture keeps the same shape, not its bytes.
# ===========================================================================

LIVE_DRAFT_SOURCE = (
    "import hashlib\n"
    "\n"
    "\n"
    "class Calculator:\n"
    "    def __init__(self):\n"
    "        self.operand1 = 0\n"
    "        self.operand2 = 0\n"
    "        self.operator = None\n"
    "        self.result = 0\n"
    "\n"
    "    def on_digit(self, digit):\n"
    "        # digits build the current operand\n"
    "        self.result = self.result * 10 + digit\n"
    "\n"
    "    def on_operator(self, op):\n"
    "        # Bug: this line removes the first operand when operator changes\n"
    "        self.operand1 = 0\n"
    "        self.operator = op\n"
    "\n"
    "\n"
    'source_code = """import hashlib\n'
    "\n"
    "class Calculator:\n"
    "    def on_operator(self, op):\n"
    "        self.operand1 = 0\n"
    '"""\n'
    "\n"
    "print(hashlib.sha256(source_code.encode()).hexdigest())\n"
)

#: The correct fix: only ``on_operator``'s body, comment preserved.
LIVE_DRAFT_REPAIRED = LIVE_DRAFT_SOURCE.replace(
    "        # Bug: this line removes the first operand when operator changes\n"
    "        self.operand1 = 0\n",
    "        # keep the first operand across operator changes\n"
    "        if self.operand1 == 0:\n"
    "            self.operand1 = self.result\n",
)

#: The live user turn named the target explicitly.
REPAIR_TEXT_LIVE = (
    "فقط باگ متد `Calculator.on_operator` را در پیش‌نویس فعلی `app.py` اصلاح کن "
    "و بقیه را تغییر نده."
)


class TestLiveDraftShape:
    """The fixture really does carry every structural trap."""

    def test_fixture_is_well_formed(self):
        tree = ast.parse(LIVE_DRAFT_SOURCE)

        assert isinstance(tree.body[0], ast.Import)
        assert tree.body[1].name == "Calculator"
        assert [m.name for m in tree.body[1].body if isinstance(m, ast.FunctionDef)] == [
            "__init__",
            "on_digit",
            "on_operator",
        ]
        assert any(
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            for node in tree.body
        )
        assert "source_code" in LIVE_DRAFT_SOURCE
        assert "print(hashlib.sha256" in LIVE_DRAFT_SOURCE

    def test_on_operator_opens_with_a_comment(self):
        node = [
            item
            for item in ast.parse(LIVE_DRAFT_SOURCE).body[1].body
            if isinstance(item, ast.FunctionDef) and item.name == "on_operator"
        ][0]

        # The comment is not an AST node, so it sits between the ``def`` line
        # and the first statement — the exact shape that broke ``_signature``.
        assert node.body[0].lineno > node.lineno + 1


class TestInitialBodyCommentIsBodyText:
    """ISSUE B — a comment at the start of the body is not the declaration."""

    def test_comment_only_edit_is_an_authorised_body_edit(self):
        comment_only = LIVE_DRAFT_SOURCE.replace(
            "        # Bug: this line removes the first operand when operator changes\n",
            "        # keep operand1; remember the operator\n",
        )

        assert comment_only != LIVE_DRAFT_SOURCE
        assert infer_changed_scope(LIVE_DRAFT_SOURCE, comment_only) == (
            "Calculator.on_operator",
            None,
        )

    def test_body_statement_and_initial_comment_together_are_accepted(self):
        assert infer_changed_scope(
            LIVE_DRAFT_SOURCE, LIVE_DRAFT_REPAIRED
        ) == ("Calculator.on_operator", None)

    def test_signature_change_is_still_rejected(self):
        # ``replace(..., 1)``: the same ``def`` line also appears inside the
        # module-level duplicate literal, and changing THAT would be an
        # out-of-scope edit rather than a signature change.
        changed = LIVE_DRAFT_SOURCE.replace(
            "    def on_operator(self, op):",
            "    def on_operator(self, op, unexpected=None):",
            1,
        )

        assert infer_changed_scope(LIVE_DRAFT_SOURCE, changed) == (
            None,
            staging.REPAIR_SIGNATURE,
        )

    def test_comment_edit_on_the_real_draft_shape_lands_in_the_store(
        self, sandbox
    ):
        proposal = _seed_pending(sandbox, source=LIVE_DRAFT_SOURCE)
        comment_only = LIVE_DRAFT_SOURCE.replace(
            "        # Bug: this line removes the first operand when operator changes\n",
            "        # keep operand1; remember the operator\n",
        )

        outcome = _repair(proposal, comment_only)

        assert outcome["status"] == "replaced"
        assert outcome["scope"] == "Calculator.on_operator"

    def test_unrelated_code_is_still_rejected(self):
        # The module-level duplicate literal drifts: outside every span.
        drifted = LIVE_DRAFT_SOURCE.replace(
            "class Calculator:\n    def on_operator(self, op):",
            "class Calculator:\n    def on_operator(self, operator):",
        )

        assert infer_changed_scope(LIVE_DRAFT_SOURCE, drifted) == (
            None,
            staging.REPAIR_OUTSIDE,
        )

    def test_module_level_print_change_is_still_rejected(self):
        drifted = LIVE_DRAFT_SOURCE.replace(
            "print(hashlib.sha256(source_code.encode()).hexdigest())",
            "print(hashlib.sha256(source_code.encode()).hexdigest().upper())",
        )

        assert infer_changed_scope(LIVE_DRAFT_SOURCE, drifted) == (
            None,
            staging.REPAIR_OUTSIDE,
        )

    def test_unnamed_repair_still_requires_a_byte_exact_whole_file(
        self, sandbox
    ):
        """The whole-file path is NOT weakened to make anything pass."""

        proposal = _seed_pending(sandbox, source=LIVE_DRAFT_SOURCE)
        drifted = LIVE_DRAFT_REPAIRED.replace(
            "print(hashlib.sha256(source_code.encode()).hexdigest())",
            "print(hashlib.sha256(source_code.encode()).hexdigest().upper())",
        )

        outcome = _repair(proposal, drifted)

        assert outcome["reason"] == staging.REPAIR_OUTSIDE
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]


class TestBoundedHandoff:
    """ISSUE C — only the named target's body comes from the model."""

    def test_splice_takes_only_the_target_body(self):
        result = staging.splice_target_body(
            LIVE_DRAFT_SOURCE, "Calculator.on_operator", LIVE_DRAFT_REPAIRED
        )

        assert result["ok"] is True
        assert result["candidate"] == LIVE_DRAFT_REPAIRED
        assert result["model_changed_outside_scope"] is False

    def test_splice_discards_drift_outside_the_span(self):
        # The model fixes the body AND rewrites module-level code.
        drifted = LIVE_DRAFT_REPAIRED.replace(
            "print(hashlib.sha256(source_code.encode()).hexdigest())",
            "print('SHA256:', hashlib.sha256(source_code.encode()).hexdigest())",
        ).replace(
            "class Calculator:\n    def on_operator(self, op):",
            "class Calculator:\n    def on_operator(self, operator):",
        )

        result = staging.splice_target_body(
            LIVE_DRAFT_SOURCE, "Calculator.on_operator", drifted
        )

        assert result["ok"] is True
        # The drift was NOT applied ...
        assert result["candidate"] == LIVE_DRAFT_REPAIRED
        assert "SHA256:" not in result["candidate"]
        # ... and it was REPORTED, not silently dropped.
        assert result["model_changed_outside_scope"] is True
        assert result["model_outside_diff_lines"] > 0

    def test_splice_preserves_base_bytes_outside_the_span_exactly(self):
        drifted = LIVE_DRAFT_REPAIRED.replace(
            "print(hashlib.sha256(source_code.encode()).hexdigest())",
            "print('SHA256:', hashlib.sha256(source_code.encode()).hexdigest())",
        )

        result = staging.splice_target_body(
            LIVE_DRAFT_SOURCE, "Calculator.on_operator", drifted
        )

        base_spans = staging._qualified_functions(ast.parse(LIVE_DRAFT_SOURCE))
        candidate_spans = staging._qualified_functions(
            ast.parse(result["candidate"])
        )

        assert staging._skeleton(
            LIVE_DRAFT_SOURCE, base_spans
        ) == staging._skeleton(result["candidate"], candidate_spans)

    def test_splice_rejects_a_signature_change(self):
        changed = LIVE_DRAFT_REPAIRED.replace(
            "    def on_operator(self, op):",
            "    def on_operator(self, op, extra=None):",
        )

        result = staging.splice_target_body(
            LIVE_DRAFT_SOURCE, "Calculator.on_operator", changed
        )

        assert result["ok"] is False
        assert result["reason"] == staging.REPAIR_SIGNATURE

    def test_splice_rejects_a_missing_model_target(self):
        result = staging.splice_target_body(
            LIVE_DRAFT_SOURCE, "Calculator.on_operator", "class Other:\n    pass\n"
        )

        assert result["ok"] is False
        assert result["reason"] == staging.SPLICE_MODEL_TARGET_MISSING

    def test_splice_rejects_an_unknown_target(self):
        result = staging.splice_target_body(
            LIVE_DRAFT_SOURCE, "Calculator.not_a_method", LIVE_DRAFT_REPAIRED
        )

        assert result["ok"] is False
        assert result["reason"] == staging.SPLICE_NO_TARGET

    def test_splice_rejects_a_no_op_body(self):
        result = staging.splice_target_body(
            LIVE_DRAFT_SOURCE, "Calculator.on_operator", LIVE_DRAFT_SOURCE
        )

        assert result["ok"] is False
        assert result["reason"] == staging.REPAIR_NO_OP

    def test_splice_rejects_a_non_python_response(self):
        result = staging.splice_target_body(
            LIVE_DRAFT_SOURCE, "Calculator.on_operator", "I cannot help with that."
        )

        assert result["ok"] is False
        assert result["reason"] == staging.REPAIR_SYNTAX

    def test_splice_rejects_a_body_at_the_wrong_indentation(self):
        base = "class C:\n    def f(self):\n        a = 1\n"
        model = "class C:\n    def f(self):\n      a = 2\n"  # 6 spaces, valid

        result = staging.splice_target_body(base, "C.f", model)

        assert result["ok"] is False
        assert result["reason"] == staging.SPLICE_INDENT


class TestLiveRepairEndToEnd:
    """The named-target repair now lands on a self-referential draft."""

    def test_named_repair_survives_outside_span_drift(self, sandbox):
        proposal = _seed_pending(sandbox, source=LIVE_DRAFT_SOURCE)

        drifted_model = LIVE_DRAFT_REPAIRED.replace(
            "print(hashlib.sha256(source_code.encode()).hexdigest())",
            "print('SHA256:', hashlib.sha256(source_code.encode()).hexdigest())",
        ).replace(
            "class Calculator:\n    def on_operator(self, op):",
            "class Calculator:\n    def on_operator(self, operator):",
        )

        chat, calls = _chat()
        chat._generate_code_with_coder = lambda text: (calls.append(text), drifted_model)[1]

        message = chat._authorized_code_repair(REPAIR_TEXT_LIVE, PROJECT)

        assert len(calls) == 1
        assert "اصلاح شد" in message
        # The model's unrelated edits were not applied and the user was told.
        assert "اعمال نشد" in message

        live = staging.pending_proposal(PROJECT)
        assert live["content"] == LIVE_DRAFT_REPAIRED
        assert live["digest"] == _sha(LIVE_DRAFT_REPAIRED)
        assert live["digest"] != proposal["digest"]
        assert live["repair"]["representation"] == "spliced_body"
        assert live["repair"]["model_changed_outside_scope"] is True
        assert live["repair"]["target"] == "Calculator.on_operator"
        assert not _written(sandbox)

    def test_named_repair_with_a_clean_model_response(self, sandbox):
        _seed_pending(sandbox, source=LIVE_DRAFT_SOURCE)
        chat, _calls = _chat(coder=lambda text: LIVE_DRAFT_REPAIRED)

        message = chat._authorized_code_repair(REPAIR_TEXT_LIVE, PROJECT)

        assert "اصلاح شد" in message
        assert "اعمال نشد" not in message
        assert staging.pending_proposal(PROJECT)["content"] == LIVE_DRAFT_REPAIRED

    def test_named_repair_still_refuses_a_broken_candidate(self, sandbox):
        proposal = _seed_pending(sandbox, source=LIVE_DRAFT_SOURCE)
        broken = LIVE_DRAFT_REPAIRED.replace(
            "            self.operand1 = self.result\n", "            self.operand1 = (\n"
        )
        chat, _calls = _chat(coder=lambda text: broken)

        message = chat._authorized_code_repair(REPAIR_TEXT_LIVE, PROJECT)

        assert staging.REPAIR_SYNTAX in message
        assert staging.pending_proposal(PROJECT)["digest"] == proposal["digest"]
        assert not _written(sandbox)

