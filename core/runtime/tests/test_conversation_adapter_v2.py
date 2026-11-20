"""Conversation Adapter V2 — HumanActToken integration.

Proves that the claim-request path REQUIRES an explicit human act:

    1. a claim request without a token is rejected
    2. a valid issued token is accepted and the request is created
    3. the token is consumed exactly once after a successful submission
    4. a replay (consumed token) is rejected
    5. a released token is rejected; unknown / forged / wrong-type are rejected
    6. a FAILED submission never burns the token
    7. the advisory path still needs no token and never yields a claim request
    8. the V1 guarantees still hold (confidence dropped, forbidden fields rejected)
    9. dependency direction: the token module is runtime-local, no client import
"""

from __future__ import annotations


import ast
from pathlib import Path

import pytest

from core.runtime.conversation_adapter_v1 import (
    ConversationAdapterError,
    REASON_TOKEN_CONSUMED,
    REASON_TOKEN_NOT_A_TOKEN,
    REASON_TOKEN_RELEASED,
    REASON_TOKEN_REQUIRED,
    REASON_TOKEN_UNKNOWN,
    to_advisory_input,
    to_claim_request_input,
)
from core.runtime.human_act_token_v1 import (
    HumanActToken,
    HumanActTokenLedger,
    STATE_ISSUED,
    human_act_token_state,
    issue_human_act_token,
)


MODULE = Path(__file__).resolve().parents[1] / "conversation_adapter_v1.py"


def _intent():

    """A fresh, issued human-act token (one-shot — never reuse)."""

    return issue_human_act_token(turn_kind="TEACHING_STATEMENT")


def _candidate(**overrides):

    fields = {
        "candidate_id": "tc_abc123",
        "source_turn_id": "turn_xyz789",
        "raw_statement": "a closet is a storage space",
        "normalized_meaning": "a closet is a storage space",
        "language": "mixed",
        "turn_kind": "TEACHING_STATEMENT",
        "candidate_kind": "definition",
        "provenance": "human_teacher",
        "confidence": 0.87,
        "confidence_kind": "learning_state",
        "status": "observed",
    }

    fields.update(overrides)

    return fields


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
# 1-2. required token / accepted
# ==========================================================

def test_a_claim_request_without_a_token_is_rejected():

    with pytest.raises(ConversationAdapterError) as error:

        to_claim_request_input("a bed exists in this space")

    assert REASON_TOKEN_REQUIRED in str(error.value)


def test_an_explicit_none_intent_is_rejected():

    with pytest.raises(ConversationAdapterError) as error:

        to_claim_request_input("a bed exists", intent=None)

    assert REASON_TOKEN_REQUIRED in str(error.value)


def test_a_valid_issued_token_is_accepted():

    token = _intent()

    result = to_claim_request_input("a bed exists in this space", intent=token)

    assert result.proposal_fields is not None

    assert result.proposal_fields["proposed_content"] == "a bed exists in this space"

    assert result.advisory_material is None


def test_neutral_fields_are_preserved_through_the_token_path():

    result = to_claim_request_input(
        "a bed exists",
        intent=_intent(),
        language="fa",
        proposed_claim_type="existence",
        trigger_references=("obs_bed_region",),
        basis=("observed",),
        limitations=("no geometry asserted",),
    )

    fields = result.proposal_fields

    assert fields["language"] == "fa"

    assert fields["proposed_claim_type"] == "existence"

    assert fields["trigger_references"] == ("obs_bed_region",)

    assert fields["basis"] == ("observed",)

    assert fields["limitations"] == ("no geometry asserted",)


# ==========================================================
# 3-4. consumption and replay
# ==========================================================

def test_the_token_is_consumed_after_a_successful_submission():

    token = _intent()

    assert human_act_token_state(token.token_reference) == STATE_ISSUED

    to_claim_request_input("a bed exists", intent=token)

    assert human_act_token_state(token.token_reference) == "consumed"


def test_a_replayed_token_is_rejected():

    token = _intent()

    to_claim_request_input("a bed exists", intent=token)

    with pytest.raises(ConversationAdapterError) as error:

        to_claim_request_input("a bed exists again", intent=token)

    assert REASON_TOKEN_CONSUMED in str(error.value)


# ==========================================================
# 5. released / unknown / forged / wrong type
# ==========================================================

def test_a_released_token_is_rejected():

    from core.runtime.human_act_token_v1 import release_human_act_token

    token = _intent()

    release_human_act_token(token)

    with pytest.raises(ConversationAdapterError) as error:

        to_claim_request_input("a bed exists", intent=token)

    assert REASON_TOKEN_RELEASED in str(error.value)


def test_an_unknown_token_is_rejected():

    ledger = HumanActTokenLedger()

    ledger.issue(turn_kind="TEACHING_STATEMENT")

    forged = HumanActToken(
        token_reference="hat_never_issued",
        turn_kind="TEACHING_STATEMENT",
    )

    with pytest.raises(ConversationAdapterError) as error:

        to_claim_request_input("a bed exists", intent=forged)

    assert REASON_TOKEN_UNKNOWN in str(error.value)


def test_a_wrong_object_type_is_rejected():

    for value in ("hat_x", {"token_reference": "hat_x"}, 42, object()):

        with pytest.raises(ConversationAdapterError) as error:

            to_claim_request_input("a bed exists", intent=value)

        assert REASON_TOKEN_NOT_A_TOKEN in str(error.value)


# ==========================================================
# 6. a failed submission never burns the token
# ==========================================================

def test_an_empty_statement_does_not_consume_the_token():

    token = _intent()

    with pytest.raises(ConversationAdapterError):

        to_claim_request_input("   ", intent=token)

    assert human_act_token_state(token.token_reference) == STATE_ISSUED


def test_a_rejected_traceability_reference_does_not_consume_the_token():

    token = _intent()

    with pytest.raises(ConversationAdapterError):

        to_claim_request_input("a bed exists", intent=token, traceability_reference="clm_x")

    assert human_act_token_state(token.token_reference) == STATE_ISSUED


def test_the_token_can_be_used_once_the_reason_is_fixed():

    token = _intent()

    with pytest.raises(ConversationAdapterError):

        to_claim_request_input("", intent=token)

    # still issued -> a corrected submission succeeds
    result = to_claim_request_input("a bed exists", intent=token)

    assert result.proposal_fields is not None

    assert human_act_token_state(token.token_reference) == "consumed"


# ==========================================================
# 7. the advisory path is unchanged
# ==========================================================

def test_the_advisory_path_needs_no_token():

    result = to_advisory_input(_candidate())

    assert result.proposal_fields is None

    assert result.advisory_material is not None


def test_the_advisory_path_never_yields_a_claim_request():

    result = to_advisory_input(_candidate())

    assert result.proposal_fields is None


def test_a_candidate_still_cannot_be_a_claim_request_even_with_a_token():

    with pytest.raises(ConversationAdapterError):

        to_claim_request_input(_candidate(), intent=_intent())


# ==========================================================
# 8. V1 guarantees still hold
# ==========================================================

def test_confidence_is_still_dropped():

    result = to_advisory_input(_candidate(confidence=0.99))

    payload = result.to_dict()

    assert "confidence" not in payload

    assert "confidence" not in (payload.get("advisory_material") or {})

    assert "0.99" not in repr(payload)


def test_forbidden_fields_are_still_rejected():

    for field in ("truth", "approved", "claim_id", "scope_authority"):

        with pytest.raises(ConversationAdapterError):

            to_advisory_input(_candidate(**{field: "x"}))


def test_the_proposal_fields_carry_no_confidence_or_truth():

    result = to_claim_request_input("a bed exists", intent=_intent())

    for field in ("truth", "confidence", "certainty", "approval", "status"):

        assert field not in result.proposal_fields


# ==========================================================
# 9. dependency direction
# ==========================================================

def test_the_adapter_imports_the_runtime_token_module():

    roots = _imported_roots(MODULE)

    assert "core.runtime.human_act_token_v1" in roots


def test_the_adapter_imports_no_client_module():

    roots = _imported_roots(MODULE)

    for forbidden in (
        "core.conversation",
        "core.vision",
        "core.knowledge",
        "core.architecture.reasoning",
        "core.prompt_intelligence",
        "core.bim",
        "core.structure",
    ):

        assert forbidden not in roots


def test_the_adapter_calls_no_governance_factory():

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))

    called = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Call):

            func = node.func

            called.append(
                func.id
                if isinstance(func, ast.Name)
                else (func.attr if isinstance(func, ast.Attribute) else "")
            )

    for name in (
        "build_proposal",
        "mint_claim",
        "mint_licence_record",
        "record_derivation_event",
        "record_endorsement_event",
        "build_knowledge_candidate",
        "Claim",
        "LicenceRecord",
        "InterpretationProposal",
    ):

        assert name not in called
