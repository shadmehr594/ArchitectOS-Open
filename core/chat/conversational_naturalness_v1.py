# -*- coding: utf-8 -*-
"""CONVERSATIONAL_NATURALNESS_V1 — human conversation tone for chat replies.

PROBLEM THIS FIXES
------------------
Two defects made ArchitectOS *talk* unnaturally:

1. STICKY ARCHITECTURAL DOMAIN
   `architectural_conversation_context_v1.merge()` stores
   `turn_has_architectural_signal` for the CURRENT turn, but the session
   carries architectural state forward. The conversation-domain classifier
   (`conversation_domain_v1.classify_domain`) treats a `True` signal as a
   TOP-PRIORITY override, so once ONE architectural turn has happened, EVERY
   later turn in the session is forced into the `architecture` domain and the
   full architectural payload is injected — even `"سلام خوبی؟"` or
   `"بیا راجع به آشپزی صحبت کنیم"`. The LLM then answers every turn with
   generic architectural knowledge.

2. NO NATURAL-CONVERSATION INSTRUCTION
   The system prompt (`core/prompt_engine.py`) contained an
   `ARCHITECTURE / DESIGN MODE` block instructing "structured professional
   output" and injected the whole architectural context dict, with NO rule
   distinguishing *"let's talk about architecture"* (conversation) from
   *"design me a house"* (a request). It also had no rule against lectures,
   repetition, canned formal Persian, mixed-language fragments, or forced
   follow-up questions.

WHAT THIS MODULE DOES (ADDITIVE — it changes no routing)
--------------------------------------------------------
* `reclassify_turn_domain()` — recomputes the domain for the CURRENT turn
  from THIS turn's own text/understanding, so a stale carried-forward signal
  cannot force an unrelated turn into architecture. It calls the SAME frozen
  `classify_domain()`; it only supplies the *current turn's* signal instead
  of the session's stale one. Architecture turns still resolve to
  `architecture` and still receive the full architectural context.

* `conversation_naturalness_instruction()` — returns the natural-conversation
  rules that belong in the chat prompt, plus a per-turn "conversational
  register" hint (short greeting / casual chat / topic conversation /
  detailed question) so the reply matches the turn.

WHAT IT DOES NOT DO
-------------------
No new assistant, no new LLM, no new memory, no new conversation store.
It generates no design, never renders, never calls ComfyUI, never touches
STT/TTS/voice/vision. It does NOT change Teaching/Architecture/General
routing boundaries — it only stops a stale signal from mislabelling the
CURRENT turn (which the brief records as a KNOWN issue for the NEXT phase).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from core.chat.architectos_capability_context_v1 import (
    self_introduction_context,
)

from core.chat.negation_scope_v1 import rejected_span


CONTRACT = "ConversationalNaturalnessV1"
VERSION = "1.0"

print("🗣️ CONVERSATIONAL NATURALNESS v1.0 ONLINE (tone only, no routing)")


# ==========================================================
# 1. TURN-LEVEL DOMAIN RECOMPUTATION (anti-stale-signal)
# ==========================================================

def _has_own_architectural_signal(understanding: Any) -> bool:
    """Does THIS turn's own parsed understanding carry an architectural
    signal? Mirrors `architectural_conversation_context_v1._has_architectural_signal`
    (frozen) — re-implemented here so we can decide the CURRENT turn without
    importing the sticky session flag.
    """

    if not isinstance(understanding, dict) or not understanding:
        return False

    if (understanding.get("style") or {}).get("target"):
        return True

    if (understanding.get("materials") or {}).get("primary"):
        return True

    if understanding.get("negative_constraints"):
        return True

    if (understanding.get("reference_image_policy") or {}).get("referenced"):
        return True

    for op in understanding.get("change_operations", []) or []:
        if op.get("operation") != "preserve":
            return True

    preserve = understanding.get("preserve_constraints") or {}
    for key, value in preserve.items():
        if key not in ("explicit", "scope_unspecified") and value is True:
            return True

    return False


def reclassify_turn_domain(
    text: Any,
    architectural_context: Any = None,
    *,
    understanding: Any = None,
    context: Any = None,
) -> Dict[str, Any]:
    """Classify the CURRENT turn using THIS turn's signal.

    The frozen `resolve_turn_domain()` reads `turn_has_architectural_signal`
    from the SESSION context, which is carried forward and therefore stale for
    a non-architectural follow-up. Here the signal is recomputed for the
    current turn only.

    Returns the SAME shape as `resolve_turn_domain()` so the caller is a
    drop-in swap.
    """

    from core.chat.conversation_domain_v1 import (
        classify_domain,
        project_context_for_domain,
        domain_guidance,
        CONTRACT as _DOMAIN_CONTRACT,
        VERSION as _DOMAIN_VERSION,
    )

    # the CURRENT turn's signal — not the session's carried-forward one
    current_signal = _has_own_architectural_signal(understanding)

    # IMPORTANT: `understanding` must NOT be passed straight through.
    # `classify_domain` treats ANY non-empty understanding as a strong
    # architectural signal (`bool(understanding)`), and the Persian
    # understanding interpreter ALWAYS returns a full contract dict (with
    # `contract` / `version` / `intensity` keys) even for `"سلام خوبی؟"`.
    # Passing it through would therefore re-introduce the exact bug: every
    # turn classified as architecture. We pass an EMPTY dict and express the
    # turn's real signal through `architectural_signal` only.
    domain = classify_domain(
        text,
        understanding=({} if not current_signal else understanding),
        architectural_signal=(True if current_signal else None),
        context=context,
    )

    safe_context = project_context_for_domain(
        architectural_context,
        domain["domain"],
        architectural_signal=(True if current_signal else None),
    )

    return {
        "domain": domain,
        "architectural_context": safe_context,
        "domain_block": {
            "contract": _DOMAIN_CONTRACT,
            "version": _DOMAIN_VERSION,
            "domain": domain["domain"],
            "guidance": domain_guidance(domain["domain"]),
            "architectural_context_injected": (
                domain["domain"] == "architecture" or current_signal
            ),
            "architectural_context_suspended": bool(
                isinstance(safe_context, dict) and safe_context.get("suspended")
            ),
            # additive provenance for the audit trail
            "naturalness_contract": CONTRACT,
            "naturalness_version": VERSION,
            "signal_source": "current_turn",
        },
    }


# ==========================================================
# 2. TURN REGISTER (how the reply should be shaped)
# ==========================================================

# a greeting / well-being check — a SHORT turn
_GREETING = (
    "سلام", "درود", "خوبی", "چطوری", "چه خبر", "صبح بخیر", "شب بخیر",
    "hello", "hi ", "hey", "how are you", "good morning", "good evening",
)

# an explicit invitation to converse, not a request for facts
_CONVERSE_INVITE = (
    "حرف بزنیم", "صحبت کنیم", "گپ", "درد دل", "باهم حرف", "با هم حرف",
    "let's chat", "lets chat", "let us chat", "chat for a bit", "have a chat",
    "just talk", "talk for a bit",
)

# a topic being raised WITHOUT a question word (conversation about a topic)
_TOPIC_ABOUT = (
    "راجع به", "راجب", "درباره", "در مورد",
    "about", "regarding", "on the topic of",
)

# an actual request for explanation / detail
_DETAIL_REQUEST = (
    "چرا", "چطور", "چگونه", "توضیح بده", "توضیح بدهید", "شرح بده",
    "explain", "why", "how does", "how do", "in detail", "elaborate",
    "tell me more about",
)

# a genuine question (needs an answer, not small talk)
_QUESTION_MARK = re.compile(r"[?\u061f]")

# ==========================================================
# STRUCTURED REQUEST SIGNALS — reused, never re-derived here
# ==========================================================

# The CURRENT turn's structured signals are owned by the Conversation Intent
# Boundary (`conversation_intent_boundary_v1`). This module does NOT classify
# intent; it only honours the decision that has already been made.
#
# A signal listed here means "the user is explicitly asking the assistant for
# information", so the turn is an information request even when it opens with
# a greeting word — a greeting is a SHORT social turn, never a wrapper around
# a real request.
#
# This is a CONTRACT, not a keyword list: it names intent signals, never user
# utterances. Extend it only with a signal the boundary actually emits.
_REQUEST_SIGNALS = (
    "self_introduction",
)


def _is_information_request(signals: Any) -> bool:
    """True when the CURRENT turn carries a structured request signal."""

    if not signals:
        return False

    try:
        return any(signal in _REQUEST_SIGNALS for signal in signals)

    except TypeError:
        return False


# ==========================================================
# EXPLICIT INFORMATION / LIST REQUESTS
#
# An explicit request for information or for a LIST is not small talk. It
# used to fall through to `casual_chat`, whose rule is "Do NOT list facts,
# Do NOT produce a structured answer" — the exact opposite of what was asked.
#
# These are REQUEST VERBS and QUANTITY words (a grammatical category), never
# topics, so nothing here names a subject. A request is recognised EITHER by
# a strong list/enumeration marker OR by the two-part form
# (a request verb AND an information object), which is what keeps a stray
# verb from over-capturing a greeting.
# ==========================================================

_LIST_REQUEST = (
    "لیست کن", "لیست بده", "لیستش کن", "لیست کن برام", "لیست کن برا",
    "فهرست کن", "فهرست بده", "فهرستش",
    "انتخاب کن", "انتخاب کنید", "انتخاب کن برام",
    "پیشنهاد بده", "پیشنهاد بدید", "پیشنهاد کن", "پیشنهاد بدی",
    "نام ببر", "نام ببرید", "اسم بده", "اسمش رو بگو", "اسم‌ها رو",
    "بنویس", "بنویس برام", "بشمار", "بشمار برام",
    "چند تا", "چندتا", "چنتا", "چندین", "چند مورد", "چند نمونه",
    "اطلاعات بده", "اطلاعات بدید", "بیان کن",
    "list them", "make a list", "list of", "enumerate", "recommend",
    "suggest", "give me", "tell me", "which ones", "how many", "what are",
)

# Part A — a request verb. Part B — the information object it asks for.
#
# A bare "معرفی کن" / "بگو" is deliberately NOT a strong marker: "خودت را
# معرفی کن" is a self-introduction, not a list. Those verbs only count
# together with an information object, which keeps the CHAT-01 invariant
# (the same sentence flips register only when its SIGNAL is present).
_REQUEST_VERBS = (
    "بده", "بدید", "بگو", "بگید", "بنویس", "بشمار", "لیست", "فهرست",
    "انتخاب", "معرفی", "پیشنهاد", "select", "list", "give", "name", "show",
)

_INFORMATION_OBJECTS = (
    "اسم", "نام", "لیست", "فهرست", "مثال", "نمونه", "مورد", "چند",
    "عنوان", "توضیح", "اطلاعات",
    "name", "title", "list", "example", "examples", "item", "items",
    "option", "options", "how many",
)


def _is_explicit_information_request(text: str) -> bool:
    """True when the user EXPLICITLY asks for information or for a list.

    A strong list marker is enough on its own. Otherwise the request must
    have BOTH a request verb and an information object, so an ordinary
    sentence that merely contains a verb is not re-classified.
    """

    if _any(text, _LIST_REQUEST):
        return True

    return _any(text, _REQUEST_VERBS) and _any(text, _INFORMATION_OBJECTS)


# An EXPLICIT design / render request is a request too. `casual_chat` forbids
# the structured answer such a turn needs, and it would contradict the render
# instruction compiled for the same turn.
_DESIGN_REQUEST = (
    "بساز", "بسازید", "طراحی کن", "طراحی کنید", "رندر کن", "رندر بگیر",
    "رندر بگیرید", "ایجاد کن", "درست کن", "بکش", "بکشید",
    "build", "create a", "design a", "design me", "render", "generate a",
)


def _is_explicit_design_request(text: str) -> bool:

    return _any(text, _DESIGN_REQUEST)


def _is_self_introduction(signals: Any) -> bool:
    """True when the CURRENT turn asks who the assistant is / what it can do.

    The identity/capability context is added ONLY for this signal, so no other
    turn ever receives architectural capability text.
    """

    if not signals:
        return False

    try:
        return "self_introduction" in signals

    except TypeError:
        return False


def _is_correction(signals: Any) -> bool:
    """True when the CURRENT turn corrects / repairs the exchange.

    GENERAL_CONVERSATION_CORRECTION_V1 — a correction asks for a corrected
    ANSWER, so it must never be shaped as small talk. Without this the short
    correction "معمایی گفتم نه معماری" fell into the `casual_chat` register,
    whose rule is "Do NOT list facts, do NOT produce a structured answer" —
    the opposite of what re-answering the original request needs.
    """

    if not signals:
        return False

    try:
        return "conversation_repair" in signals

    except TypeError:
        return False


def _norm(value: Any) -> str:
    if value is None:
        return ""
    s = " ".join(str(value).split()).lower()
    return s.replace("\u200c", " ").replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")


def _any(text: str, markers) -> bool:
    low = _norm(text)
    return any(_norm(m) in low for m in markers)


def resolve_turn_register(text: Any, signals: Any = None) -> str:
    """One of: greeting | casual_chat | topic_conversation | detail_request.

    Deterministic, order-sensitive (most specific first):
      detail_request    -> the user actually wants information / depth
      greeting          -> a short hello / well-being turn
      topic_conversation-> the user raised a topic to talk about
      casual_chat       -> generic small talk

    `signals` is the CURRENT turn's structured signal list from the
    Conversation Intent Boundary (optional; the default `None` preserves the
    previous text-only behaviour exactly). When the user is explicitly asking
    about the assistant itself, that structured request outranks a surface
    greeting word — otherwise a greeting that merely OPENS a real request
    would be answered as if the user had said nothing but the greeting.
    """

    raw = " ".join(str(text or "").split())

    if not raw:
        return "casual_chat"

    # A correction asks for a corrected ANSWER, so it is never small talk and
    # never a bare greeting, whatever else the surface text looks like.
    if _is_correction(signals):
        return "detail_request"

    # An EXPLICIT request for information or for a list is never small talk:
    # the `casual_chat` rule forbids exactly the list the user just asked for.
    if _is_explicit_information_request(raw):
        return "detail_request"

    # The same holds for an explicit design / render request.
    if _is_explicit_design_request(raw):
        return "detail_request"

    # A structured request signal is decided BEFORE the greeting check: an
    # explicit request about the assistant is not a well-being check, however
    # it opens. Text alone cannot make this distinction safely, which is
    # exactly why the already-computed boundary signal is reused here.
    if _is_information_request(signals):
        return "detail_request"

    # A greeting is decided BEFORE the question-mark check: `"سلام خوبی؟"`
    # is a well-being check, not a request for explanation.
    if _any(raw, _GREETING) and len(raw) < 24:
        return "greeting"

    if _any(raw, _DETAIL_REQUEST) or _QUESTION_MARK.search(raw):
        return "detail_request"

    if _any(raw, _CONVERSE_INVITE) or _any(raw, _TOPIC_ABOUT):
        return "topic_conversation"

    if _any(raw, _GREETING):
        return "greeting"

    return "casual_chat"


_REGISTER_RULES = {
    "greeting": (
        "This turn is a greeting / well-being check. Reply in ONE short "
        "natural sentence and, only if it fits, ONE short friendly question "
        "back. Do NOT explain anything. Do NOT list facts. Do NOT mention "
        "architecture unless the user did."
    ),
    "casual_chat": (
        "This turn is small talk. Reply briefly and naturally, like a normal "
        "conversation partner. Do NOT lecture, do NOT list facts, do NOT "
        "produce a structured answer, and do NOT end with a question unless "
        "it genuinely helps the conversation."
    ),
    "topic_conversation": (
        "The user raised a TOPIC to talk about, not a request for a report. "
        "Acknowledge it conversationally in one or two sentences and let the "
        "user lead. Do NOT dump general knowledge about the topic. Do NOT "
        "list definitions, categories or rules. Ask what part they want to "
        "focus on ONLY if that is natural — never as a forced template."
    ),
    "detail_request": (
        "The user is asking for explanation or detail. Give a clear, useful, "
        "well-structured answer at the depth requested, and stay on the "
        "user's actual question instead of a generic overview."
    ),
}


def correction_context(text: Any, signals: Any = None) -> str:
    """The directive injected when the user is CORRECTING the exchange.

    GENERAL_CONVERSATION_CORRECTION_V1 — a correction states what the user
    does NOT want, so the model must not reaffirm it. The rejected term is
    extracted from the user's own wording (everything after their negation
    word), never from a fixed vocabulary, so nothing is special-cased here.

    Returns "" for every turn that is not a correction.
    """

    if not signals:

        return ""

    try:

        is_correction = "conversation_repair" in signals

    except TypeError:

        return ""

    if not is_correction:

        return ""

    rejected = rejected_span(text)

    lines = [

        "",
        "CORRECTION — THE USER IS CORRECTING THE PREVIOUS EXCHANGE:",
        "",
        "- The user is rejecting part of what was said or assumed above. What",
        "  they reject is NOT what they want.",
    ]

    if rejected:

        lines.append(
            "- What the user does NOT want is: \u00ab" + rejected + "\u00bb."
        )

    lines.extend([

        "- Do NOT reaffirm the rejected subject, and do NOT treat your own",
        "  previous reply as evidence of what the user wants.",
        "- Find the ORIGINAL request in the conversation above and answer THAT,",
        "  with the subject the user actually asked for, keeping that request's",
        "  original requirements and output format.",
        "- Acknowledge the misunderstanding in one short sentence, then answer.",
        "  Do not ask the user to repeat a request that is already above.",
        # GENERAL_CONVERSATION_CORRECTION_V1 — measured on the live model: when
        # the correction is spurious (the previous answer was already right)
        # the model replied by only echoing the user's own sentence. A
        # correction is not automatically an error, so say what to do instead.
        "- If nothing in the previous answer was actually wrong, say so in one",
        "  short sentence and then continue with the original request. Never",
        "  reply by only repeating the user's sentence back to them.",
    ])

    return "\n".join(lines)


def conversation_naturalness_instruction(text: Any, signals: Any = None) -> str:
    """The natural-conversation block injected into the chat prompt.

    It is language-neutral (the language lock is owned by the prompt engine)
    and register-aware for the CURRENT turn. `signals` is the CURRENT turn's
    structured signal list from the Conversation Intent Boundary (optional;
    omitted => previous behaviour).
    """

    register = resolve_turn_register(text, signals)

    # SELF-DESCRIPTION FIX — the verified identity/capability context is
    # appended ONLY when the CURRENT turn actually asks who the assistant is.
    # Every other turn keeps the byte-identical block it had before, so no
    # architectural capability text can leak into an unrelated conversation.
    identity_context = ""

    if _is_self_introduction(signals):

        identity_context = self_introduction_context()

    # GENERAL_CONVERSATION_CORRECTION_V1 — when the user is correcting the
    # exchange, say so explicitly and name what they rejected. Empty for
    # every other turn.
    correction = correction_context(text, signals)

    return f"""

CONVERSATION STYLE (IMPORTANT — READ BEFORE ANSWERING):

- Answer the user's actual message directly. Do not answer a different,
  larger question than the one that was asked.
- If the user is just talking (greeting, small talk, raising a topic), respond
  conversationally. Do NOT turn the turn into a lecture.
- Never dump general knowledge on a subject unless the user actually asks a
  question about it.
- Do not repeat the same sentence, the same idea or the same opening twice.
- Do not use canned, overly formal or translated-sounding phrasing. If the
  user writes casually, reply naturally in the same register.
- Do not mix languages. Never drop random English words into a Persian reply
  (or Persian words into an English reply).
- Do not over-explain a simple turn. Keep short turns short; give a longer,
  detailed answer only when the user asks for detail.
- Do not end every reply with a question. Ask a follow-up only when it is
  genuinely useful. Do not use a fixed conversational template.
- Do not invent friendliness or filler.
- The user's CURRENT message and the recent turns of THIS conversation are
  what define the topic. Stored profile facts (interests, preferences,
  family, projects) are BACKGROUND ONLY: never use one to introduce a
  subject, change the subject, or reinterpret what the user asked. If a
  stored interest is not what the user is talking about right now, leave it
  out — do not mention it, and do not draw an analogy from it.

CURRENT TURN:
{_REGISTER_RULES.get(register, _REGISTER_RULES["casual_chat"])}
{identity_context}
{correction}
"""


# ==========================================================
# THE CLASS (house style)
# ==========================================================

class ConversationalNaturalnessV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    CREATES_SECOND_ASSISTANT = False
    CHANGES_ROUTING = False
    MUTATES_SESSION_CONTEXT = False
    RENDERS = False
    USES_VISION = False
    TOUCHES_STT = False
    TOUCHES_TTS = False

    def reclassify(self, text, architectural_context=None, **kwargs):
        return reclassify_turn_domain(
            text, architectural_context, **kwargs
        )

    def register(self, text, signals=None):
        return resolve_turn_register(text, signals)

    def instruction(self, text, signals=None):
        return conversation_naturalness_instruction(text, signals)


conversational_naturalness = ConversationalNaturalnessV1()
