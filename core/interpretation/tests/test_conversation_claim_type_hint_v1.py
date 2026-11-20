"""Conversation claim-type hint layer (V1) — isolated self-checks.

Proves the conversation-side interpretation layer:

    1. every claim type is produced by a representative statement
    2. EVERY declared marker (English and Persian) classifies to its rule
    3. an unclassifiable / blank statement yields None (no default)
    4. a non-string statement is rejected
    5. the artefact carries exactly two DATA fields and no forbidden field
    6. the artefact is immutable and validates its vocabulary
    7. the vocabulary is a local mirror (a subset of the governance vocabulary)
    8. the layer imports NOTHING from core.*  (stdlib only)
    9. the layer references no taxonomy / score / truth / status field
   10. the `meaning` argument is NOT read (the classification is statement-only)
   11. the class + singleton agree with the function
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.interpretation.conversation_claim_type_hint_v1 import (
    ALTERNATIVE_INTERPRETATION_MARKERS,
    CLAIM_TYPE_HINT_VOCABULARY,
    CONTRACT,
    EXISTENCE_MARKERS,
    FUNCTIONAL_RELATIONSHIP_MARKERS,
    FUNCTIONAL_ROLE_MARKERS,
    PROVENANCE_CONVERSATION,
    REASON_NOT_A_STATEMENT,
    REASON_UNKNOWN_CLAIM_TYPE,
    RULES,
    SEMANTIC_SPACE_MARKERS,
    SPATIAL_RELATIONSHIP_MARKERS,
    ConversationClaimTypeHint,
    ConversationClaimTypeHintError,
    ConversationClaimTypeHintInterpreter,
    conversation_claim_type_hint_interpreter,
    to_claim_type_hint,
)


MODULE = (
    Path(__file__).resolve().parents[1] / "conversation_claim_type_hint_v1.py"
)


# The governance vocabulary this layer MIRRORS. Hard-coded (the layer imports
# nothing from governance); the alignment is a CONTRACT, not a dependency.
GOVERNANCE_CLAIM_TYPES_MIRROR = (
    "existence",
    "semantic_space",
    "functional_role",
    "functional_relationship",
    "spatial_relationship",
    "alternative_interpretation",
)


FORBIDDEN_NAMES = (
    "candidate_kind",
    "knowledge_class",
    "domain",
    "confidence",
    "confidence_kind",
    "score",
    "truth",
    "truth_status",
    "status",
    "approval",
    "is_true",
    "verified_truth",
    "claim_id",
    "licence_id",
    "candidate_id",
)


def _imported_roots(path):

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    roots = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            roots.extend(alias.name for alias in node.names)

        elif isinstance(node, ast.ImportFrom):

            if node.module:

                roots.append(node.module)

    return roots


# ==========================================================
# 1. each claim type
# ==========================================================

def test_spatial_relationship():

    hint = to_claim_type_hint("the bedroom is next to the living room")

    assert hint.claim_type_hint == "spatial_relationship"


def test_functional_role():

    hint = to_claim_type_hint("this space is used for sleeping")

    assert hint.claim_type_hint == "functional_role"


def test_functional_relationship():

    hint = to_claim_type_hint("the corridor connects to the kitchen")

    assert hint.claim_type_hint == "functional_relationship"


def test_semantic_space():

    hint = to_claim_type_hint("the master bedroom means the parents room")

    assert hint.claim_type_hint == "semantic_space"


def test_alternative_interpretation():

    hint = to_claim_type_hint("it is not a bedroom but rather a study")

    assert hint.claim_type_hint == "alternative_interpretation"


def test_existence():

    hint = to_claim_type_hint("there is a bed in this space")

    assert hint.claim_type_hint == "existence"


# ==========================================================
# 2. every declared marker (English and Persian)
# ==========================================================

def test_every_declared_marker_classifies_to_its_rule():

    mismatches = []

    for claim_type, markers in RULES:

        for marker in markers:

            got = to_claim_type_hint("this " + marker + " that").claim_type_hint

            if got != claim_type:

                mismatches.append((claim_type, marker, got))

    assert mismatches == []


def test_the_persian_markers_are_present_and_distinct():

    for markers in (
        ALTERNATIVE_INTERPRETATION_MARKERS,
        SPATIAL_RELATIONSHIP_MARKERS,
        FUNCTIONAL_RELATIONSHIP_MARKERS,
        FUNCTIONAL_ROLE_MARKERS,
        EXISTENCE_MARKERS,
        SEMANTIC_SPACE_MARKERS,
    ):

        assert any(not marker.isascii() for marker in markers), markers


def test_a_persian_spatial_statement_classifies():

    # "اتاق خواب كنار پذیرایی است" — the bedroom is beside the living area
    statement = (
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 "
        "\u06a9\u0646\u0627\u0631 \u067e\u0630\u06cc\u0631\u0627\u06cc\u06cc "
        "\u0627\u0633\u062a"
    )

    assert to_claim_type_hint(statement).claim_type_hint == "spatial_relationship"


# ==========================================================
# 3. absence is first-class (no default)
# ==========================================================

def test_an_unclassifiable_statement_yields_none():

    hint = to_claim_type_hint("a random sentence about nothing at all")

    assert hint.claim_type_hint is None


def test_a_blank_statement_yields_none():

    for statement in ("", "   ", "\n\t "):

        assert to_claim_type_hint(statement).claim_type_hint is None


def test_punctuation_does_not_break_a_marker():

    hint = to_claim_type_hint("The bedroom, next to the living room!")

    assert hint.claim_type_hint == "spatial_relationship"


# ==========================================================
# 4. a non-string statement is rejected
# ==========================================================

def test_a_non_string_statement_is_rejected():

    for value in (None, 42, ["x"], {"a": 1}):

        with pytest.raises(ConversationClaimTypeHintError) as error:

            to_claim_type_hint(value)

        assert REASON_NOT_A_STATEMENT in str(error.value)


# ==========================================================
# 5. the clean artefact
# ==========================================================

def test_the_artefact_carries_exactly_two_data_fields():

    payload = to_claim_type_hint("there is a bed").to_dict()

    assert payload["claim_type_hint"] == "existence"

    assert payload["provenance"] == PROVENANCE_CONVERSATION

    assert payload["contract"] == CONTRACT

    # exactly two DATA fields
    data_keys = {
        key for key in payload if key not in ("contract", "version")
        and not isinstance(payload[key], bool)
    }

    assert data_keys == {"claim_type_hint", "provenance"}


def test_no_forbidden_field_in_the_artefact():

    payload = to_claim_type_hint("there is a bed").to_dict()

    for forbidden in FORBIDDEN_NAMES:

        assert forbidden not in payload


def test_the_declaration_flags_are_clean():

    assert ConversationClaimTypeHint.IS_ADVISORY is True

    assert ConversationClaimTypeHint.CREATES_IDENTITY is False

    assert ConversationClaimTypeHint.GRANTS_AUTHORITY is False

    assert ConversationClaimTypeHint.CARRIES_CONFIDENCE is False

    assert ConversationClaimTypeHint.DECIDES_TRUTH is False


def test_the_artefact_is_immutable():

    hint = to_claim_type_hint("there is a bed")

    with pytest.raises(FrozenInstanceError):

        hint.claim_type_hint = "existence"


# ==========================================================
# 6. the vocabulary is a local mirror
# ==========================================================

def test_the_vocabulary_is_the_declared_mirror():

    assert CLAIM_TYPE_HINT_VOCABULARY == GOVERNANCE_CLAIM_TYPES_MIRROR


def test_the_vocabulary_is_a_subset_of_the_governance_mirror():

    for token in CLAIM_TYPE_HINT_VOCABULARY:

        assert token in GOVERNANCE_CLAIM_TYPES_MIRROR


def test_every_rule_targets_a_vocabulary_token():

    for claim_type, _markers in RULES:

        assert claim_type in CLAIM_TYPE_HINT_VOCABULARY


def test_an_unknown_token_is_rejected():

    with pytest.raises(ConversationClaimTypeHintError) as error:

        ConversationClaimTypeHint(claim_type_hint="not_a_claim_type")

    assert REASON_UNKNOWN_CLAIM_TYPE in str(error.value)


# ==========================================================
# 7. dependency direction — stdlib only
# ==========================================================

def test_the_layer_imports_nothing_from_core():

    for root in _imported_roots(MODULE):

        assert not root.startswith("core"), "imported %r" % (root,)

    for forbidden in (
        "core.governance",
        "core.conversation",
        "core.vision",
        "core.runtime",
    ):

        assert forbidden not in _imported_roots(MODULE)


# ==========================================================
# 8. no taxonomy / score / truth / status reference
# ==========================================================

def test_the_layer_references_no_forbidden_name():

    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))

    offenders = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Constant) and isinstance(node.value, str):

            if node.value.strip().lower() in FORBIDDEN_NAMES:

                offenders.append(node.value)

        if isinstance(node, ast.Attribute):

            if node.attr in FORBIDDEN_NAMES:

                offenders.append(node.attr)

    assert offenders == []


# ==========================================================
# 9. the `meaning` argument is NOT read
# ==========================================================

def test_the_meaning_argument_is_not_read():

    statement = "the bedroom is next to the living room"

    plain = to_claim_type_hint(statement)

    with_meaning = to_claim_type_hint(
        statement,
        meaning={
            "domain": "spatial_relationship",
            "candidate_kind": "rule",
            "knowledge_class": "DESIGN_RULE",
            "confidence": 0.99,
            "status": "observed",
        },
    )

    opaque = to_claim_type_hint(statement, meaning=object())

    assert plain.claim_type_hint == "spatial_relationship"

    assert with_meaning.claim_type_hint == plain.claim_type_hint

    assert opaque.claim_type_hint == plain.claim_type_hint


# ==========================================================
# 10. the class and the singleton
# ==========================================================

def test_the_class_agrees_with_the_function():

    statement = "there is a bed"

    assert (
        ConversationClaimTypeHintInterpreter().interpret(statement).claim_type_hint
        == to_claim_type_hint(statement).claim_type_hint
    )


def test_the_singleton_works():

    hint = conversation_claim_type_hint_interpreter.interpret("there is a bed")

    assert hint.claim_type_hint == "existence"

    assert "advisory=True" in repr(conversation_claim_type_hint_interpreter)


# ==========================================================
# 11. the declared priority
# ==========================================================

def test_existence_precedes_semantic_space():

    # "there is a ..." must be an EXISTENCE claim, not a definition
    assert to_claim_type_hint("there is a bedroom").claim_type_hint == "existence"


def test_the_first_matching_rule_wins():

    # a statement carrying both a spatial and an existence marker resolves to
    # the higher-priority rule (spatial)
    statement = "there is a window next to the bed"

    assert to_claim_type_hint(statement).claim_type_hint == "spatial_relationship"
