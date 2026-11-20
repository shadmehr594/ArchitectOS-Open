"""CONVERSATION_CONTINUITY_V3 — ordered dialogue contract.

Guards the three defects measured in ARCHITECTOS_LIVE_PRODUCT_SMOKE_ACCEPTANCE_V2:

  1. the write boundary stored `str(response)` envelopes instead of the
     assistant's actual message text;
  2. retrieval exposed `user_messages` / `assistant_messages` as two parallel
     lists, so turn order and role alternation were lost;
  3. the prompt embedded the whole memory dict, so the dialogue reached the
     model without chronology and a follow-up ("now make it iterative") had
     no antecedent.

Run:
  ./.venv/Scripts/python.exe -m pytest tests/test_conversation_continuity_v3.py -q \
      --basetemp=runs/_pytest_tmp_ccv3
"""

import uuid

import pytest

from core.memory.memory_manager import memory_manager
from core.memory.conversation_writeback import create_writeback
from core.memory.context_builder import ContextBuilder
from core.memory.conversation_intelligence import ConversationIntelligence
from core.prompt_engine import PromptEngine


ENVELOPE = {
    "type": "chat",
    "engine": "llm_gateway",
    "result": "def fibonacci(n):\n    return n if n < 2 else fibonacci(n - 1) + fibonacci(n - 2)",
    "status": "success",
    "language": {"input_language": "english", "output_language": "english"},
    "render_handoff": {"contract": "RenderHandoffTraceV1", "isolated_session": True},
}


def _session():
    return "ccv3_" + uuid.uuid4().hex[:12]


def _write(session_id, user, assistant):
    return create_writeback(memory_manager).store(user, assistant, session_id=session_id)


# ----------------------------------------------------------
# 1. STORAGE — plain text, not envelopes
# ----------------------------------------------------------

def test_assistant_turn_is_stored_as_message_text_not_an_envelope():
    """`str(response)` must be reduced to what the assistant actually said."""
    sid = _session()
    _write(sid, "Write a recursive Fibonacci function.", str(ENVELOPE))

    rows = memory_manager.get_history(20, session_id=sid)
    assistant = [r for r in rows if r["type"] == "assistant"]

    assert len(assistant) == 1
    stored = assistant[0]["message"]

    assert stored.startswith("def fibonacci(n):")
    # none of the envelope scaffolding may survive
    assert "render_handoff" not in stored
    assert "llm_gateway" not in stored
    assert not stored.startswith("{'")


def test_assistant_turn_accepts_a_dict_envelope_too():
    sid = _session()
    _write(sid, "hi", ENVELOPE)

    rows = memory_manager.get_history(20, session_id=sid)
    assistant = [r for r in rows if r["type"] == "assistant"][0]

    assert assistant["message"].startswith("def fibonacci(n):")
    assert "llm_gateway" not in assistant["message"]


# ----------------------------------------------------------
# 2. RETRIEVAL — chronological order
# ----------------------------------------------------------

def test_turns_preserve_chronological_user_assistant_order():
    sid = _session()
    _write(sid, "first question", "first answer")
    _write(sid, "second question", "second answer")

    ctx = ContextBuilder().build("third question", task="chat", session_id=sid)
    turns = ctx["memory"]["conversation"]["turns"]

    assert [t["role"] for t in turns] == [
        "user", "assistant", "user", "assistant",
    ]
    assert [t["text"] for t in turns] == [
        "first question", "first answer",
        "second question", "second answer",
    ]


def test_legacy_parallel_lists_are_still_populated():
    """Existing consumers keep working; the ordered view is additive."""
    sid = _session()
    _write(sid, "q1", "a1")

    ctx = ContextBuilder().build("q2", task="chat", session_id=sid)
    conv = ctx["memory"]["conversation"]

    assert conv["user_messages"] == ["q1"]
    assert conv["assistant_messages"] == ["a1"]
    assert conv["turns"]


def test_persian_follow_up_keeps_order_and_text():
    sid = _session()
    _write(
        sid,
        "یک تابع پایتون برای فیبوناچی بازگشتی بنویس.",
        "def fibonacci(n): ...  # بازگشتی",
    )

    ctx = ContextBuilder().build(
        "حالا همان را تکرارشونده کن.", task="chat", session_id=sid
    )
    turns = ctx["memory"]["conversation"]["turns"]

    assert turns[0]["role"] == "user"
    assert "فیبوناچی" in turns[0]["text"]
    assert turns[1]["role"] == "assistant"
    assert "بازگشتی" in turns[1]["text"]


# ----------------------------------------------------------
# 3. PRESENTATION — transcript in the prompt
# ----------------------------------------------------------

def test_prompt_renders_an_ordered_transcript_before_the_user_message():
    sid = _session()
    _write(sid, "Write a recursive Fibonacci function.", str(ENVELOPE))

    ctx = ContextBuilder().build(
        "Now make it iterative instead of recursive.", task="chat", session_id=sid
    )
    prompt = PromptEngine().build("Now make it iterative instead of recursive.", ctx)

    assert "CONVERSATION SO FAR" in prompt
    assert "User: Write a recursive Fibonacci function." in prompt
    assert "Assistant: def fibonacci(n):" in prompt

    # the transcript must precede the current message, so the referent is
    # the nearest preceding turn
    assert prompt.index("CONVERSATION SO FAR") < prompt.index(
        "USER MESSAGE:\n\nNow make it iterative"
    )
    # and the current message must be the LAST dialogue turn
    assert prompt.index("Assistant: def fibonacci(n):") < prompt.index(
        "USER MESSAGE:\n\nNow make it iterative"
    )


def test_prompt_does_not_duplicate_the_conversation_as_parallel_lists():
    sid = _session()
    _write(sid, "q1", "a1")

    ctx = ContextBuilder().build("q2", task="chat", session_id=sid)
    prompt = PromptEngine().build("q2", ctx)

    assert "'user_messages'" not in prompt
    assert "'assistant_messages'" not in prompt
    assert "rendered_as" in prompt


def test_empty_history_adds_no_transcript():
    ctx = ContextBuilder().build("hello", task="chat", session_id=_session())
    prompt = PromptEngine().build("hello", ctx)

    assert "CONVERSATION SO FAR" not in prompt
    assert "USER MESSAGE:" in prompt


# ----------------------------------------------------------
# 4. BOUNDING — keep the referent, drop the oldest
# ----------------------------------------------------------

def test_transcript_is_bounded_and_keeps_the_newest_turn():
    intelligence = ConversationIntelligence()

    history = [
        {"text": "x" * 400, "type": "user" if i % 2 == 0 else "assistant"}
        for i in range(40)
    ]

    turns = intelligence._ordered_turns(history)

    assert len(turns) <= intelligence.MAX_TRANSCRIPT_TURNS
    # the newest turn survives the bound
    assert turns[-1] == {"role": "assistant", "text": "x" * 400}


def test_transcript_character_budget_drops_the_oldest_lines():
    engine = PromptEngine()

    turns = [
        {"role": "user" if i % 2 == 0 else "assistant", "text": "y" * 900}
        for i in range(12)
    ]
    context = {"memory": {"conversation": {"turns": turns}}}

    transcript = engine._conversation_transcript(context)

    assert len(transcript) <= engine.MAX_TRANSCRIPT_CHARS + 400
    # the final turn is still present
    assert transcript.rstrip().endswith("y" * 900)


def test_single_oversized_turn_is_never_trimmed_away():
    """The immediate referent must survive even if it alone exceeds the budget."""
    engine = PromptEngine()

    turns = [
        {"role": "user", "text": "z" * (engine.MAX_TRANSCRIPT_CHARS + 500)},
    ]
    transcript = engine._conversation_transcript(
        {"memory": {"conversation": {"turns": turns}}}
    )

    assert "z" * (engine.MAX_TRANSCRIPT_CHARS + 500) in transcript


# ----------------------------------------------------------
# 5. NON-REGRESSION — other context keys survive
# ----------------------------------------------------------

def test_architectural_context_keys_survive_the_trimmed_context_block():
    engine = PromptEngine()

    context = {
        "task": "chat",
        "conversation_state": {"mode": "chat", "last_render_asset": {"id": "x"}},
        "conversation_domain": {"domain": "architecture"},
        "memory": {"conversation": {"turns": [{"role": "user", "text": "a"}]}},
    }

    block = engine._context_block(context)

    assert "conversation_state" in block
    assert "conversation_domain" in block
    # the dialogue itself is not re-dumped
    assert "'role': 'user'" not in block
