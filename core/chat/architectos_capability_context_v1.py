# -*- coding: utf-8 -*-
"""ARCHITECTOS — SELF-DESCRIPTION CAPABILITY CONTEXT V1.

Read-only, source-verified facts about what ArchitectOS can actually do, so a
self-introduction turn can be answered truthfully instead of with generic
assistant boilerplate.

WHAT THIS IS
------------
A tiny data module plus one pure function. It is NOT a feature registry, NOT a
capability engine, NOT a memory system and NOT a classifier. It holds no state,
performs no I/O, calls no LLM, and is never persisted.

HOW THE FACTS WERE ESTABLISHED (read-only audit, 2026-10-10)
------------------------------------------------------------
Every entry in ``VERIFIED_CAPABILITIES`` was checked against the running
implementation and its acceptance tests — never assumed from a module's
existence:

* Persian/English conversation and architectural discussion —
  ``ConversationIntentBoundaryV1`` resolves ``GENERAL_CONVERSATION`` and
  ``ARCHITECTURE_CONVERSATION`` deterministically (live-classified 0.80), and
  the full chat path was accepted end-to-end (backend + UI proxy + browser).
* Teaching with confirmation — the boundary resolves ``TEACHING`` (0.90) and
  ``core/teaching/architectural_teaching_v1.py`` documents that it "does not
  write memory, learn automatically, promote knowledge, or generate design
  reasoning". The teaching suites pass (154 cases).
* Corrections — the boundary emits ``conversation_repair`` and
  ``tests/test_correction_loop_01.py`` passes (35 cases).

WHAT IS DELIBERATELY EXCLUDED
-----------------------------
``NOT_OPERATIONAL`` lists what must NOT be advertised as an available action.
These are frozen, disconnected or unverified: the Vision V2 observation stack,
plan generation, CAD / BIM / IFC output, rendering (ComfyUI) and image
generation. A frozen pipeline is not an available action, so the model is told
plainly not to offer them. This list exists to prevent an invented feature
claim, which is the failure mode this module is here to stop.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple


CONTRACT = "ArchitectOSCapabilityContextV1"
VERSION = "1.0"


# ==========================================================
# VERIFIED — safe to state in a self-introduction
# ==========================================================

VERIFIED_CAPABILITIES: Tuple[Dict[str, str], ...] = (

    {
        "name": "Natural conversation",
        "statement": (
            "holds a natural conversation in Persian and English"
        ),
        "evidence": (
            "ConversationIntentBoundaryV1 GENERAL_CONVERSATION; live backend / "
            "UI-proxy / browser acceptance"
        ),
    },

    {
        "name": "Architectural discussion and reasoning",
        "statement": (
            "discusses and reasons about architecture and answers "
            "architectural questions"
        ),
        "evidence": (
            "ConversationIntentBoundaryV1 ARCHITECTURE_CONVERSATION (0.80); "
            "tests/test_architectural_intent_*.py"
        ),
    },

    {
        "name": "Human teaching",
        "statement": (
            "lets you teach it architectural rules; a taught rule is recorded "
            "as a PENDING candidate and is kept only after your explicit "
            "confirmation — nothing is learned or promoted automatically"
        ),
        "evidence": (
            "ConversationIntentBoundaryV1 TEACHING (0.90); "
            "core/teaching/architectural_teaching_v1.py (no memory write, no "
            "auto-promotion); teaching suites"
        ),
    },

    {
        "name": "Correction handling",
        "statement": (
            "understands when you correct or refine something it said and "
            "continues from the corrected version"
        ),
        "evidence": (
            "ConversationIntentBoundaryV1 conversation_repair; "
            "tests/test_correction_loop_01.py (35 cases)"
        ),
    },
)


# ==========================================================
# NOT OPERATIONAL — must never be offered as an available action
# ==========================================================

NOT_OPERATIONAL: Tuple[Dict[str, str], ...] = (

    {
        "name": "Building-plan generation",
        "reason": "no verified end-to-end plan generator is connected",
    },

    {
        "name": "CAD / BIM / IFC output",
        "reason": "those pipelines are frozen and are not wired into chat",
    },

    {
        "name": "Rendering and image generation",
        "reason": (
            "the render backend (ComfyUI) is externally managed and is not "
            "available to this conversation"
        ),
    },

    {
        "name": "Reading architectural drawings or photographs",
        "reason": (
            "the visual observation stack is frozen and is not an available "
            "action here"
        ),
    },
)


# ==========================================================
# PROMPT TEXT
# ==========================================================

def _bullet(item: Dict[str, str]) -> str:
    return "- " + item["statement"]


def self_introduction_context() -> str:
    """The identity/capability paragraph for a self-introduction turn.

    Pure and deterministic: derived only from the audited data above. Returns
    the empty string if the audit data were ever emptied, so a caller can
    always append the result unconditionally.
    """

    if not VERIFIED_CAPABILITIES:
        return ""

    lines = [

        "",
        "IDENTITY AND CAPABILITY CONTEXT (verified — describe yourself ONLY",
        "from this):",
        "",
        "ArchitectOS is a LOCAL ARCHITECTURAL AI ASSISTANT running on the",
        "user's own machine. What it can actually do today:",
        "",
    ]

    lines.extend(_bullet(item) for item in VERIFIED_CAPABILITIES)

    lines.extend([

        "",
        "It must NOT claim any other capability. In particular it must NOT",
        "offer or promise: " + "; ".join(
            item["name"] for item in NOT_OPERATIONAL
        ) + ". Those are not available in this conversation.",
        "",
        "Answer as yourself, in one short natural paragraph, using only the",
        "capabilities listed above. Do not invent extra features, do not",
        "present a marketing list, and do not mention source files, internal",
        "modules or version numbers.",
    ])

    return "\n".join(lines)


class ArchitectOSCapabilityContextV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    CREATES_SECOND_ASSISTANT = False
    CHANGES_ROUTING = False
    MUTATES_SESSION_CONTEXT = False
    READS_OR_WRITES_MEMORY = False
    CALLS_AN_LLM = False
    USES_VISION = False
    RENDERS = False

    def verified(self) -> Tuple[Dict[str, str], ...]:
        return VERIFIED_CAPABILITIES

    def not_operational(self) -> Tuple[Dict[str, str], ...]:
        return NOT_OPERATIONAL

    def context(self) -> str:
        return self_introduction_context()


capability_context = ArchitectOSCapabilityContextV1()
