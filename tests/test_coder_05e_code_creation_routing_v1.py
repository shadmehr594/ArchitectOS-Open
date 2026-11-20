"""CODER-05E — an explicit code-file creation request must reach the code boundary.

Live failure this pins (project_f043688f, 2026-10-25 21:34:35): a 1 659-character
calculator request was routed

    {'intent': 'chat', 'mode': 'conversation'}

so the code capability boundary never opened. The GENERAL chat model
(qwen3.8:27b) answered with prose plus a code block that was TRUNCATED
mid-function — no staging, no SHA-256, no syntax report — while claiming to
provide all three. A 287-character request for the same thing routed correctly,
and `_programming_request_kind()` returns "code_file" for BOTH.

The fix opens the boundary on an explicit create verb plus the existing
programming classifier, so a misclassification can no longer hand a creation
turn to the general model.

No source is executed. No file is written.
"""

import ast
import json
import os

import pytest

from core.chat.chat_architect import ChatArchitect


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHAT_JSON = os.path.join(
    ROOT, "data", "projects", "project_f043688f", "conversations", "chat.json"
)

# A prose-heavy app request: it mentions a .py path (so the programming
# classifier sees a code file), contains a create verb, and — like the real
# request — contains "نمایش", whose substring "نما" collides with the
# architectural vocabulary.
LONG_REQUEST = (
    "یک ماشین‌حساب گرافیکی برای ویندوز با Python و Tkinter بساز. "
    "می‌خواهم کد برنامه را خودت از نو تولید کنی، نه اینکه کد قدیمی گفت‌وگو را "
    "دوباره نمایش بدهی. نمایش اعداد بزرگ و کوچک باید دقیق باشد. "
    "خروجی: کد کامل، نتیجه بررسی نحو، SHA-256، و مسیر documents/code/app.py. "
    "هیچ فایلی ذخیره یا اجرا نکن."
)

SHORT_REQUEST = (
    "یک ماشین‌حساب گرافیکی برای ویندوز با Python و Tkinter بساز. "
    "چیدمان چهار ستون، اعشار، و فایل app.py."
)

# Questions / design turns that must NOT be dragged onto the code boundary.
CASUAL_CODE_QUESTION = "این فایل app.py چیست؟"
ARCHITECTURAL_REQUEST = "یک ویلای دو طبقه با نمای آجری بساز"
ARCHITECTURAL_PLAN = "پلان طبقه همکف را بساز"


def _chat():
    chat = object.__new__(ChatArchitect)
    chat.context = {}
    return chat


def _gate(chat, text, intent="chat", mode="conversation"):
    """Mirror the _handle_internal gate that precedes the code boundary."""
    return bool(
        (intent == "code" and mode == "capability")
        or chat._staging_action_turn(text)
        or chat._code_file_creation_turn(text)
    )


# --------------------------------------------------------------------------
# the gate opens for real creation requests
# --------------------------------------------------------------------------


def test_long_prose_request_opens_the_code_boundary():
    chat = _chat()

    assert _gate(chat, LONG_REQUEST, intent="chat", mode="conversation") is True


def test_short_request_still_opens_the_code_boundary():
    assert _chat()._code_file_creation_turn(SHORT_REQUEST) is True


def test_real_failing_request_from_the_project_opens_the_boundary():
    """The exact 1 659-character turn that was misrouted."""
    if not os.path.isfile(CHAT_JSON):
        pytest.skip("project conversation not present")

    with open(CHAT_JSON, encoding="utf-8") as handle:
        data = json.load(handle)

    candidates = [
        message.get("text") or ""
        for message in data.get("messages") or []
        if message.get("role") == "user"
    ]

    request = next((text for text in candidates if len(text) > 1500), None)

    if not request:
        pytest.skip("long request not found in the conversation")

    assert _chat()._code_file_creation_turn(request) is True


# --------------------------------------------------------------------------
# the gate stays closed for turns that are not creation requests
# --------------------------------------------------------------------------


def test_casual_question_about_a_code_file_stays_chat():
    """Mentions app.py but asks nothing to be created."""
    assert _chat()._code_file_creation_turn(CASUAL_CODE_QUESTION) is False


@pytest.mark.parametrize(
    "text", [ARCHITECTURAL_REQUEST, ARCHITECTURAL_PLAN]
)
def test_architectural_requests_are_not_code_turns(text):
    assert _chat()._code_file_creation_turn(text) is False


def test_empty_and_non_string_input_is_safe():
    chat = _chat()

    assert chat._code_file_creation_turn("") is False
    assert chat._code_file_creation_turn(None) is False
    assert chat._code_file_creation_turn(123) is False


# --------------------------------------------------------------------------
# CODER-05B/C/D must be untouched
# --------------------------------------------------------------------------


def test_staging_action_turns_still_open_the_gate():
    assert _gate(_chat(), "رد کن", intent="chat") is True
    assert _gate(_chat(), "تأیید می‌کنم، فایل app.py را ذخیره کن") is True


def test_plain_chat_still_does_not_open_the_gate():
    assert _gate(_chat(), "سلام، حالت چطوره؟") is False


# --------------------------------------------------------------------------
# structural guard: the gate must keep consulting the new predicate
# --------------------------------------------------------------------------


def test_code_boundary_gate_consults_both_predicates():
    path = os.path.join(ROOT, "core", "chat", "chat_architect.py")

    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    gates = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.If):
            continue

        body = ast.dump(ast.Module(body=node.body, type_ignores=[]))

        if "_authorized_code_file_approval" in body:
            gates.append(node)

    assert gates, "the code-capability branch must still call the approval path"

    for gate in gates:

        test_dump = ast.dump(gate.test)

        assert "_staging_action_turn" in test_dump, (
            "CODER-05D regression: approve/reject turns would fall to chat"
        )

        assert "_code_file_creation_turn" in test_dump, (
            "CODER-05E regression: a misrouted creation request would be "
            "answered by the general chat model with unverified source"
        )
