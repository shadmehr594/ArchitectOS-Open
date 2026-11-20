# ==========================================================
# ArchitectOS Execution Boundary v1
#
# PHASE 08G — FUTURE TOOL-EXECUTION BOUNDARY
#
# This module is a CONTRACT, not an implementation.
#
# It names the five capability stages ArchitectOS will eventually need,
# and states truthfully which of them exist TODAY.
#
#   UNDERSTAND  turn semantics + meaning normalization   <- Phase 08
#   LEARN       permanent learned knowledge              <- NOT IMPLEMENTED
#   RECALL      answer from knowledge                    <- existing LLM chat
#   EXECUTE     draw / render / run code                 <- existing frozen
#                                                           render path only
#   VERIFY      validate a learned rule                  <- NOT IMPLEMENTED
#
# Phase 08 MUST NOT implement autonomous code execution or drawing.
# Nothing in this module can execute anything.
# ==========================================================


from __future__ import annotations


from core.conversation.turn_semantics_v1 import (
    TURN_QUESTION,
    TURN_INSTRUCTION,
    TURN_CORRECTION,
    TURN_TEACHING_STATEMENT,
    TURN_CONFIRMATION_REQUEST,
    TURN_NORMAL_CONVERSATION,
    TURN_OFFER_TO_TEACH,
    TURN_KNOWLEDGE_REFLECTION,
    TURN_UNKNOWN,
)


CONTRACT = "ExecutionBoundaryV1"
VERSION = "1.0"


CAP_UNDERSTAND = "UNDERSTAND"
CAP_LEARN = "LEARN"
CAP_RECALL = "RECALL"
CAP_EXECUTE = "EXECUTE"
CAP_VERIFY = "VERIFY"


CAPABILITIES = (

    CAP_UNDERSTAND,
    CAP_LEARN,
    CAP_RECALL,
    CAP_EXECUTE,
    CAP_VERIFY,
)


# ----------------------------------------------------------
# CAPABILITY DECLARATION
#
# `implemented` describes TODAY, not the plan.
# ----------------------------------------------------------

DECLARATION = {

    CAP_UNDERSTAND: {
        "implemented": True,
        "implemented_in_phase": "08",
        "module": "core/conversation/turn_semantics_v1.py",
        "notes": (
            "Deterministic turn classification + meaning normalization. "
            "Produces candidates, never knowledge."
        ),
        "can_mutate_files": False,
        "can_execute_code": False,
        "can_call_render": False,
    },

    CAP_LEARN: {
        "implemented": False,
        "implemented_in_phase": None,
        "module": None,
        "notes": (
            "Permanent learned knowledge is explicitly out of scope for "
            "Phase 08. No promotion path exists."
        ),
        "can_mutate_files": False,
        "can_execute_code": False,
        "can_call_render": False,
    },

    CAP_RECALL: {
        "implemented": True,
        "implemented_in_phase": "pre-08 (frozen)",
        "module": "core/chat/chat_architect.py (canonical chat reply)",
        "notes": (
            "Question turns keep using the existing canonical chat path. "
            "Phase 08 does not change how the model is asked."
        ),
        "can_mutate_files": False,
        "can_execute_code": False,
        "can_call_render": False,
    },

    CAP_EXECUTE: {
        "implemented": "pre-existing only",
        "implemented_in_phase": "01-06 / 07 (frozen)",
        "module": "core/render/* (frozen render pipeline)",
        "notes": (
            "The existing frozen render pipeline still owns EXECUTE. "
            "Phase 08 adds NO new execution capability and introduces no "
            "new execution route. An INSTRUCTION turn is handed to the "
            "pre-existing path unchanged."
        ),
        "can_mutate_files": True,
        "can_execute_code": True,
        "can_call_render": True,
        "owned_by_phase_08": False,
    },

    CAP_VERIFY: {
        "implemented": False,
        "implemented_in_phase": None,
        "module": None,
        "notes": (
            "Validating a learned rule against geometry/regulation is a "
            "later phase. Nothing validates candidates in Phase 08."
        ),
        "can_mutate_files": False,
        "can_execute_code": False,
        "can_call_render": False,
    },
}


# ----------------------------------------------------------
# TURN -> CAPABILITY
# ----------------------------------------------------------

_TURN_TO_CAPABILITY = {

    TURN_QUESTION: CAP_RECALL,

    TURN_CONFIRMATION_REQUEST: CAP_UNDERSTAND,

    TURN_TEACHING_STATEMENT: CAP_UNDERSTAND,

    TURN_CORRECTION: CAP_UNDERSTAND,

    TURN_NORMAL_CONVERSATION: CAP_UNDERSTAND,

    # PHASE 09 — a teaching intent is a KNOWLEDGE turn. It must never be
    # routed to EXECUTE, so it maps to UNDERSTAND and is answered with a
    # clarifying question.
    TURN_OFFER_TO_TEACH: CAP_UNDERSTAND,

    # TEACHING SESSION STATE FIX — a read-only reflection turn answers
    # from the EXISTING corpus. It is a RECALL turn: it writes nothing,
    # learns nothing and never reaches EXECUTE.
    TURN_KNOWLEDGE_REFLECTION: CAP_RECALL,

    # An instruction is an ACTION request, never architectural knowledge.
    TURN_INSTRUCTION: CAP_EXECUTE,

    TURN_UNKNOWN: CAP_UNDERSTAND,
}


def capability_for_turn(turn_kind):

    return _TURN_TO_CAPABILITY.get(turn_kind, CAP_UNDERSTAND)


def is_knowledge_turn(turn_kind):

    """Knowledge/teaching turns must never be routed to execution."""

    return capability_for_turn(turn_kind) in (
        CAP_UNDERSTAND,
        CAP_LEARN,
        CAP_RECALL,
        CAP_VERIFY,
    )


def is_action_turn(turn_kind):

    return capability_for_turn(turn_kind) == CAP_EXECUTE


# ----------------------------------------------------------
# HARD GUARD
# ----------------------------------------------------------

def phase_08_execution_implemented():

    """Phase 08 introduces no execution capability. Always False."""

    return False


def assert_execution_not_implemented_by_phase_08():

    if DECLARATION[CAP_EXECUTE].get("owned_by_phase_08"):

        raise AssertionError(
            "Phase 08 must not own EXECUTE"
        )

    if DECLARATION[CAP_LEARN]["implemented"]:

        raise AssertionError(
            "Phase 08 must not implement LEARN"
        )

    return True


def describe():

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "capabilities": list(CAPABILITIES),

        "declaration": DECLARATION,

        "turn_to_capability": dict(_TURN_TO_CAPABILITY),

        "phase_08_execution_implemented": False,

        "phase_08_learning_implemented": False,

        "future_boundary": (
            "UNDERSTAND -> LEARN -> RECALL -> EXECUTE -> VERIFY. "
            "Phase 08 implements UNDERSTAND only and reuses the existing "
            "frozen RECALL/EXECUTE paths without modifying them."
        ),
    }
