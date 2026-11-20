"""Conversation -> Runtime adapter V1 — isolated self-checks.

PASS
    1. a TeachingCandidate yields ADVISORY input and NEVER a claim request
    2. neutral advisory fields are preserved
    3. an explicit statement yields neutral proposal_fields
    4. neutral claim-request fields are preserved

DROP
    5. confidence / confidence_kind are dropped
    6. status is dropped
    7. conversation-local id VALUES (tc_ / turn_) are dropped
    8. conversation-internal structure is dropped

REJECT
    9. truth / approval fields
   10. authority / identity fields
   11. a non-teaching turn kind
   12. a governance identity as a traceability reference

ANTI-PROMOTION
   13. a candidate can never be a claim request

HARDENING
   14. no governance object construction
   15. no identity generation
   16. no governance factory call
   17. import direction preserved
   18. no truth field, no persistence, immutable output
"""

from __future__ import annotations


import ast
import inspect
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.runtime.conversation_adapter_v1 import (
    ALLOWED_TURN_KINDS,
    ConversationAdapterError,
    ConversationRuntimeInput,
    PROPOSAL_FIELD_KEYS,
    to_advisory_input,
    to_claim_request_input,
)
from core.runtime.human_act_token_v1 import issue_human_act_token


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
        "knowledge_class": "definition",
        "scope": "current_project",
        "domain_tags": ["storage"],
        "zone_assignment": {"zone": "storage"},
        "space_topic": "closet",
        "entities": ["closet"],
        "relations": [],
        "polarity": "neutral",
        "rationale": "because storage",
        "created_at": 1.0,
        "updated_at": 1.0,
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


def _called_names(path):

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    names = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Call):

            func = node.func

            if isinstance(func, ast.Name):

                names.append(func.id)

            elif isinstance(func, ast.Attribute):

                names.append(func.attr)

    return names


# ==========================================================
# PASS
# ==========================================================

def test_candidate_yields_advisory_and_never_a_claim_request():

    result = to_advisory_input(_candidate())

    assert result.proposal_fields is None

    assert result.advisory_material is not None

    assert type(result.advisory_material).__name__ == "TeachingProposalMaterial"


def test_neutral_advisory_fields_are_preserved():

    result = to_advisory_input(_candidate(language="fa"))

    assert result.language == "fa"

    assert result.turn_kind == "TEACHING_STATEMENT"


def test_explicit_statement_yields_neutral_proposal_fields():

    result = to_claim_request_input(
        "a bed exists in this space", intent=_intent(), language="en"
    )

    assert result.proposal_fields is not None

    assert result.advisory_material is None

    assert set(result.proposal_fields) == set(PROPOSAL_FIELD_KEYS)


def test_neutral_claim_request_fields_are_preserved():

    result = to_claim_request_input(
        "a bed exists in this space",
        intent=_intent(),
        language="en",
        proposed_claim_type="existence",
        trigger_references=("obs_bed_region",),
        basis=("observed",),
        limitations=("no geometry asserted",),
    )

    fields = result.proposal_fields

    assert fields["proposed_content"] == "a bed exists in this space"

    assert fields["proposed_claim_type"] == "existence"

    assert fields["language"] == "en"

    assert fields["trigger_references"] == ("obs_bed_region",)

    assert fields["basis"] == ("observed",)

    assert fields["limitations"] == ("no geometry asserted",)


# ==========================================================
# DROP
# ==========================================================

def test_confidence_is_dropped():

    result = to_advisory_input(_candidate(confidence=0.99))

    payload = result.to_dict()

    assert "confidence" not in payload

    assert "confidence" not in (payload.get("advisory_material") or {})

    assert "0.99" not in repr(payload)


def test_confidence_kind_is_dropped():

    result = to_advisory_input(_candidate(confidence_kind="learning_state"))

    payload = result.to_dict()

    assert "confidence_kind" not in payload

    assert "confidence_kind" not in (payload.get("advisory_material") or {})


def test_status_is_dropped():

    result = to_advisory_input(_candidate(status="needs_confirmation"))

    payload = result.to_dict()

    assert "status" not in payload

    assert "status" not in (payload.get("advisory_material") or {})

    assert "needs_confirmation" not in repr(payload)


def test_conversation_local_id_values_are_dropped():

    result = to_advisory_input(_candidate())

    blob = repr(result.to_dict())

    # the VALUES must be gone (note: the allowed key `turn_kind` is not a value)
    assert "tc_abc123" not in blob

    assert "turn_xyz789" not in blob

    assert result.traceability_reference is None


def test_conversation_internal_structure_is_dropped():

    result = to_advisory_input(_candidate())

    payload = result.to_dict()

    # exact keys, not substrings: the advisory CONTENT is allowed to carry the
    # statement itself, but the conversation's internal structure is not
    keys = set(payload) | set(payload.get("advisory_material") or {})

    for name in (
        "candidate_id",
        "source_turn_id",
        "project_id",
        "domain",
        "domain_tags",
        "knowledge_class",
        "scope",
        "zone_assignment",
        "space_topic",
        "entities",
        "relations",
        "polarity",
        "clause_role",
        "clause_index",
        "clause_count",
        "source_statement",
        "rationale",
        "created_at",
        "updated_at",
    ):

        assert name not in keys


def test_dropped_fields_are_not_in_the_claim_request_path():

    result = to_claim_request_input("a bed exists", intent=_intent())

    for name in ("confidence", "status", "candidate_id", "source_turn_id"):

        assert name not in result.proposal_fields


# ==========================================================
# REJECT
# ==========================================================

def test_truth_and_approval_fields_are_rejected():

    for field in ("truth", "is_true", "truth_status", "approval", "approved", "certainty", "probability"):

        with pytest.raises(ConversationAdapterError):

            to_advisory_input(_candidate(**{field: "x"}))


def test_authority_and_identity_fields_are_rejected():

    for field in ("claim_id", "licence_id", "scope_authority", "knowledge_status"):

        with pytest.raises(ConversationAdapterError):

            to_advisory_input(_candidate(**{field: "x"}))


def test_a_non_teaching_turn_is_rejected():

    for turn_kind in ("QUESTION", "INSTRUCTION", "NORMAL_CONVERSATION", "UNKNOWN"):

        with pytest.raises(ConversationAdapterError):

            to_advisory_input(_candidate(turn_kind=turn_kind))


def test_allowed_turn_kinds_are_exactly_teaching_and_correction():

    assert ALLOWED_TURN_KINDS == ("TEACHING_STATEMENT", "CORRECTION")

    for turn_kind in ALLOWED_TURN_KINDS:

        assert to_advisory_input(_candidate(turn_kind=turn_kind)) is not None


def test_a_governance_identity_as_traceability_is_rejected():

    for value in ("clm_abc", "lic_abc", "dev_abc", "eev_abc", "kcd_abc"):

        with pytest.raises(ConversationAdapterError):

            to_claim_request_input(
                "a bed exists", intent=_intent(), traceability_reference=value
            )

        with pytest.raises(ConversationAdapterError):

            to_advisory_input(_candidate(), traceability_reference=value)


def test_no_source_is_rejected():

    with pytest.raises(ConversationAdapterError):

        to_advisory_input(None)


# ==========================================================
# ANTI-PROMOTION
# ==========================================================

def test_a_candidate_can_never_be_a_claim_request():

    with pytest.raises(ConversationAdapterError):

        to_claim_request_input(_candidate())


def test_a_mapping_can_never_be_a_claim_request():

    with pytest.raises(ConversationAdapterError):

        to_claim_request_input({"raw_statement": "a bed exists"})


def test_an_empty_statement_is_rejected():

    for value in ("", "   ", "\n"):

        with pytest.raises(ConversationAdapterError):

            to_claim_request_input(value)


def test_the_claim_request_entry_takes_no_candidate_parameter():

    parameters = set(inspect.signature(to_claim_request_input).parameters)

    assert "candidate" not in parameters

    assert "source" not in parameters

    assert "candidate_input" not in parameters


# ==========================================================
# HARDENING
# ==========================================================

def test_no_governance_object_construction():

    called = _called_names(MODULE)

    for name in (
        "Claim",
        "LicenceRecord",
        "DerivationEvent",
        "EndorsementEvent",
        "InterpretationProposal",
        "KnowledgeCandidate",
        "TeachingProposalMaterial",
    ):

        assert name not in called


def test_no_identity_generation():

    called = _called_names(MODULE)

    for name in (
        "uuid4",
        "uuid1",
        "mint_id",
        "new_claim_id",
        "new_licence_id",
        "new_derivation_event_id",
        "new_endorsement_event_id",
    ):

        assert name not in called


def test_no_governance_factory_is_called():

    called = _called_names(MODULE)

    for name in (
        "build_proposal",
        "mint_claim",
        "mint_licence_record",
        "record_derivation_event",
        "record_endorsement_event",
        "build_knowledge_candidate",
        "mint_licence_record",
    ):

        assert name not in called


def test_import_direction_is_preserved():

    roots = _imported_roots(MODULE)

    # only the sanctioned governance ADAPTER package may be imported
    governance = sorted({r for r in roots if r.startswith("core.governance")})

    assert governance == ["core.governance.adapters"]

    # no client imports
    for forbidden in (
        "core.vision",
        "core.conversation",
        "core.knowledge",
        "core.architecture.reasoning",
        "core.prompt_intelligence",
        "core.bim",
        "core.structure",
    ):

        assert forbidden not in roots


def test_output_is_immutable_and_truth_free():

    result = to_claim_request_input("a bed exists", intent=_intent())

    with pytest.raises(FrozenInstanceError):

        result.proposal_fields = None

    assert ConversationRuntimeInput.CREATES_IDENTITY is False

    assert ConversationRuntimeInput.CREATES_OBJECTS is False

    assert ConversationRuntimeInput.TRANSFERS_CONFIDENCE is False

    assert ConversationRuntimeInput.DECIDES_TRUTH is False

    assert ConversationRuntimeInput.PERSISTS is False

    payload = result.to_dict()

    for field in ("truth", "confidence", "certainty", "approval", "probability"):

        assert field not in payload


def test_proposal_fields_are_read_only():

    result = to_claim_request_input("a bed exists", intent=_intent())

    with pytest.raises(TypeError):

        result.proposal_fields["proposed_content"] = "changed"


def test_the_adapter_does_not_persist():

    source = MODULE.read_text(encoding="utf-8")

    for token in ("open(", "json.dump", "pickle", "sqlite3", "shelve"):

        assert token not in source
