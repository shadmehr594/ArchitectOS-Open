# -*- coding: utf-8 -*-
"""CHAT-01 CONTENT FIX — conversational register for self-introduction turns.

Scope: the CHAT turn-register layer only (the shape/tone of the reply). This
file touches no routing, no domain classification, no teaching flow, no
vision provider, no BIM/IFC/render/ComfyUI path.

The fix is SIGNAL-driven, never utterance-driven. The exact acceptance
sentence appears in this file only as a test payload; production code must
never name it. `test_the_same_text_changes_register_only_because_of_the_signal`
is the proof of that property.
"""

import json
from pathlib import Path

import pytest

from config.chat_config import ChatConfig, DEFAULT_CHAT_MODEL
from core.chat.chat_architect import ChatArchitect  # noqa: F401  (import guard)
from core.chat.conversational_naturalness_v1 import (
    ConversationalNaturalnessV1,
    conversation_naturalness_instruction,
    resolve_turn_register,
)
from core.chat.conversation_intent_boundary_v1 import (
    classify_conversation_intent,
)
from core.llm.llm_gateway import LLMGateway


ROOT = Path(__file__).resolve().parents[1]

# The exact CHAT-01 acceptance utterance — a PAYLOAD here, never production.
CHAT_01 = "سلام، خودت رو معرفی کن و بگو چه کارهایی می‌تونی انجام بدی"

# Production files this change owns.
CHANGED_FILES = (
    "core/chat/conversational_naturalness_v1.py",
    "core/chat/chat_architect.py",
)

# Fragments that must never appear in production logic.
ACCEPTANCE_FRAGMENTS = (
    "خودت رو معرفی کن",
    "خودت را معرفی",
    "چه کارهایی",
    "چکارهایی",
)


def _source(path):
    """Source with comment-only lines and trailing comments removed."""
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
    """The CURRENT turn's real structured signals, from the boundary."""
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
# 1. PURE GREETING REMAINS A SHORT GREETING
# ==========================================================

@pytest.mark.parametrize("text", [
    "سلام",
    "سلام، خوبی؟",
    "درود",
    "صبح بخیر",
    "hello",
    "Hi, how are you",
])
def test_pure_greeting_stays_a_short_greeting(text):
    assert resolve_turn_register(text, _signals(text)) == "greeting"


def test_pure_greeting_instruction_stays_brief():
    block = conversation_naturalness_instruction("سلام", _signals("سلام"))
    assert "ONE short natural sentence" in block


# ==========================================================
# 2/3/4. GREETING + SUBSTANTIVE REQUEST IS NOT A GREETING
# ==========================================================

def test_greeting_plus_self_introduction_is_an_information_request():
    assert resolve_turn_register(CHAT_01, _signals(CHAT_01)) == "detail_request"


def test_self_introduction_without_a_greeting_works():
    text = "خودت را معرفی کن و قابلیت‌هایت را توضیح بده"
    assert resolve_turn_register(text, _signals(text)) == "detail_request"


def test_greeting_plus_factual_question_is_not_downgraded():
    text = "سلام، می‌توانی توضیح بدهی چرا آسمان آبی است؟"
    assert resolve_turn_register(text, _signals(text)) == "detail_request"


def test_greeting_plus_factual_question_without_question_mark():
    text = "سلام، توضیح بده چرا آسمان آبی است"
    assert resolve_turn_register(text, _signals(text)) == "detail_request"


def test_information_request_instruction_drops_the_greeting_rule():
    block = conversation_naturalness_instruction(CHAT_01, _signals(CHAT_01))
    assert "Do NOT explain anything" not in block
    assert "ONE short natural sentence" not in block
    assert "asking for explanation or detail" in block


# ==========================================================
# 5. ENGLISH EQUIVALENTS
# ==========================================================

def test_english_greeting_stays_a_greeting():
    assert resolve_turn_register("hello", _signals("hello")) == "greeting"


def test_english_self_introduction_is_an_information_request():
    text = "Who are you?"
    assert resolve_turn_register(text, _signals(text)) == "detail_request"


def test_english_greeting_plus_request_is_not_downgraded():
    text = "Hi, introduce yourself and tell me what you can do"
    assert resolve_turn_register(text, _signals(text)) == "detail_request"


# ==========================================================
# 6. SIGNAL-DRIVEN, NOT UTTERANCE-DRIVEN  (the core proof)
# ==========================================================

def test_the_same_text_changes_register_only_because_of_the_signal():
    """The identical sentence must flip register ONLY when the structured
    boundary signal is supplied. That is what makes this a signal fix rather
    than a hardcoded sentence fix."""
    assert resolve_turn_register(CHAT_01) == "greeting"           # no signals
    assert resolve_turn_register(CHAT_01, ["self_introduction"]) == "detail_request"
    assert resolve_turn_register(CHAT_01, _signals(CHAT_01)) == "detail_request"


def test_a_bare_greeting_is_promoted_by_the_signal_not_by_its_text():
    """Even a one-word greeting follows the signal — proving the branch reads
    the signal, not a phrase."""
    assert resolve_turn_register("سلام") == "greeting"
    assert resolve_turn_register("سلام", ["self_introduction"]) == "detail_request"


def test_unrelated_signals_do_not_change_the_register():
    """A generic (non-request) signal must not promote a greeting."""
    for generic in (["subject:general"], [], None):
        assert resolve_turn_register("سلام", generic) == "greeting"


@pytest.mark.parametrize("path", CHANGED_FILES)
@pytest.mark.parametrize("fragment", ACCEPTANCE_FRAGMENTS)
def test_production_never_names_the_acceptance_sentence(path, fragment):
    assert fragment not in _source(path), "%s special-cases %r" % (path, fragment)


def test_production_register_is_not_a_persian_phrase_list():
    """The register layer must stay free of request-vocabulary additions:
    only the greeting/detail/topic markers that already existed may be there."""
    source = _source("core/chat/conversational_naturalness_v1.py")
    assert "self_introduction" in source          # it reads the SIGNAL
    assert "_REQUEST_SIGNALS" in source           # declared as a contract


# ==========================================================
# BACKWARD COMPATIBILITY (omitted `signals` => previous behaviour)
# ==========================================================

@pytest.mark.parametrize("text,expected", [
    ("سلام", "greeting"),
    ("سلام، خوبی؟", "greeting"),
    ("چرا آسمان آبی است؟", "detail_request"),
    ("", "casual_chat"),
])
def test_omitting_signals_preserves_previous_behaviour(text, expected):
    assert resolve_turn_register(text) == expected


def test_class_helper_accepts_signals():
    naturalness = ConversationalNaturalnessV1()
    assert naturalness.register(CHAT_01, _signals(CHAT_01)) == "detail_request"
    assert "asking for explanation or detail" in naturalness.instruction(
        CHAT_01, _signals(CHAT_01)
    )


# ==========================================================
# 7. TEACHING ISOLATION IS INTACT
# ==========================================================

@pytest.mark.parametrize("text", [
    "میخوام یه نکته معماری بهت یاد بدم",
    "I want to teach you an architecture rule.",
])
def test_teaching_classification_is_unchanged(text):
    decision = classify_conversation_intent(text)
    assert decision["intent"] == "TEACHING"
    assert "self_introduction" not in decision["signals"]


def test_naturalness_layer_does_not_classify_intent():
    """It must consume the boundary decision, never re-derive it."""
    source = _source("core/chat/conversational_naturalness_v1.py")
    assert "classify_conversation_intent" not in source
    assert "conversation_intent_boundary" not in source


# ==========================================================
# 8. NO MEMORY / KNOWLEDGE PROMOTION, NO SIDE EFFECTS
# ==========================================================

def test_naturalness_layer_has_no_memory_or_assistant_surface():
    cls = ConversationalNaturalnessV1
    assert cls.CREATES_SECOND_ASSISTANT is False
    assert cls.CHANGES_ROUTING is False
    assert cls.MUTATES_SESSION_CONTEXT is False
    assert cls.RENDERS is False
    assert cls.USES_VISION is False
    assert cls.TOUCHES_STT is False
    assert cls.TOUCHES_TTS is False


def test_instruction_is_a_pure_function():
    first = conversation_naturalness_instruction(CHAT_01, _signals(CHAT_01))
    second = conversation_naturalness_instruction(CHAT_01, _signals(CHAT_01))
    assert isinstance(first, str)
    assert first == second


# ==========================================================
# 9. MODEL ROUTING IS UNCHANGED BY THIS FIX
# ==========================================================

def test_chat_model_default_is_unchanged(monkeypatch):
    monkeypatch.delenv("ARCHITECTOS_CHAT_MODEL", raising=False)
    assert DEFAULT_CHAT_MODEL == "gemma4:12b"
    assert ChatConfig.from_env().model == "gemma4:12b"


def test_naturalness_layer_does_not_read_the_model_config():
    source = _source("core/chat/conversational_naturalness_v1.py")
    assert "chat_config" not in source
    assert "ARCHITECTOS_CHAT_MODEL" not in source


# ==========================================================
# 10/11/12. GATEWAY CONTRACT STILL HOLDS
# ==========================================================

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


def test_missing_model_is_still_reported_not_faked(monkeypatch):
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "definitely-not-installed:99b")
    gateway = LLMGateway()
    gateway.session = FakeSession(FakeResponse({"error": "not found"}, status=404))
    assert gateway.generate("hi") is None
    assert gateway.last_error == "model_not_installed:definitely-not-installed:99b"


def test_empty_response_is_still_not_a_success(monkeypatch):
    gateway = LLMGateway()
    gateway.session = FakeSession(FakeResponse({"response": ""}))
    assert gateway.generate("hi") is None
    assert gateway.last_error == "empty_response"
