# -*- coding: utf-8 -*-
"""CHAT-02D — user correction / negation semantics.

Scope: the SUBJECT/DOMAIN decision for a turn that CORRECTS the previous
exchange, the `conversation_repair` signal, and the reply register that a
correction needs. No routing change, no teaching change, no vision / BIM /
IFC / render path.

The fix is GRAMMATICAL, never utterance-driven. The acceptance sentence appears
in this file only as a test payload; production code must never name a topic.
`test_production_never_names_a_topic` is the proof of that property, and
`test_a_different_concept_pair_works_the_same_way` proves the parser
generalises beyond the acceptance pair.
"""

from pathlib import Path

import ast

import pytest

from core.chat.negation_scope_v1 import (
    affirmed_hit,
    has_contrastive_negation,
    is_affirmed,
    rejected_span,
)
from core.chat.conversation_domain_v1 import classify_domain
from core.chat.conversation_intent_boundary_v1 import (
    classify_conversation_intent,
)
from core.chat.conversational_naturalness_v1 import (
    conversation_naturalness_instruction,
    correction_context,
    resolve_turn_register,
)


ROOT = Path(__file__).resolve().parents[1]

# Test payloads only — never production vocabulary.
ARCH = "معماری"
MYST = "معمایی"
ARCH_EN = "architecture"
MYST_EN = "mystery"

# Production files this change owns.
CHANGED_FILES = (
    "core/chat/negation_scope_v1.py",
    "core/chat/conversation_intent_boundary_v1.py",
    "core/chat/conversation_domain_v1.py",
    "core/chat/conversational_naturalness_v1.py",
)


def _signals(text):
    return classify_conversation_intent(text)["signals"]


def _has_repair(text):
    return "conversation_repair" in _signals(text)


def _runtime_strings(path):
    """Every string literal in a module that is NOT a docstring."""

    tree = ast.parse(path.read_text(encoding="utf-8"))

    docstrings = set()

    for node in ast.walk(tree):

        if not isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue

        body = getattr(node, "body", [])

        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):

            docstrings.add(id(body[0].value))

    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


# ==========================================================
# 1. NEGATION POLARITY — cases A, B, E, F, G, H, I, J
# ==========================================================

def test_contrastive_correction_negates_the_trailing_subject():
    """A — 'mystery, NOT architecture'."""

    text = "معمایی گفتم نه معماری"

    assert is_affirmed(text, MYST) is True
    assert is_affirmed(text, ARCH) is False
    assert rejected_span(text) == ARCH


def test_reversed_contrast_affirms_the_trailing_subject():
    """B — 'architecture, NOT mystery' (the mirror image)."""

    text = "معماری گفتم نه معمایی"

    assert is_affirmed(text, ARCH) is True
    assert is_affirmed(text, MYST) is False
    assert rejected_span(text) == MYST


def test_negated_copula_after_the_subject():
    """E — 'معماری نبود' negates the architectural claim."""

    assert is_affirmed("معماری نبود", ARCH) is False


def test_a_preference_statement_keeps_its_subject():
    """F — a negative PREFERENCE is not a denial of the subject."""

    text = "من معماری دوست ندارم"

    assert is_affirmed(text, ARCH) is True
    assert has_contrastive_negation(text) is False
    assert _has_repair(text) is False


def test_english_contrastive_correction():
    """G — 'I said mystery, not architecture.'"""

    text = "I said mystery, not architecture."

    assert is_affirmed(text, MYST_EN) is True
    assert is_affirmed(text, ARCH_EN) is False
    assert rejected_span(text) == ARCH_EN


def test_english_reversed_contrast():
    """H — 'I said architecture, not mystery.'"""

    text = "I said architecture, not mystery."

    assert is_affirmed(text, ARCH_EN) is True
    assert is_affirmed(text, MYST_EN) is False


def test_english_capitalised_negation_is_recognised():
    """J — a capitalised 'Not' is still a negation."""

    text = "Not architecture, please."

    assert is_affirmed(text, ARCH_EN) is False


def test_plain_positive_request_is_not_negated():
    """I — 'I want architecture books.'"""

    text = "I want architecture books."

    assert is_affirmed(text, ARCH_EN) is True
    assert has_contrastive_negation(text) is False
    assert _has_repair(text) is False


# ==========================================================
# 2. DISCOURSE "نه،" — cases C, D, K
# ==========================================================

def test_discourse_no_does_not_negate_a_positive_request():
    """C — 'نه، معماری رو توضیح بده' still ASKS for architecture."""

    text = "نه، معماری رو توضیح بده"

    assert is_affirmed(text, ARCH) is True
    assert has_contrastive_negation(text) is False
    assert rejected_span(text) == ""
    assert _has_repair(text) is False


def test_discourse_no_with_a_negated_predicate_rejects_the_subject():
    """D — 'نه، معماری رو نمی‌خوام' explicitly does NOT want architecture."""

    text = "نه، معماری رو نمی‌خوام"

    assert is_affirmed(text, ARCH) is False
    assert _has_repair(text) is True


def test_dimension_correction_names_the_rejected_value():
    """K — '۱۲ متره، نه ۱۰ متر' corrects a dimension."""

    text = "اتاق ۱۲ متره، نه ۱۰ متر"

    assert has_contrastive_negation(text) is True
    assert rejected_span(text) == "۱۰ متر"
    assert _has_repair(text) is True


# ==========================================================
# 3. NO CORRECTION WHERE THERE IS NONE — cases L, M, N
# ==========================================================

def test_ordinary_mystery_request_is_not_a_correction():
    """L — a plain request must not infer a correction."""

    text = "کتاب معمایی چند تا انتخاب کن"

    assert is_affirmed(text, MYST) is True
    assert has_contrastive_negation(text) is False
    assert _has_repair(text) is False


def test_greeting_stays_a_greeting():
    """M — 'سلام'."""

    assert resolve_turn_register("سلام", _signals("سلام")) == "greeting"
    assert _has_repair("سلام") is False


def test_self_introduction_signal_is_preserved():
    """N — CHAT-01 self-introduction is untouched."""

    signals = _signals("خودت را معرفی کن")

    assert "self_introduction" in signals
    assert "conversation_repair" not in signals


# ==========================================================
# 4. SUBJECT + DOMAIN ROUTING
# ==========================================================

def test_correction_routes_to_general_not_architecture():
    decision = classify_conversation_intent("معمایی گفتم نه معماری")

    assert decision["intent"] == "GENERAL_CONVERSATION"
    assert decision["is_architecture"] is False
    assert classify_domain("معمایی گفتم نه معماری")["domain"] == "general"


def test_reversed_correction_keeps_the_architectural_subject():
    decision = classify_conversation_intent("معماری گفتم نه معمایی")

    assert decision["intent"] == "ARCHITECTURE_CONVERSATION"
    assert decision["is_architecture"] is True
    assert classify_domain("معماری گفتم نه معمایی")["domain"] == "architecture"


def test_domain_classifier_ignores_a_negated_marker():
    assert classify_domain("معماری نبود")["domain"] == "general"


# ==========================================================
# 5. CORRECTION SIGNAL
# ==========================================================

@pytest.mark.parametrize("text", [
    "معمایی گفتم نه معماری",
    "معماری گفتم نه معمایی",
    "معماری نبود",
    "نه، معماری رو نمی‌خوام",
    "I said mystery, not architecture.",
    "I said architecture, not mystery.",
    "Not architecture, please.",
    "اتاق ۱۲ متره، نه ۱۰ متر",
])
def test_correction_signal_is_raised(text):
    assert _has_repair(text) is True


@pytest.mark.parametrize("text", [
    "نه، معماری رو توضیح بده",
    "من معماری دوست ندارم",
    "I want architecture books.",
    "کتاب معمایی چند تا انتخاب کن",
    "سلام",
    "خودت را معرفی کن",
])
def test_correction_signal_is_not_raised(text):
    assert _has_repair(text) is False


# ==========================================================
# 6. REGISTER + DIRECTIVE
# ==========================================================

def test_a_correction_is_never_small_talk():
    """A correction asks for an ANSWER, so it is a detail request."""

    text = "معمایی گفتم نه معماری"

    assert resolve_turn_register(text, _signals(text)) == "detail_request"
    assert resolve_turn_register("سلام", _signals("سلام")) == "greeting"


def test_the_directive_names_the_rejected_term_and_the_original_task():
    text = "معمایی گفتم نه معماری"
    directive = correction_context(text, _signals(text))

    assert directive
    assert ARCH in directive                       # what was rejected
    assert "ORIGINAL request" in directive         # recover the earlier task
    assert "Do NOT reaffirm" in directive          # never re-assert it


def test_the_directive_is_empty_for_a_non_correction():
    for text in ("سلام", "I want architecture books.", "کتاب معمایی چند تا انتخاب کن"):
        assert correction_context(text, _signals(text)) == ""


def test_the_instruction_block_carries_the_correction_directive():
    text = "معمایی گفتم نه معماری"
    block = conversation_naturalness_instruction(text, _signals(text))

    assert "CORRECTION" in block
    assert ARCH in block


# ==========================================================
# 7. GENERALISATION — the parser is not bound to one topic pair
# ==========================================================

def test_a_different_concept_pair_works_the_same_way():
    """The same contrast shape, a completely different topic."""

    text = "شعر گفتم نه رمان"

    assert is_affirmed(text, "شعر") is True
    assert is_affirmed(text, "رمان") is False
    assert rejected_span(text) == "رمان"
    assert affirmed_hit(text, ("رمان",)) is False
    assert affirmed_hit(text, ("شعر",)) is True


def test_production_never_names_a_topic():
    """No production module may hardcode the acceptance vocabulary.

    Parsed with `ast`, not grepped: the modules legitimately DISCUSS the
    acceptance sentence in comments and docstrings, so only runtime string
    literals (docstrings excluded) are scanned.
    """

    forbidden = ("معمایی", "mystery")

    for relative in CHANGED_FILES:

        for literal in _runtime_strings(ROOT / relative):

            for token in forbidden:

                assert token not in literal, (relative, token)
