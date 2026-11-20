"""Conversation interaction carrier (V1) — isolated self-checks.

Proves the clean carrier:

    1. the fields EXACTLY match the contract
    2. no confidence / score / truth / status / id / authority field
    3. a governance-reference provenance is rejected
    4. an out-of-vocabulary hint is rejected; a missing statement is rejected
    5. the carrier is immutable
    6. the carrier imports nothing from the frozen packages
    7. the frozen packages do not reference the new layer
"""

from __future__ import annotations


import ast
import dataclasses
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.interpretation.conversation_interaction_carrier_v1 import (
    CARRIER_FIELDS,
    CONTRACT,
    ConversationInteractionCarrier,
    ConversationInteractionCarrierError,
    REASON_GOVERNANCE_REFERENCE,
    REASON_NOT_A_STATEMENT,
    REASON_UNKNOWN_CLAIM_TYPE,
)


MODULE = (
    Path(__file__).resolve().parents[1] / "conversation_interaction_carrier_v1.py"
)

ROOT = Path(__file__).resolve().parents[3]


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
    "session_reference",
    "interaction_nonce",
)


FROZEN_PACKAGES = ("conversation", "vision", "governance")

NEW_LAYER_TOKENS = (
    "core.interpretation",
    "conversation_claim_type_hint",
    "conversation_interaction_carrier",
    "conversation_interpretation_adapter",
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


def _carrier(**overrides):

    fields = {
        "statement": "the bedroom is next to the living room",
        "claim_type_hint": "spatial_relationship",
        "basis": ("interpreter",),
        "limitations": ("no scale",),
    }

    fields.update(overrides)

    return ConversationInteractionCarrier(**fields)


# ==========================================================
# 1. the exact contract
# ==========================================================

def test_the_fields_exactly_match_the_contract():

    assert CARRIER_FIELDS == (
        "statement",
        "claim_type_hint",
        "basis",
        "limitations",
        "provenance",
    )

    assert tuple(f.name for f in dataclasses.fields(ConversationInteractionCarrier)) == (
        CARRIER_FIELDS
    )

    assert ConversationInteractionCarrier.FIELDS == CARRIER_FIELDS


def test_the_provenance_defaults_to_conversation():

    assert _carrier().provenance == "conversation"


def test_basis_and_limitations_are_tuples():

    carrier = _carrier(basis=["a", "b", "a"], limitations="only one")

    assert carrier.basis == ("a", "b")

    assert carrier.limitations == ("only one",)


# ==========================================================
# 2. no forbidden field
# ==========================================================

def test_no_forbidden_field_in_the_payload():

    payload = _carrier().to_dict()

    for forbidden in FORBIDDEN_NAMES:

        assert forbidden not in payload

    data_keys = {
        key
        for key in payload
        if key not in ("contract", "version")
        and not isinstance(payload[key], bool)
    }

    assert data_keys == set(CARRIER_FIELDS)


def test_the_declaration_flags_are_clean():

    assert ConversationInteractionCarrier.IS_ADVISORY is True

    assert ConversationInteractionCarrier.CREATES_IDENTITY is False

    assert ConversationInteractionCarrier.GRANTS_AUTHORITY is False

    assert ConversationInteractionCarrier.CARRIES_CONFIDENCE is False

    assert ConversationInteractionCarrier.DECIDES_TRUTH is False


# ==========================================================
# 3. a governance reference is rejected
# ==========================================================

def test_a_governance_reference_provenance_is_rejected():

    for reference in ("clm_abc", "lic_x", "dev_x", "eev_x", "kcd_x"):

        with pytest.raises(ConversationInteractionCarrierError) as error:

            _carrier(provenance=reference)

        assert REASON_GOVERNANCE_REFERENCE in str(error.value)


# ==========================================================
# 4. malformed fields are rejected
# ==========================================================

def test_an_out_of_vocabulary_hint_is_rejected():

    with pytest.raises(ConversationInteractionCarrierError) as error:

        _carrier(claim_type_hint="not_a_claim_type")

    assert REASON_UNKNOWN_CLAIM_TYPE in str(error.value)


def test_a_missing_statement_is_rejected():

    for statement in ("", "   ", None):

        with pytest.raises(ConversationInteractionCarrierError) as error:

            _carrier(statement=statement)

        assert REASON_NOT_A_STATEMENT in str(error.value)


def test_a_none_hint_is_allowed():

    assert _carrier(claim_type_hint=None).claim_type_hint is None


# ==========================================================
# 5. immutability
# ==========================================================

def test_the_carrier_is_immutable():

    carrier = _carrier()

    with pytest.raises(FrozenInstanceError):

        carrier.statement = "changed"


# ==========================================================
# 6. dependency direction
# ==========================================================

def test_the_carrier_does_not_import_the_frozen_packages():

    for root in _imported_roots(MODULE):

        for frozen in (
            "core.conversation",
            "core.vision",
            "core.governance",
            "core.runtime",
        ):

            assert not root.startswith(frozen), root


def test_the_carrier_references_no_forbidden_name():

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
# 7. the frozen surfaces are unchanged
# ==========================================================

def test_the_frozen_packages_do_not_reference_the_new_layer():

    for package in FROZEN_PACKAGES:

        for path in sorted((ROOT / "core" / package).rglob("*.py")):

            source = path.read_text(encoding="utf-8", errors="ignore")

            for token in NEW_LAYER_TOKENS:

                assert token not in source, (str(path), token)


def test_app_py_does_not_reference_the_new_layer():

    source = (ROOT / "app.py").read_text(encoding="utf-8", errors="ignore")

    for token in NEW_LAYER_TOKENS:

        assert token not in source, token
