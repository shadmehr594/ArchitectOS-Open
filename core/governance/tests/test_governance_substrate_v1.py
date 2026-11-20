"""Claim Governance substrate V1 — isolated boundary self-checks.

Verifies the invariants the substrate claims:
    1. claim identity cannot be supplied externally
    2. minted fields cannot mutate
    3. forbidden truth fields do not exist
    4. the licence vocabulary is closed and truth-free
    5. events carry their required fields and are immutable
    6. governance imports no client subsystem
    7. a vision-derived id is never accepted
    8. a proposal carries no authority
"""

from __future__ import annotations


import ast
from pathlib import Path

import pytest

from core.governance import (
    CLIENT_ADAPTERS_IMPLEMENTED,
    FORBIDDEN_IMPORT_ROOTS,
    PERSISTENCE_IMPLEMENTED,
    PIPELINE_WIRING_IMPLEMENTED,
    SUBSTRATE_IMPLEMENTED,
    TRANSITION_VALIDATOR_IMPLEMENTED,
)
from core.governance.claim import (
    CLAIM_TYPES,
    FORBIDDEN_CLAIM_FIELDS,
    IMMUTABLE_FIELDS,
    SCOPES,
    SOURCE_TYPES,
    Claim,
    ClaimIdentityError,
    ClaimImmutabilityError,
    ClaimVocabularyError,
    assert_no_forbidden_fields,
    mint_claim,
)
from core.governance.events import (
    ACT_TYPES,
    OPERATION_TYPES,
    DerivationEvent,
    EndorsementEvent,
    EventError,
    record_derivation_event,
    record_endorsement_event,
)
from core.governance.identity_v1 import (
    IdentityError,
    is_governance_id,
    new_claim_id,
    reject_vision_id,
)
from core.governance.licence import (
    FORBIDDEN_LICENCE_STATES,
    LICENCE_STATES,
    LicenceError,
    LicenceRecord,
    mint_licence_record,
)
from core.governance.proposal import (
    FORBIDDEN_PROPOSAL_FIELDS,
    InterpretationProposal,
    ProposalAuthorityError,
    build_proposal,
)


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]


# ----------------------------------------------------------
# 1. identity cannot be supplied externally
# ----------------------------------------------------------

def test_mint_claim_rejects_client_supplied_claim_id():

    with pytest.raises(IdentityError):

        mint_claim(
            content="a bed exists",
            origin="provider_payload",
            source_type="observation_evidence",
            claim_type="existence",
            original_scope="single_case",
            claim_id="clm_client_supplied",
        )


def test_claim_cannot_be_constructed_directly():

    with pytest.raises(ClaimIdentityError):

        Claim(
            claim_id="clm_forged",
            content="a bed exists",
            origin="provider_payload",
            source_type="observation_evidence",
            claim_type="existence",
            original_scope="single_case",
        )


def test_minted_claim_id_is_governance_minted():

    claim = mint_claim(
        content="a bed exists",
        origin="provider_payload",
        source_type="observation_evidence",
        claim_type="existence",
        original_scope="single_case",
    )

    assert is_governance_id(claim.claim_id)

    assert claim.claim_id.startswith("clm_")


# ----------------------------------------------------------
# 2. immutability
# ----------------------------------------------------------

def test_minted_claim_fields_cannot_mutate():

    claim = mint_claim(
        content="a bed exists",
        origin="provider_payload",
        source_type="observation_evidence",
        claim_type="existence",
        original_scope="single_case",
    )

    for field in IMMUTABLE_FIELDS:

        with pytest.raises(ClaimImmutabilityError):

            setattr(claim, field, "mutated")

    with pytest.raises(ClaimImmutabilityError):

        del claim.claim_id


def test_licence_record_is_immutable():

    record = mint_licence_record(
        target_claim_reference="clm_abc",
        licence_state="unlicensed_hypothesis",
    )

    with pytest.raises(LicenceError):

        record.licence_state = "candidate_for_learning"


def test_events_are_immutable():

    event = record_derivation_event(
        input_references=("obs_a", "obs_b"),
        output_claim_reference="clm_abc",
        operation_type="mint_from_proposal",
        licence_check_result="not_checked",
    )

    with pytest.raises(EventError):

        event.operation_type = "generalize"


# ----------------------------------------------------------
# 3. forbidden truth fields do not exist
# ----------------------------------------------------------

def test_forbidden_truth_fields_do_not_exist_on_claim():

    claim = mint_claim(
        content="a bed exists",
        origin="provider_payload",
        source_type="observation_evidence",
        claim_type="existence",
        original_scope="single_case",
    )

    payload = claim.to_dict()

    for field in FORBIDDEN_CLAIM_FIELDS:

        assert field not in payload

        assert not hasattr(claim, field)


def test_forbidden_truth_fields_are_refused_in_a_payload():

    for field in FORBIDDEN_CLAIM_FIELDS:

        with pytest.raises(ClaimVocabularyError):

            assert_no_forbidden_fields({field: 1.0})


def test_claim_vocabularies_are_closed():

    with pytest.raises(ClaimVocabularyError):

        mint_claim(
            content="x",
            origin="o",
            source_type="made_up_source",
            claim_type="existence",
            original_scope="single_case",
        )

    with pytest.raises(ClaimVocabularyError):

        mint_claim(
            content="x",
            origin="o",
            source_type="observation_evidence",
            claim_type="made_up_type",
            original_scope="single_case",
        )

    assert "existence" in CLAIM_TYPES

    assert "observation_evidence" in SOURCE_TYPES

    assert "single_case" in SCOPES


# ----------------------------------------------------------
# 4. licence vocabulary is closed and truth-free
# ----------------------------------------------------------

def test_licence_states_are_closed():

    with pytest.raises(LicenceError):

        mint_licence_record(
            target_claim_reference="clm_abc",
            licence_state="made_up_state",
        )


def test_licence_never_means_truth():

    for forbidden in ("fact", "truth", "probability", "confidence"):

        with pytest.raises(LicenceError):

            mint_licence_record(
                target_claim_reference="clm_abc",
                licence_state=forbidden,
            )

    assert not set(LICENCE_STATES) & set(FORBIDDEN_LICENCE_STATES)


# ----------------------------------------------------------
# 5. events carry required fields
# ----------------------------------------------------------

def test_derivation_event_required_fields():

    event = record_derivation_event(
        input_references=("obs_a",),
        output_claim_reference="clm_abc",
        operation_type="mint_from_proposal",
        licence_check_result="allowed",
    )

    assert is_governance_id(event.event_id)

    assert event.input_references == ("obs_a",)

    assert event.output_claim_reference == "clm_abc"

    assert event.operation_type in OPERATION_TYPES

    assert event.licence_check_result == "allowed"


def test_endorsement_event_required_fields():

    event = record_endorsement_event(
        actor="human:teacher",
        target_claim_reference="clm_abc",
        previous_licence="unlicensed_hypothesis",
        new_licence="human_endorsed_hypothesis",
        act_type="endorsement",
        scope="single_case",
        ordering=1,
    )

    assert is_governance_id(event.event_id)

    assert event.actor == "human:teacher"

    assert event.act_type in ACT_TYPES

    assert event.new_licence in LICENCE_STATES

    assert event.ordering == 1


def test_endorsement_may_not_grant_a_forbidden_licence():

    with pytest.raises(EventError):

        record_endorsement_event(
            actor="human:teacher",
            target_claim_reference="clm_abc",
            previous_licence="unlicensed_hypothesis",
            new_licence="truth",
            act_type="endorsement",
            scope="single_case",
            ordering=1,
        )


def test_event_id_cannot_be_supplied():

    with pytest.raises(IdentityError):

        record_endorsement_event(
            actor="human:teacher",
            target_claim_reference="clm_abc",
            previous_licence="unlicensed_hypothesis",
            new_licence="human_endorsed_hypothesis",
            act_type="endorsement",
            scope="single_case",
            ordering=1,
            event_id="eev_forged",
        )


# ----------------------------------------------------------
# 6. governance imports no client subsystem
# ----------------------------------------------------------

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


def test_governance_has_no_client_imports():

    offenders = []

    for path in sorted(GOVERNANCE_DIR.rglob("*.py")):

        for root in _imported_roots(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if root == forbidden or root.startswith(forbidden + "."):

                    offenders.append((str(path), root))

    assert offenders == [], "governance imported a client subsystem: %r" % (
        offenders,
    )


# ----------------------------------------------------------
# 7. vision-derived ids are never accepted
# ----------------------------------------------------------

def test_vision_id_is_rejected():

    with pytest.raises(IdentityError):

        reject_vision_id("au2_claim_001")

    claim = mint_claim(
        content="a bed exists",
        origin="provider_payload",
        source_type="observation_evidence",
        claim_type="existence",
        original_scope="single_case",
    )

    assert not claim.claim_id.startswith("au2_")


# ----------------------------------------------------------
# 8. proposal carries no authority
# ----------------------------------------------------------

def test_proposal_has_no_authority():

    proposal = build_proposal(
        proposed_content="this space may be a sleeping area",
        trigger_references=("sleeping_element",),
        basis=("observed",),
        language="en",
    )

    assert InterpretationProposal.AUTHORITY is False

    assert InterpretationProposal.CREATES_IDENTITY is False

    assert InterpretationProposal.CREATES_CLAIMS is False

    assert proposal.to_dict()["authority"] is False


def test_proposal_rejects_authority_fields():

    for field in ("claim_id", "licence", "scope", "truth_status", "knowledge_status"):

        assert field in FORBIDDEN_PROPOSAL_FIELDS

        with pytest.raises(ProposalAuthorityError):

            build_proposal(
                proposed_content="x",
                **{field: "forged"},
            )


# ----------------------------------------------------------
# 9. V1 scope flags are honest
# ----------------------------------------------------------

def test_v1_scope_flags():

    assert SUBSTRATE_IMPLEMENTED is True

    assert PERSISTENCE_IMPLEMENTED is False

    # implemented in later phases (LINEAGE_MODEL_V1, TRANSITION_VALIDATOR_V1,
    # ACT_CLASSIFIER_V1, ENDORSEMENT_WIRING_V1, CLIENT_ADAPTER_BOUNDARY_V1)
    assert TRANSITION_VALIDATOR_IMPLEMENTED is True

    assert CLIENT_ADAPTERS_IMPLEMENTED is True

    assert PIPELINE_WIRING_IMPLEMENTED is False
