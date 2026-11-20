# -*- coding: utf-8 -*-
"""CHAT-02 — GENERAL CONVERSATION CONTINUITY V1.

Scope: the CHAT turn's conversational context. Nothing here touches routing,
the domain layer, teaching, vision, BIM, IFC, render or ComfyUI.

Two defects are locked down here:

1. The recent turns were BLANKED before prompt assembly, so a follow-up
   question ("with regard to what you said before") had no conversational
   anchor and a stored profile interest could hijack it.
2. The in-process conversation store is shared by every session, so the
   history must be read back SESSION-SCOPED or one conversation leaks into
   another.

The deterministic tests below need no model. Model-dependent acceptance lives
in `LiveConversationAcceptance`, gated behind ARCHITECTOS_LIVE_CHAT_TESTS=1 so
a unit run never depends on Ollama.
"""

import json
import os
from pathlib import Path

import pytest

from config.chat_config import ChatConfig, DEFAULT_CHAT_MODEL
from core.chat.conversation_intent_boundary_v1 import classify_conversation_intent
from core.chat.conversational_naturalness_v1 import (
    conversation_naturalness_instruction,
    resolve_turn_register,
)
from core.llm.llm_gateway import LLMGateway
from core.memory.context_builder import ContextBuilder
from core.memory.conversation_memory import ConversationMemory, ConversationWriteBack
from core.memory.memory_fusion import MemoryFusion


ROOT = Path(__file__).resolve().parents[1]

CHAT_PATH = "core/chat/chat_architect.py"
NATURALNESS_PATH = "core/chat/conversational_naturalness_v1.py"
MEMORY_FILES = (
    "core/memory/conversation_memory.py",
    "core/memory/memory_manager.py",
    "core/memory/memory_fusion.py",
    "core/memory/context_builder.py",
)

# The exact CHAT-02 acceptance utterances — PAYLOADS here, never production.
READING = "می خوام یکم درباره مطالعه حرف بزنیم. به نظرت چرا بعضی آدم‌ها از کتاب خوندن لذت می‌برن؟"
MYSTERY = "من بیشتر داستان‌های معمایی رو دوست دارم. با توجه به حرف قبلیت، به نظرت چرا این سبک برام جذابه؟"
MYSTERY_2 = "پس به نظرت چه ویژگی‌هایی باعث می‌شه یه داستان معمایی واقعاً خوب باشه؟"

ACCEPTANCE_FRAGMENTS = (
    "درباره مطالعه حرف بزنیم",
    "داستان‌های معمایی",
    "داستان معمایی",
    "چرا آسمان آبی است",
)


def _source(path):
    lines = []
    for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0]
        lines.append(line)
    return "\n".join(lines)


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
# 1-3. SESSION HISTORY: RETENTION, ORDERING, SCOPING
# ==========================================================

def test_history_retains_user_and_assistant_turns():
    m = ConversationMemory()
    m.add("u1", "user", session_id="s1")
    m.add("a1", "assistant", session_id="s1")
    got = m.history(20, session_id="s1")
    assert [i["message"] for i in got] == ["u1", "a1"]
    assert [i["type"] for i in got] == ["user", "assistant"]


def test_history_is_chronological():
    m = ConversationMemory()
    for i in range(5):
        m.add("m%d" % i, "user", session_id="s1")
    assert [i["message"] for i in m.history(20, session_id="s1")] == \
        ["m0", "m1", "m2", "m3", "m4"]


def test_history_is_session_scoped():
    """The store is one in-process list; a read must never cross sessions."""
    m = ConversationMemory()
    m.add("A-u1", "user", session_id="A")
    m.add("A-a1", "assistant", session_id="A")
    m.add("B-u1", "user", session_id="B")
    m.add("B-a1", "assistant", session_id="B")
    m.add("A-u2", "user", session_id="A")

    a = [i["message"] for i in m.history(20, session_id="A")]
    b = [i["message"] for i in m.history(20, session_id="B")]
    assert a == ["A-u1", "A-a1", "A-u2"]
    assert b == ["B-u1", "B-a1"]
    assert not set(a) & set(b)


def test_history_limit_is_applied_per_session():
    m = ConversationMemory()
    for i in range(30):
        m.add("A-%d" % i, "user", session_id="A")
    for i in range(30):
        m.add("B-%d" % i, "user", session_id="B")
    a = m.history(5, session_id="A")
    assert [i["message"] for i in a] == ["A-25", "A-26", "A-27", "A-28", "A-29"]


def test_omitting_session_id_preserves_legacy_behaviour():
    m = ConversationMemory()
    m.add("x", "user")
    m.add("y", "assistant")
    assert len(m.history(20)) == 2


def test_writeback_threads_the_session_id():
    m = ConversationMemory()

    class _MM:
        def save_conversation(self, message, message_type="chat", session_id=None):
            m.add(message, message_type, session_id=session_id)

    ConversationWriteBack(_MM()).store("u", "a", session_id="s9")
    assert [i["message"] for i in m.history(20, session_id="s9")] == ["u", "a"]
    assert m.history(20, session_id="other") == []


# ==========================================================
# 4. RELEVANT CONTEXT SELECTION REACHES THE PROMPT BUILDER
# ==========================================================

def test_context_builder_accepts_and_forwards_session_id(monkeypatch):
    seen = {}

    class _Fusion:
        def build(self, query, session_id=None):
            seen["query"] = query
            seen["session_id"] = session_id
            return {"conversation": {"user_messages": [], "assistant_messages": []}}

    b = ContextBuilder()
    monkeypatch.setattr(b, "fusion", _Fusion())
    b.build("hello", task="chat", session_id="sess-42")
    assert seen["session_id"] == "sess-42"


def test_memory_fusion_reads_history_for_the_session(monkeypatch):
    import core.memory.memory_fusion as mf

    class _MM:
        def get_history(self, limit=20, session_id=None):
            return [{"type": "user", "message": "prev-q"},
                    {"type": "assistant", "message": "prev-a"}]

    fusion = MemoryFusion()
    monkeypatch.setattr(fusion, "memory", _MM())
    conv = fusion.build("q", session_id="s1")["conversation"]
    assert conv["user_messages"] == ["prev-q"]
    assert conv["assistant_messages"] == ["prev-a"]


# ==========================================================
# 5. THE BLANKING IS GONE AND THE SESSION IS THREADED
# ==========================================================

def test_chat_path_no_longer_blanks_the_conversation():
    src = _source(CHAT_PATH)
    # the old blanking assignment must not exist anywhere
    assert '"user_messages": []' not in src
    assert "'user_messages': []" not in src


def test_chat_path_threads_session_id_into_context_and_writeback():
    src = _source(CHAT_PATH)
    assert "session_id=session_id" in src
    assert src.count("session_id=session_id") >= 2


def test_chat_path_still_isolates_design_state():
    """Design/render project state must STILL be cleared from a chat turn."""
    src = _source(CHAT_PATH)
    assert '"active_projects": []' in src


# ==========================================================
# 6. PROFILE FACTS MUST NOT HIJACK THE ACTIVE TOPIC
# ==========================================================

def test_naturalness_block_ranks_the_active_conversation_first():
    block = conversation_naturalness_instruction(
        MYSTERY, classify_conversation_intent(MYSTERY)["signals"])
    assert "BACKGROUND ONLY" in block
    assert "define the topic" in block


def test_profile_priority_rule_is_general_not_utterance_specific():
    src = _source(NATURALNESS_PATH)
    for fragment in ACCEPTANCE_FRAGMENTS:
        assert fragment not in src, "production names %r" % fragment


# ==========================================================
# 7-9. INTENT / REGISTER BOUNDARIES STAY CORRECT
# ==========================================================

@pytest.mark.parametrize("text,intent", [
    (READING, "GENERAL_CONVERSATION"),
    (MYSTERY, "GENERAL_CONVERSATION"),
    (MYSTERY_2, "GENERAL_CONVERSATION"),
    ("چرا آسمان آبی است؟", "GENERAL_CONVERSATION"),
    ("در طراحی یک فضای مسکونی چه نکاتی مهم هستند؟", "ARCHITECTURE_CONVERSATION"),
    ("می‌خواهم یک نکته معماری به تو آموزش بدهم", "TEACHING"),
])
def test_intent_boundary_unchanged(text, intent):
    assert classify_conversation_intent(text)["intent"] == intent


def test_general_turns_stay_out_of_the_greeting_register():
    for text in (READING, MYSTERY, MYSTERY_2):
        assert resolve_turn_register(
            text, classify_conversation_intent(text)["signals"]) == "detail_request"


# ==========================================================
# 10-11. CHAT-01 REGRESSIONS
# ==========================================================

def test_self_introduction_still_gets_identity_context():
    text = "سلام، خودت رو معرفی کن و بگو چه کارهایی می‌تونی انجام بدی"
    block = conversation_naturalness_instruction(
        text, classify_conversation_intent(text)["signals"])
    assert "IDENTITY AND CAPABILITY CONTEXT" in block


def test_general_turns_do_not_get_identity_context():
    for text in (READING, MYSTERY, "چرا آسمان آبی است؟"):
        block = conversation_naturalness_instruction(
            text, classify_conversation_intent(text)["signals"])
        assert "IDENTITY AND CAPABILITY CONTEXT" not in block


def test_pure_greeting_still_brief():
    assert resolve_turn_register("سلام", classify_conversation_intent("سلام")["signals"]) == "greeting"
    assert "ONE short natural sentence" in conversation_naturalness_instruction(
        "سلام", classify_conversation_intent("سلام")["signals"])


# ==========================================================
# 12-13. TEACHING ISOLATION / NO PROMOTION
# ==========================================================

def test_teaching_signal_unchanged():
    d = classify_conversation_intent("می‌خواهم یک نکته معماری به تو آموزش بدهم")
    assert d["intent"] == "TEACHING"
    assert "self_introduction" not in d["signals"]


def test_memory_layer_has_no_promotion_surface():
    """The change only stores/tags turns; it must add no learning step."""
    for path in MEMORY_FILES:
        src = _source(path).lower()
        assert "promote" not in src


# ==========================================================
# 14-17. MODEL ROUTING / GATEWAY CONTRACT UNCHANGED
# ==========================================================

def test_chat_model_default_unchanged(monkeypatch):
    monkeypatch.delenv("ARCHITECTOS_CHAT_MODEL", raising=False)
    assert DEFAULT_CHAT_MODEL == "gemma4:12b"
    assert ChatConfig.from_env().model == "gemma4:12b"


def test_llm_request_still_sends_think_false(monkeypatch):
    monkeypatch.delenv("ARCHITECTOS_CHAT_THINK", raising=False)
    g = LLMGateway()
    s = FakeSession(FakeResponse({"response": "ok"}))
    g.session = s
    g.generate("hi")
    assert s.calls[0]["json"]["think"] is False


def test_thinking_is_never_returned():
    g = LLMGateway()
    g.session = FakeSession(FakeResponse({"response": "پاسخ", "thinking": "راز"}))
    out = g.generate("hi")
    assert out == "پاسخ" and "راز" not in out


def test_no_silent_degraded_on_missing_model(monkeypatch):
    monkeypatch.setenv("ARCHITECTOS_CHAT_MODEL", "definitely-not-installed:99b")
    g = LLMGateway()
    g.session = FakeSession(FakeResponse({"error": "x"}, status=404))
    assert g.generate("hi") is None
    assert g.last_error.startswith("model_not_installed:")


# ==========================================================
# 18. NO ACCEPTANCE SENTENCE IS SPECIAL-CASED
# ==========================================================

@pytest.mark.parametrize("path", (CHAT_PATH, NATURALNESS_PATH) + MEMORY_FILES)
@pytest.mark.parametrize("fragment", ACCEPTANCE_FRAGMENTS)
def test_production_never_names_an_acceptance_sentence(path, fragment):
    assert fragment not in _source(path), "%s special-cases %r" % (path, fragment)


# ==========================================================
# MODEL-DEPENDENT ACCEPTANCE (opt-in)
# ==========================================================

LIVE = os.environ.get("ARCHITECTOS_LIVE_CHAT_TESTS") == "1"


@pytest.mark.skipif(not LIVE, reason="set ARCHITECTOS_LIVE_CHAT_TESTS=1 with the stack running")
class TestLiveConversationAcceptance:

    ARCH = ("معماری", "معمار", "ساختمان", "سازه", "طراحی معماری")

    @staticmethod
    def _post(text, session):
        import requests
        s = requests.Session()
        s.trust_env = False
        r = s.post("http://127.0.0.1:5000/api/chat",
                   json={"text": text, "session_id": session},
                   timeout=400)
        d = r.json()
        resp = d.get("response") if isinstance(d.get("response"), dict) else {}
        return resp.get("result") or resp.get("message") or ""

    def test_two_turn_continuity_is_not_architectural(self):
        a = self._post(READING, "live_continuity")
        b = self._post(MYSTERY, "live_continuity")
        assert a.strip() and b.strip()
        assert not any(w in b for w in self.ARCH), b
        assert any(k in b for k in ("قبلی", "قبل", "بحث", "صحبت", "گفت")), b

    def test_explicit_topic_change_still_reaches_architecture(self):
        self._post(READING, "live_switch")
        self._post(MYSTERY, "live_switch")
        d = self._post("حالا می‌خوام درباره طراحی معماری صحبت کنیم.", "live_switch")
        assert any(w in d for w in self.ARCH), d
