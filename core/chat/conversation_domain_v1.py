# -*- coding: utf-8 -*-
"""CONVERSATION_DOMAIN_V1 — chat / voice domain isolation.

PROBLEM THIS FIXES
------------------
The session's architectural context (active materials, elements, scope,
targets, recent turns) was merged across turns for design continuity — and
then injected into the general chat prompt **unconditionally**. A question
about audio ("صدا میاد؟") was therefore answered with the previous
architectural topic, because the prompt still carried "brick / facade /
windows / bedroom".

WHAT THIS MODULE DOES
---------------------
1. Classifies the turn into a DOMAIN:
       architecture | voice_audio | general
2. Projects the session architectural context into a form that is SAFE to
   inject for that domain.

THE SUSPENSION RULE (important)
-------------------------------
The architectural context is **SUSPENDED, never deleted**:

  * it stays in the session store untouched (design continuity survives),
  * a non-architectural turn simply does NOT inject its payload,
  * when the user returns to architecture, the very next architectural turn
    injects it again in full.

This module is read-only over the context: it never mutates the session.

NOT IN SCOPE
------------
No vision, no knowledge, no teaching, no interpretation, no UI, no render.
This module makes no design decision and generates nothing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.chat.negation_scope_v1 import is_affirmed


CONTRACT = "ConversationDomainV1"
VERSION = "1.0"

DOMAINS = ("architecture", "voice_audio", "general")


# ==========================================================
# DOMAIN MARKERS (closed tables — they only RECOGNISE words)
# ==========================================================

# --- voice / audio / STT / TTS ---
VOICE_AUDIO_MARKERS: Tuple[str, ...] = (
    # Persian
    "صدا", "صوت", "صدای", "صداها", "میکروفن", "میکروفون", "میکروفن", "میکروفنى",
    "بلندگو", "اسپیکر", "ضبط", "رکورد", "ضبط می‌کن", "ضبط میکن",
    "می‌شنوی", "میشنوی", "می‌شنوید", "میشنوید", "شنیدن", "شنیدم", "شنوایی",
    "شنیده می‌شود", "شنیده میشود", "قطع است", "قطع شد", "وصل است", "وصل شد",
    "ولوم", "نویز", "پژواک", "اکو", "تلفظ", "گفتار", "صحبت من",
    "صدای من", "صدایم", "چیزی نمی‌شنوم", "چیزی نمیشنوم", "نمیشنوم",
    # English
    "voice", "audio", "sound", "microphone", "mic", "hear me", "can you hear",
    "listen", "listening", "recording", "recorded", "tts", "stt", "speaker",
    "volume", "noise", "echo", "transcri",
)

# --- architecture / design ---
ARCHITECTURE_MARKERS: Tuple[str, ...] = (
    # Persian
    "خانه", "خونه", "ساختمان", "ویلا", "آپارتمان", "مجتمع", "برج",
    "اتاق", "اتاق خواب", "پذیرایی", "نشیمن", "آشپزخانه", "حمام", "سرویس",
    "پلان", "نقشه", "طبقه", "همکف", "زیرزمین", "پارکینگ", "بالکن", "تراس",
    "نما", "نمای", "دیوار", "پنجره", "در ورودی", "ورودی", "راه پله", "راهپله",
    "متراژ", "متر مربع", "مساحت", "ابعاد", "شمالی", "جنوبی",
    "طراحی", "معمار", "معماری", "پروژه", "سازه", "مصالح", "متریال",
    "کلوزت", "کمد", "نورگیر", "حیاط", "استخر",
    # English
    "house", "home", "building", "villa", "apartment", "residence",
    "room", "bedroom", "living room", "kitchen", "bathroom", "floor",
    "plan", "blueprint", "facade", "wall", "window", "door", "parking",
    "balcony", "terrace", "stair", "design", "architect", "architecture",
    "project", "structure", "material", "closet", "wardrobe",
)

# a meta-question about the ASSISTANT itself is general, not architecture
_GENERAL_META_MARKERS = (
    "کی هستی", "تو کی هستی", "اسمت", "نامت", "چیکار می‌کنی", "چیکار میکنی",
    "who are you", "your name", "what can you do",
)


def _text(value: Any) -> str:

    if value is None:

        return ""

    if isinstance(value, str):

        return " ".join(value.split())

    return " ".join(str(value).split())


def _norm(value: Any) -> str:

    s = _text(value).lower()

    return (
        s.replace("\u200c", " ")
        .replace("\u064a", "\u06cc")
        .replace("\u0643", "\u06a9")
    )


def _hits(text: str, markers: Tuple[str, ...]) -> List[str]:

    low = _norm(text)

    found: List[str] = []

    for marker in markers:

        if _norm(marker) in low and marker not in found:

            found.append(marker)

    return found


# ==========================================================
# 1. DOMAIN CLASSIFICATION
# ==========================================================

def classify_domain(
    text: Any,
    *,
    understanding: Any = None,
    architectural_signal: Optional[bool] = None,
    context: Any = None,
) -> Dict[str, Any]:

    """Return {domain, evidence, confidence, reasoning_source, ...}.

    Priority:
      1. a STRONG architectural signal (a parsed architectural
         understanding, or the context store's own signal)
      2. explicit voice / audio markers
      3. architectural markers
      4. general
    """

    raw = _text(text)

    strong_architectural = bool(understanding)

    if architectural_signal is True:

        strong_architectural = True

    if strong_architectural:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "domain": "architecture",
            "evidence": ["architectural understanding/signal present"],
            "confidence": "HIGH",
            "reasoning_source": "architectural signal",
            "architectural_turn": True,
        }

    voice_hits = _hits(raw, VOICE_AUDIO_MARKERS)

    if voice_hits:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "domain": "voice_audio",
            "evidence": voice_hits[:5],
            "confidence": "HIGH",
            "reasoning_source": "explicit voice/audio markers",
            "architectural_turn": False,
        }

    # GENERAL_CONVERSATION_CORRECTION_V1 — a subject word inside a negation
    # is NOT an affirmation of that subject. Without this, a correction such
    # as "معمایی گفتم نه معماری" (mystery, NOT architecture) still matched an
    # architecture marker and the turn was routed into the architecture domain
    # — the exact inversion the correction was rejecting.
    arch_hits = [
        marker
        for marker in _hits(raw, ARCHITECTURE_MARKERS)
        if is_affirmed(_norm(raw), _norm(marker))
    ]

    if arch_hits:

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "domain": "architecture",
            "evidence": arch_hits[:5],
            "confidence": "MEDIUM",
            "reasoning_source": "architectural markers",
            "architectural_turn": True,
        }

    meta_hits = _hits(raw, _GENERAL_META_MARKERS)

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "domain": "general",
        "evidence": meta_hits[:3],
        "confidence": "MEDIUM" if meta_hits else "LOW",
        "reasoning_source": "no architectural or voice/audio signal",
        "architectural_turn": False,
    }


# ==========================================================
# 2. THE DOMAIN GUIDANCE (what the assistant should answer about)
# ==========================================================

_DOMAIN_GUIDANCE = {
    "architecture": (
        "The user's turn is about architecture/design. "
        "The session's architectural context is provided below and may be used."
    ),
    "voice_audio": (
        "The user's turn is about audio / voice / the microphone / speech "
        "recognition. Answer ONLY about audio and voice. "
        "Do NOT discuss architecture, buildings, rooms or design."
    ),
    "general": (
        "The user's turn is general conversation. Answer it directly and "
        "briefly. Do NOT discuss architecture, buildings, rooms or design "
        "unless the user asks about them."
    ),
}


def domain_guidance(domain: str) -> str:

    return _DOMAIN_GUIDANCE.get(domain, _DOMAIN_GUIDANCE["general"])


# ==========================================================
# 3. THE CONTEXT PROJECTION (suspend, never delete)
# ==========================================================

# the fields that must NEVER reach a non-architectural prompt
_ARCHITECTURAL_PAYLOAD_KEYS = (
    "active_topic",
    "active_scope",
    "active_architectural_intent",
    "active_architectural_understanding",
    "active_compiled_prompt",
    "active_preserve_constraints",
    "active_negative_constraints",
    "active_materials",
    "active_style",
    "active_reference_policy",
    "active_targets",
    "active_elements",
    "pending_ambiguities",
    "pending_clarifications",
    "active_design_id",
    "active_candidate_id",
    "active_render_id",
    "active_reference_id",
)

# the neutral value per payload key when suspended
_NEUTRAL = {
    "active_topic": None,
    "active_scope": None,
    "active_architectural_intent": {},
    "active_architectural_understanding": {},
    "active_compiled_prompt": {},
    "active_preserve_constraints": {},
    "active_negative_constraints": [],
    "active_materials": {},
    "active_style": {},
    "active_reference_policy": {},
    "active_targets": [],
    "active_elements": {},
    "pending_ambiguities": [],
    "pending_clarifications": [],
    "active_design_id": None,
    "active_candidate_id": None,
    "active_render_id": None,
    "active_reference_id": None,
}


def _is_architectural_turn(turn: Any) -> bool:

    if not isinstance(turn, dict):

        return False

    scope = turn.get("scope")

    if scope:

        return True

    return bool(_hits(turn.get("raw_text") or turn.get("normalized_text") or "",
                      ARCHITECTURE_MARKERS))


def project_context_for_domain(
    architectural_context: Any,
    domain: str,
    *,
    architectural_signal: Optional[bool] = None,
) -> Dict[str, Any]:

    """The architectural context that is SAFE to inject for `domain`.

    * architecture  -> the full context, unchanged (design continuity kept)
    * anything else -> a SUSPENDED projection: the payload is emptied, the
                       session identifiers are kept, and the session store
                       itself is untouched, so the context returns in full
                       on the next architectural turn.
    """

    context = architectural_context if isinstance(architectural_context, dict) else {}

    if domain == "architecture" or architectural_signal is True:

        return context

    suspended = {
        "contract": CONTRACT,
        "version": VERSION,
        "suspended": True,
        "suspended_reason": (
            "non-architectural turn: the architectural context is retained "
            "in the session but not injected"
        ),
        "domain": domain,
        # session identity is kept so the turn is still attributable
        "session_id": context.get("session_id"),
        "conversation_id": context.get("conversation_id"),
        "context_hash": context.get("context_hash"),
    }

    for key in _ARCHITECTURAL_PAYLOAD_KEYS:

        suspended[key] = _NEUTRAL[key]

    # requirement: no architectural recent turns are injected
    recent = context.get("recent_turns") or []

    suspended["recent_turns"] = [
        turn for turn in recent if not _is_architectural_turn(turn)
    ]

    suspended["turn_has_architectural_signal"] = False

    suspended["context_sources"] = ["session_state", "domain_isolation"]

    suspended["provenance"] = {
        "engine": "ConversationDomainV1",
        "version": VERSION,
        "suspended": True,
        "domain": domain,
    }

    return suspended


# ==========================================================
# 4. THE ONE-CALL HELPER USED BY THE CHAT RUNTIME
# ==========================================================

def resolve_turn_domain(
    text: Any,
    architectural_context: Any = None,
    *,
    understanding: Any = None,
    context: Any = None,
) -> Dict[str, Any]:

    """Classify the turn and return the safe context + the domain block."""

    signal = None

    if isinstance(architectural_context, dict):

        signal = architectural_context.get("turn_has_architectural_signal")

    domain = classify_domain(
        text,
        understanding=understanding,
        architectural_signal=signal,
        context=context,
    )

    safe_context = project_context_for_domain(
        architectural_context,
        domain["domain"],
        architectural_signal=signal,
    )

    return {
        "domain": domain,
        "architectural_context": safe_context,
        "domain_block": {
            "contract": CONTRACT,
            "version": VERSION,
            "domain": domain["domain"],
            "guidance": domain_guidance(domain["domain"]),
            "architectural_context_injected": (
                domain["domain"] == "architecture" or signal is True
            ),
            "architectural_context_suspended": bool(
                isinstance(safe_context, dict) and safe_context.get("suspended")
            ),
        },
    }


# ==========================================================
# THE CLASS
# ==========================================================

class ConversationDomainV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    MUTATES_SESSION_CONTEXT = False
    DELETES_ARCHITECTURAL_CONTEXT = False
    GENERATES_DESIGN = False
    RENDERS = False
    USES_VISION = False

    def classify(self, text, **kwargs):

        return classify_domain(text, **kwargs)

    def project(self, architectural_context, domain, **kwargs):

        return project_context_for_domain(architectural_context, domain, **kwargs)

    def resolve(self, text, architectural_context=None, **kwargs):

        return resolve_turn_domain(text, architectural_context, **kwargs)


conversation_domain = ConversationDomainV1()
