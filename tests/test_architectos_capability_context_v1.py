# -*- coding: utf-8 -*-
"""CHAT-01 SELF-DESCRIPTION FIX — verified capability context.

Scope: the identity/capability paragraph injected into a self-introduction
turn. Nothing here touches routing, the domain layer, teaching, vision, BIM,
IFC, render or ComfyUI.

The point of this suite is that a self-description must be GROUNDED: the text
is generated from audited data, only verified capabilities are affirmed, and
frozen/unavailable functionality is explicitly prohibited.
"""

import json
from pathlib import Path

import pytest

from config.chat_config import ChatConfig, DEFAULT_CHAT_MODEL
from core.chat.architectos_capability_context_v1 import (
    NOT_OPERATIONAL,
    VERIFIED_CAPABILITIES,
    ArchitectOSCapabilityContextV1,
    self_introduction_context,
)
from core.chat.conversation_intent_boundary_v1 import (
    classify_conversation_intent,
)
from core.chat.conversational_naturalness_v1 import (
    conversation_naturalness_instruction,
    resolve_turn_register,
)
from core.llm.llm_gateway import LLMGateway


ROOT = Path(__file__).resolve().parents[1]

CHAT_01 = "سلام، خودت رو معرفی کن و بگو چه کارهایی می‌تونی انجام بدی"
MARKER = "IDENTITY AND CAPABILITY CONTEXT"

CHANGED_FILES = (
    "core/chat/architectos_capability_context_v1.py",
    "core/chat/conversational_naturalness_v1.py",
)

ACCEPTANCE_FRAGMENTS = (
    "خودت رو معرفی کن",
    "خودت را معرفی",
    "چه کارهایی",
    "چکارهایی",
)


def _source(path):
    lines = []
    for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0]
        lines.append(line)
    return "\n".join(lines)


def _signals(text):
    return classify_conversation_intent(text)["signals"]


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status
        self.text = json.dumps(body) if isinstance(body, dict) else str(body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.trust_env = True

    def post(self, url, **kwargs):
        self.calls.append({"url": url, "json": kwargs.get("json")})
        return self.response

    def get(self, url, **kwargs):
        self.calls.append({"url": url, "get": True})
        return self.response


# ==========================================================
# 1. THE CONTEXT IS DELIVERED ONLY FOR A SELF-INTRODUCTION
# ==========================================================

def test_self_introduction_receives_the_capability_context():
    block = conversation_naturalness_instruction(CHAT_01, _signals(CHAT_01))
    assert MARKER in block
    assert "LOCAL ARCHITECTURAL AI ASSISTANT" in block


def test_persian_self_introduction_without_a_greeting_receives_it():
    text = "خودت را معرفی کن و قابلیت‌هایت را توضیح بده"
    assert MARKER in conversation_naturalness_instruction(text, _signals(text))


def test_english_self_introduction_receives_it():
    text = "Who are you?"
    assert MARKER in conversation_naturalness_instruction(text, _signals(text))


@pytest.mark.parametrize("text", [
    "سلام",
    "سلام، خوبی؟",
    "چرا آسمان آبی است؟",
    "در طراحی یک فضای مسکونی چه نکاتی مهم هستند؟",
    "می‌خواهم یک نکته معماری به تو آموزش بدهم",
])
def test_ordinary_turns_never_receive_capability_context(text):
    block = conversation_naturalness_instruction(text, _signals(text))
    assert MARKER not in block


def test_unrelated_turns_are_byte_identical_with_and_without_signals():
    """A non-request turn must not change at all because the identity context
    exists in the codebase."""
    for text in ("سلام", "چرا آسمان آبی است؟", ""):
        assert (
            conversation_naturalness_instruction(text, ["subject:general"])
            == conversation_naturalness_instruction(text)
        )


# ==========================================================
# 2. PURE GREETINGS STILL STAY SHORT (previous fix intact)
# ==========================================================

def test_pure_greeting_remains_a_short_greeting():
    for text in ("سلام", "سلام، خوبی؟", "hello"):
        assert resolve_turn_register(text, _signals(text)) == "greeting"
    block = conversation_naturalness_instruction("سلام", _signals("سلام"))
    assert "ONE short natural sentence" in block
    assert MARKER not in block


def test_self_introduction_is_still_an_information_request():
    assert resolve_turn_register(CHAT_01, _signals(CHAT_01)) == "detail_request"
    block = conversation_naturalness_instruction(CHAT_01, _signals(CHAT_01))
    assert "Do NOT explain anything" not in block


# ==========================================================
# 3. CLAIMS COME FROM AUDITED DATA, NOT HARDCODED PROSE
# ==========================================================

def test_every_verified_capability_is_stated():
    text = self_introduction_context()
    for item in VERIFIED_CAPABILITIES:
        assert item["statement"] in text


def test_every_verified_capability_carries_its_evidence():
    for item in VERIFIED_CAPABILITIES:
        assert item["evidence"].strip()
        assert item["name"].strip()
        assert item["statement"].strip()


def test_context_is_generated_from_the_data_not_hardcoded(monkeypatch):
    """Replacing the audit data must change the generated text — proving the
    paragraph is derived, not a fixed string."""
    import core.chat.architectos_capability_context_v1 as cap

    monkeypatch.setattr(cap, "VERIFIED_CAPABILITIES", (
        {"name": "Only", "statement": "does only the audited thing",
         "evidence": "unit test"},
    ), raising=False)

    text = cap.self_introduction_context()
    assert "does only the audited thing" in text
    assert "natural conversation" not in text


# ==========================================================
# 4. FROZEN / UNAVAILABLE THINGS ARE NOT ADVERTISED
# ==========================================================

def test_non_operational_capabilities_appear_only_as_a_prohibition():
    text = self_introduction_context()
    assert "must NOT" in text
    affirmative = text.split("It must NOT")[0]
    for item in NOT_OPERATIONAL:
        assert item["name"] in text               # named in the prohibition
        assert item["name"] not in affirmative    # never affirmed
        assert item["reason"].strip()


@pytest.mark.parametrize("forbidden", [
    "plan generation", "CAD", "BIM", "IFC", "rendering", "ComfyUI",
    "image generation", "HouseDiffusion",
])
def test_no_frozen_pipeline_is_promised_as_an_action(forbidden):
    text = self_introduction_context().lower()
    # the only permitted mention of these is inside the prohibition clause
    head = text.split("it must not")[0]
    assert forbidden.lower() not in head


def test_context_forbids_inventing_features():
    text = self_introduction_context()
    assert "must NOT claim any other capability" in text
    assert "Do not invent extra features" in text


def test_context_keeps_the_answer_short_and_clean():
    text = self_introduction_context()
    assert "one short natural paragraph" in text
    assert "source files" in text and "modules" in text


# ==========================================================
# 5. NO UTTERANCE IS HARDCODED
# ==========================================================

@pytest.mark.parametrize("path", CHANGED_FILES)
@pytest.mark.parametrize("fragment", ACCEPTANCE_FRAGMENTS)
def test_production_never_names_the_acceptance_sentence(path, fragment):
    assert fragment not in _source(path), "%s special-cases %r" % (path, fragment)


def test_the_same_text_needs_the_signal_to_receive_the_context():
    assert MARKER not in conversation_naturalness_instruction(CHAT_01)
    assert MARKER in conversation_naturalness_instruction(
        CHAT_01, ["self_introduction"])


# ==========================================================
# 6. NO MEMORY / TEACHING / KNOWLEDGE PROMOTION
# ==========================================================

def test_capability_module_has_no_state_or_side_effects():
    cls = ArchitectOSCapabilityContextV1
    assert cls.CREATES_SECOND_ASSISTANT is False
    assert cls.CHANGES_ROUTING is False
    assert cls.MUTATES_SESSION_CONTEXT is False
    assert cls.READS_OR_WRITES_MEMORY is False
    assert cls.CALLS_AN_LLM is False
    assert cls.USES_VISION is False
    assert cls.RENDERS is False


def test_capability_context_is_pure():
    assert self_introduction_context() == self_introduction_context()


@pytest.mark.parametrize("text", [
    "می‌خواهم یک نکته معماری به تو آموزش بدهم",
    "I want to teach you an architecture rule.",
])
def test_teaching_classification_unchanged(text):
    decision = classify_conversation_intent(text)
    assert decision["intent"] == "TEACHING"
    assert "self_introduction" not in decision["signals"]


def test_capability_context_states_teaching_is_never_auto_promoted():
    text = self_introduction_context()
    assert "PENDING candidate" in text
    assert "explicit" in text and "confirmation" in text


# ==========================================================
# 7. MODEL ROUTING / GATEWAY CONTRACT UNCHANGED
# ==========================================================

def test_chat_model_default_unchanged(monkeypatch):
    monkeypatch.delenv("ARCHITECTOS_CHAT_MODEL", raising=False)
    assert DEFAULT_CHAT_MODEL == "gemma4:12b"
    assert ChatConfig.from_env().model == "gemma4:12b"


def test_capability_module_does_not_touch_model_config():
    source = _source("core/chat/architectos_capability_context_v1.py")
    assert "chat_config" not in source
    assert "ARCHITECTOS_CHAT_MODEL" not in source
    assert "ARCHITECTOS_VISION_MODEL" not in source


def test_llm_request_still_sends_think_false(monkeypatch):
    monkeypatch.delenv("ARCHITECTOS_CHAT_THINK", raising=False)
    gateway = LLMGateway()
    session = FakeSession(FakeResponse({"response": "ok"}))
    gateway.session = session
    gateway.generate("hi")
    assert session.calls[0]["json"]["think"] is False


def test_thinking_channel_is_never_returned(monkeypatch):
    monkeypatch.delenv("ARCHITECTOS_CHAT_THINK", raising=False)
    gateway = LLMGateway()
    gateway.session = FakeSession(
        FakeResponse({"response": "پاسخ", "thinking": "راز درونی"})
    )
    out = gateway.generate("hi")
    assert out == "پاسخ"
    assert "راز درونی" not in out


def test_missing_model_is_still_not_faked(monkeypatch):
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "definitely-not-installed:99b")
    gateway = LLMGateway()
    gateway.session = FakeSession(FakeResponse({"error": "x"}, status=404))
    assert gateway.generate("hi") is None
    assert gateway.last_error.startswith("model_not_installed:")


def test_empty_response_is_still_a_failure():
    gateway = LLMGateway()
    gateway.session = FakeSession(FakeResponse({"response": ""}))
    assert gateway.generate("hi") is None
    assert gateway.last_error == "empty_response"
