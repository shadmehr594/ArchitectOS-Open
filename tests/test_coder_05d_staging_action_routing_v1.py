"""CODER-05D — a staging approve/reject turn must not be routed to chat.

Live defect these tests pin: in `project_f043688f` the user sent «رد کن» and
ArchitectOS answered «باشه، رد شد.» — the general chat model — while the
proposal stayed pending. The intent router classified the utterance
``subject:general`` → ``chat/conversation``, and the staging handler was gated
behind ``intent == "code" and mode == "capability"``, so it was never called.

The pending proposal is server-side authority. A generic chat acknowledgment
must never be able to impersonate a successful (or failed) staging action.

No generated source is executed. Rejection never writes; the one staging call
uses a pytest temporary ``documents_root``.
"""

import ast
import os

import pytest

from core.chat.chat_architect import ChatArchitect
from core.chat.code_file_staging_v1 import (
    pending_proposal,
    reset_staging,
    stage_code_file,
)

SOURCE = "def add(a, b):\n    return a + b"


def _auth(project="project_a", session="lss_session_a", actor="lsa_actor_a"):
    return {
        "trusted": True,
        "actor_id": actor,
        "session_id": session,
        "project_id": project,
        "source": "trusted_local_ui_proxy",
    }


@pytest.fixture(autouse=True)
def _clean_staging():
    reset_staging()
    yield
    reset_staging()


@pytest.fixture
def docs(tmp_path):
    path = tmp_path / "documents"
    path.mkdir()
    return str(path)


def _chat(authorization=None):
    chat = object.__new__(ChatArchitect)
    chat.context = {}
    if authorization is not None:
        chat.context["trusted_local_authorization"] = authorization
    return chat


def _route(chat, text, project, intent="chat", mode="conversation"):
    """Mirror the _handle_internal gate that precedes the code boundary.

    This is the exact ordering the real route uses: the staging gate is
    evaluated together with (not after) the intent/mode pair, so a
    chat-classified turn still reaches the staging handler.
    """
    if (intent == "code" and mode == "capability") or chat._staging_action_turn(
        text
    ):
        return chat._authorized_code_file_approval(text, project)
    return None  # would fall through to the general conversation branch


# --------------------------------------------------------------------------
# 1. the literal Persian rejection is recognised as a staging action
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["رد کن", "ردش کن", "لغو کن", "انصراف", "reject", "do not save"],
)
def test_rejection_utterances_open_the_staging_gate(text):
    assert _chat()._staging_action_turn(text) is True


@pytest.mark.parametrize(
    "text",
    ["تأیید می‌کنم، فایل app.py را ذخیره کن", "approve and save", "confirm"],
)
def test_approval_utterances_open_the_staging_gate(text):
    assert _chat()._staging_action_turn(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "سلام",
        "یک ماشین‌حساب گرافیکی بساز",
        "این ساختمان چند طبقه دارد؟",
        "یک فایل جدید بساز",
    ],
)
def test_ordinary_turns_do_not_open_the_staging_gate(text):
    assert _chat()._staging_action_turn(text) is False


# --------------------------------------------------------------------------
# 2. a chat-classified rejection still reaches the staging handler
# --------------------------------------------------------------------------


def test_chat_classified_rejection_rejects_the_proposal(docs):
    auth = _auth()
    stage_code_file(
        "project_a", "app.py", SOURCE,
        documents_root=docs, authorization=auth, origin="coder_model",
    )
    assert pending_proposal("project_a") is not None

    reply = _route(
        _chat(auth), "رد کن", "project_a", intent="chat", mode="conversation"
    )

    assert reply is not None, "the turn must not fall through to general chat"
    assert "پیش‌نویس فایل" in reply
    assert "رد شد" in reply
    assert "رد نشد" not in reply
    assert pending_proposal("project_a") is None
    assert not os.path.exists(os.path.join(docs, "code", "app.py"))


def test_chat_classified_rejection_never_reaches_the_model(docs):
    """The gate must return a staging reply, not None (which means "chat")."""
    auth = _auth()
    stage_code_file(
        "project_a", "app.py", SOURCE,
        documents_root=docs, authorization=auth, origin="coder_model",
    )

    reply = _route(
        _chat(auth), "رد کن", "project_a", intent="chat", mode="conversation"
    )

    # A None return is exactly what lets the general model answer
    # «باشه، رد شد.» — the impersonation this fix removes.
    assert reply is not None
    assert "باشه" not in reply


def test_rejection_of_a_foreign_session_reports_failure_not_success(docs):
    auth = _auth()
    stage_code_file(
        "project_a", "app.py", SOURCE,
        documents_root=docs, authorization=auth, origin="coder_model",
    )
    intruder = _auth(session="lss_session_intruder")

    reply = _route(
        _chat(intruder), "رد کن", "project_a",
        intent="chat", mode="conversation",
    )

    assert reply is not None
    assert "رد نشد" in reply
    assert "approval_session_mismatch" in reply
    assert pending_proposal("project_a") is not None


def test_rejection_with_no_pending_proposal_is_still_terminal():
    reply = _route(
        _chat(_auth()), "رد کن", "project_a",
        intent="chat", mode="conversation",
    )

    assert reply is not None
    assert "نیست" in reply or "پیش‌نویس" in reply


# --------------------------------------------------------------------------
# 3. the approval analogue cannot be impersonated either
# --------------------------------------------------------------------------


def test_chat_classified_approval_resolves_against_the_staging_store():
    """No proposal: the gate must still answer, never hand it to the model."""
    reply = _route(
        _chat(_auth()), "تأیید می‌کنم، فایل app.py را ذخیره کن", "project_a",
        intent="chat", mode="conversation",
    )

    assert reply is not None
    assert "پیش‌نویس" in reply


# --------------------------------------------------------------------------
# 4. structural guard: the gate must stay wired into the real dispatch
# --------------------------------------------------------------------------


def test_code_boundary_gate_consults_the_staging_predicate():
    source = open(
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "core", "chat", "chat_architect.py",
        ),
        encoding="utf-8",
    ).read()
    tree = ast.parse(source)

    gates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        body_dump = ast.dump(ast.Module(body=node.body, type_ignores=[]))
        if "_authorized_code_file_approval" in body_dump:
            gates.append(node)

    assert gates, "the code-capability branch must still call the approval path"
    for gate in gates:
        assert "_staging_action_turn" in ast.dump(gate.test), (
            "the code boundary must be opened by _staging_action_turn, "
            "otherwise a chat-classified 'رد کن' never reaches the staging store"
        )
