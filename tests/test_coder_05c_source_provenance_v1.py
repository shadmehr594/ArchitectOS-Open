"""CODER-05C — source provenance for application creation.

The defect these tests pin: ``_source_code_from_history_or_coder()`` used to
scan conversation history FIRST and return the first fenced Python block it
found, so a request to build a NEW application was answered with the previous
application's bytes under ``origin="conversation_history"`` and the coding
model was never invoked.

Contract:

* a build/regenerate turn ALWAYS reaches the coding model;
* history is used only when the turn explicitly asks to save/reuse existing code;
* a model failure is reported as a failure — never back-filled with old bytes;
* provenance and digest stay accurate;
* no file is written and no approval is bypassed.

No generated source is executed. Writes go to pytest temporary directories.
"""

import hashlib

import pytest

from core.chat.chat_architect import ChatArchitect
import core.chat.code_file_staging_v1 as staging
from core.chat.code_file_staging_v1 import (
    approve_staged_file,
    pending_proposal,
    reset_staging,
    stage_code_file,
)
from core.project.conversation_store_v1 import conversation_store

# Stored WITHOUT a trailing newline: ``extract_python_code`` strips it, so the
# canonical form keeps the digests comparable.
HISTORY_SOURCE = "def old_app():\n    return 'stale'"
MODEL_SOURCE = "def new_app():\n    return 'fresh'"

HISTORY_DIGEST = hashlib.sha256(HISTORY_SOURCE.encode("utf-8")).hexdigest()
MODEL_DIGEST = hashlib.sha256(MODEL_SOURCE.encode("utf-8")).hexdigest()

NEW_REQUEST = "یک ماشین‌حساب گرافیکی برای ویندوز با Python و Tkinter بساز."
REUSE_REQUEST = "کد بالا را در app.py ذخیره کن"


def _fenced(code):
    return "پیش‌نویس:\n```python\n%s\n```\n" % code


def _chat():
    chat = object.__new__(ChatArchitect)
    chat.context = {}
    return chat


def _auth(project="project_a"):
    return {
        "trusted": True,
        "actor_id": "lsa_actor_a",
        "session_id": "lss_session_a",
        "project_id": project,
        "source": "trusted_local_ui_proxy",
    }


@pytest.fixture(autouse=True)
def _clean_staging():
    reset_staging()
    yield
    reset_staging()


@pytest.fixture
def history(monkeypatch):
    """This project already holds a previously generated application."""
    state = {
        "messages": [
            {"role": "user", "text": "یک برنامه بساز"},
            {"role": "assistant", "text": _fenced(HISTORY_SOURCE)},
        ]
    }
    monkeypatch.setattr(conversation_store, "load", lambda pid: state)
    return state


@pytest.fixture
def empty_history(monkeypatch):
    monkeypatch.setattr(conversation_store, "load", lambda pid: {"messages": []})


@pytest.fixture
def model(monkeypatch):
    """A coding model that records every call and returns fresh source."""
    calls = []

    class FakeGateway:
        def generate(self, prompt, **kwargs):
            calls.append(prompt)
            return _fenced(MODEL_SOURCE)

    monkeypatch.setattr(
        "core.chat.chat_architect.coder_gateway", lambda: FakeGateway()
    )
    return calls


@pytest.fixture
def broken_model(monkeypatch):
    """A coding model that is reachable but fails."""
    calls = []

    class BrokenGateway:
        def generate(self, prompt, **kwargs):
            calls.append(prompt)
            raise RuntimeError("ollama unreachable")

    monkeypatch.setattr(
        "core.chat.chat_architect.coder_gateway", lambda: BrokenGateway()
    )
    return calls


@pytest.fixture
def docs(tmp_path):
    path = tmp_path / "documents"
    path.mkdir()
    return str(path)


# --------------------------------------------------------------------------
# 1. history must never satisfy a new creation request
# --------------------------------------------------------------------------


def test_new_creation_request_calls_the_model_despite_history(history, model):
    code, origin = _chat()._source_code_from_history_or_coder(
        NEW_REQUEST, "project_a", "app.py"
    )

    assert len(model) == 1, "the coding model must be called exactly once"
    assert origin == "coder_model"
    assert code == MODEL_SOURCE
    assert code != HISTORY_SOURCE
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == MODEL_DIGEST


def test_regenerate_turn_beats_the_reuse_vocabulary(history, model):
    """"the previous code, regenerate it" is generation, not reuse."""
    code, origin = _chat()._source_code_from_history_or_coder(
        "کد قبلی را از نو بساز", "project_a", "app.py"
    )

    assert len(model) == 1
    assert origin == "coder_model"
    assert code == MODEL_SOURCE


# --------------------------------------------------------------------------
# 2. explicit reuse stays bounded and never invokes the model
# --------------------------------------------------------------------------


def test_explicit_reuse_uses_history_without_calling_the_model(history, model):
    code, origin = _chat()._source_code_from_history_or_coder(
        REUSE_REQUEST, "project_a", "app.py"
    )

    assert model == [], "a save/reuse turn must not spend a model call"
    assert origin == "conversation_history"
    assert code == HISTORY_SOURCE
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == HISTORY_DIGEST


def test_reuse_lookup_is_scoped_to_the_requesting_project(
    history, model, monkeypatch
):
    """History is read for THIS project id only."""
    seen = []

    def _load(project_id):
        seen.append(project_id)
        return {"messages": []}

    monkeypatch.setattr(conversation_store, "load", _load)

    code, origin = _chat()._source_code_from_history_or_coder(
        REUSE_REQUEST, "project_zzz", "app.py"
    )

    assert seen == ["project_zzz"]
    assert (code, origin) == (None, None)
    assert model == []


def test_reuse_with_empty_history_does_not_borrow_a_generation(
    empty_history, model
):
    code, origin = _chat()._source_code_from_history_or_coder(
        REUSE_REQUEST, "project_a", "app.py"
    )

    assert (code, origin) == (None, None)
    assert model == []


# --------------------------------------------------------------------------
# 3. model failure is reported truthfully, never back-filled
# --------------------------------------------------------------------------


def test_model_failure_is_not_backfilled_with_history(history, broken_model):
    code, origin = _chat()._source_code_from_history_or_coder(
        NEW_REQUEST, "project_a", "app.py"
    )

    assert len(broken_model) == 1
    assert code is None
    assert origin is None


def test_creation_caller_reports_failure_and_stages_nothing(
    history, broken_model
):
    chat = _chat()

    reply = chat._authorized_code_file_creation(NEW_REQUEST, "project_a")

    assert reply is not None
    assert "پیدا نشد" in reply
    assert pending_proposal("project_a") is None


def test_no_misleading_proposal_is_staged_on_model_failure(history, broken_model):
    chat = _chat()

    chat._authorized_code_file_creation(NEW_REQUEST, "project_a")

    # The only acceptable outcomes are "no proposal" — never a proposal that
    # silently carries the old bytes.
    proposal = pending_proposal("project_a")
    assert proposal is None


# --------------------------------------------------------------------------
# 4. provenance and digest stay accurate
# --------------------------------------------------------------------------


def test_staged_digest_and_origin_match_the_model_output(docs, history, model):
    chat = _chat()

    code, origin = chat._source_code_from_history_or_coder(
        NEW_REQUEST, "project_a", "app.py"
    )

    assert origin == "coder_model"
    assert len(model) == 1

    proposal = stage_code_file(
        "project_a", "app.py", code,
        documents_root=docs,
        authorization=_auth(),
        origin=origin,
    )

    assert proposal["status"] == "awaiting_approval"
    assert proposal["digest"] == MODEL_DIGEST
    assert proposal["origin"] == "coder_model"
    assert proposal["preview"] == MODEL_SOURCE
    assert proposal["syntax_valid"] is True


# --------------------------------------------------------------------------
# 5. no unauthorized write, no approval bypass
# --------------------------------------------------------------------------


def test_staged_output_is_not_written_without_approval(docs):
    import os

    stage_code_file(
        "project_a", "app.py", MODEL_SOURCE,
        documents_root=docs, authorization=_auth(), origin="coder_model",
    )

    assert pending_proposal("project_a") is not None
    assert not os.path.exists(os.path.join(docs, "code", "app.py"))


def test_approval_without_trusted_authorization_is_refused(docs):
    import os

    stage_code_file(
        "project_a", "app.py", MODEL_SOURCE,
        documents_root=docs, authorization=_auth(), origin="coder_model",
    )

    refused = approve_staged_file(
        "project_a", "approve and save", documents_root=docs,
        authorization=None, approval_token="stg_anything",
    )

    assert refused["status"] == "failed"
    assert refused["reason"] == "trusted_authorization_required"
    assert refused["writes_performed"] == 0
    assert not os.path.exists(os.path.join(docs, "code", "app.py"))
    assert pending_proposal("project_a") is not None
