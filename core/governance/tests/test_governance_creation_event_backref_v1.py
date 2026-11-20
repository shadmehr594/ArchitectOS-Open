"""Claim <-> Creation Event back-reference (G2) — isolated self-checks.

Verifies that `claim.creation_event` is REACHABLE through the governance
reservation mechanism, without breaking governance ownership:

    1. a reserved derivation-event id can be bound to a claim AND its event
    2. claim.creation_event == the event id, and the event's output is the claim
    3. the reserved id is consumed exactly once
    4. forged / wrong-kind / consumed reservations and client event ids rejected
    5. the default (no reservation) path is unchanged
    6. identity_v1 is still the only id authority; no duplicated prefix literal;
       the minting service imports no client subsystem
"""

from __future__ import annotations


import ast
from pathlib import Path

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.claim import mint_claim
from core.governance.events import record_derivation_event
from core.governance.identity import reservation_v1
from core.governance.identity.reservation_v1 import (
    KIND_DERIVATION_EVENT,
    ReservationError,
    ReservedIdentity,
    reservation_ledger,
    reserve_claim_id,
    reserve_derivation_event_id,
)
from core.governance.intake import proposal_intake_service
from core.governance.lineage import LineageView
from core.governance.minting import claim_minting_service
from core.governance.minting.claim_minting_service_v1 import (
    CLAIM_CREATION_EVENT_BACKREFERENCE_DEFERRED,
)
from core.governance.proposal import build_proposal


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

MINTING_SERVICE = (
    GOVERNANCE_DIR / "minting" / "claim_minting_service_v1.py"
)

IDENTITY_PREFIX_LITERALS = ("clm_", "lic_", "dev_", "eev_")


def _proposal_and_receipt():

    proposal = build_proposal(
        proposed_content="a bed exists",
        proposed_claim_type="existence",
        trigger_references=("obs_bed_1",),
    )

    return proposal, proposal_intake_service.submit_proposal(proposal)


def _mint(**overrides):

    proposal, receipt = _proposal_and_receipt()

    fields = dict(
        source_type="observation_evidence",
        origin="provider_payload",
    )

    fields.update(overrides)

    return claim_minting_service.mint_claim_from_proposal(
        proposal, receipt, **fields
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


def _string_literals(path):

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


# ----------------------------------------------------------
# 1. the low-level flow
# ----------------------------------------------------------

def test_reserved_event_id_binds_claim_and_event():

    reserved = reserve_derivation_event_id()

    claim = mint_claim(
        content="a bed exists",
        origin="provider_payload",
        source_type="observation_evidence",
        claim_type="existence",
        original_scope="single_case",
        creation_event=reserved.identity,
    )

    event = record_derivation_event(
        input_references=("obs_bed_1",),
        output_claim_reference=claim.claim_id,
        operation_type="mint_from_proposal",
        reservation=reserved,
    )

    assert claim.creation_event == reserved.identity

    assert event.event_id == reserved.identity

    assert event.output_claim_reference == claim.claim_id

    assert reservation_ledger.is_consumed(reserved.identity) is True


# ----------------------------------------------------------
# 2. the minting service populates claim.creation_event
# ----------------------------------------------------------

def test_minting_service_populates_creation_event():

    reserved = reserve_derivation_event_id()

    result = _mint(creation_event_reservation=reserved)

    assert result.created is True

    assert result.claim.creation_event == reserved.identity

    assert result.creation_event_reference == reserved.identity

    assert reservation_ledger.is_consumed(reserved.identity) is True


def test_minting_service_event_output_matches_the_claim():

    # The service does not return the event object, so the output linkage is
    # proven through the low-level flow, where the event is in hand.
    reserved = reserve_derivation_event_id()

    claim = mint_claim(
        content="a bed exists",
        origin="provider_payload",
        source_type="observation_evidence",
        claim_type="existence",
        original_scope="single_case",
        creation_event=reserved.identity,
    )

    event = record_derivation_event(
        input_references=("obs_bed_1",),
        output_claim_reference=claim.claim_id,
        operation_type="mint_from_proposal",
        reservation=reserved,
    )

    view = LineageView(claims=[claim], derivation_events=[event])

    events = view.derivation_events(claim.claim_id)

    assert len(events) == 1

    assert events[0].output_claim_reference == claim.claim_id

    assert events[0].event_id == claim.creation_event

    assert view.what_created(claim.claim_id)["creation_event"] == reserved.identity


# ----------------------------------------------------------
# 3. the default path is unchanged
# ----------------------------------------------------------

def test_minting_service_without_reservation_leaves_creation_event_none():

    result = _mint()

    assert result.created is True

    assert result.claim.creation_event is None

    assert result.creation_event_reference.startswith("dev_")


# ----------------------------------------------------------
# 4. rejections
# ----------------------------------------------------------

def test_minting_service_rejects_a_forged_event_reservation():

    forged = ReservedIdentity(identity="dev_forged", kind=KIND_DERIVATION_EVENT)

    result = _mint(creation_event_reservation=forged)

    assert result.created is False

    assert "not reserved" in result.reason


def test_minting_service_rejects_a_wrong_kind_reservation():

    claim_reservation = reserve_claim_id()

    result = _mint(creation_event_reservation=claim_reservation)

    assert result.created is False

    assert "wrong kind" in result.reason


def test_minting_service_rejects_a_consumed_event_reservation():

    reserved = reserve_derivation_event_id()

    # consume it first through a legitimate event
    record_derivation_event(
        input_references=("obs_bed_1",),
        output_claim_reference="clm_x",
        operation_type="mint_from_proposal",
        reservation=reserved,
    )

    result = _mint(creation_event_reservation=reserved)

    assert result.created is False

    assert "not reserved" in result.reason


def test_minting_service_rejects_a_client_supplied_event_id():

    result = _mint(creation_event_reservation="dev_client_supplied")

    assert result.created is False

    assert "not a ReservedIdentity" in result.reason


def test_released_reservation_cannot_be_consumed():

    reserved = reserve_derivation_event_id()

    reservation_ledger.release(reserved)

    with pytest.raises(ReservationError):

        reservation_ledger.consume(reserved, KIND_DERIVATION_EVENT)


# ----------------------------------------------------------
# 5. ownership / hardening preserved
# ----------------------------------------------------------

def test_identity_v1_is_still_the_only_id_authority():

    offenders = []

    for path in sorted(GOVERNANCE_DIR.rglob("*.py")):

        if "tests" in path.parts or path.name == "identity_v1.py":

            continue

        for name in _called_names(path):

            if name in ("uuid4", "uuid1", "mint_id"):

                offenders.append((path.name, name))

    assert offenders == []


def test_no_duplicated_identity_prefix_literal():

    offenders = []

    for path in sorted(GOVERNANCE_DIR.rglob("*.py")):

        if "tests" in path.parts or path.name == "identity_v1.py":

            continue

        for literal in _string_literals(path):

            if literal in IDENTITY_PREFIX_LITERALS:

                offenders.append((path.name, literal))

    assert offenders == []


def test_minting_service_imports_no_client_subsystem():

    offenders = []

    for root in _imported_roots(MINTING_SERVICE):

        for forbidden in FORBIDDEN_IMPORT_ROOTS:

            if root == forbidden or root.startswith(forbidden + "."):

                offenders.append(root)

    assert offenders == []


def test_backreference_flag_is_no_longer_deferred():

    assert CLAIM_CREATION_EVENT_BACKREFERENCE_DEFERRED is False


def test_minting_service_uses_the_governance_reservation_kind():

    called = _called_names(MINTING_SERVICE)

    # the service must not mint ids itself
    assert "uuid4" not in called

    assert "mint_id" not in called

    # and must reference the derivation-event kind, never a raw prefix
    assert KIND_DERIVATION_EVENT == reservation_v1.KIND_DERIVATION_EVENT
