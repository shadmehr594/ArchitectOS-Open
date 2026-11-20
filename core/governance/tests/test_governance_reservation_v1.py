"""Reserved Identity Mechanism V1 — isolated self-checks.

Verifies the reservation contracts:
    1. reserve -> consume succeeds; consume binds the reserved id
    2. double consume, released consume, unknown, forged, wrong-kind all rejected
    3. reservation + client-supplied id is rejected
    4. a fresh mint (no reservation) is unchanged
    5. identity_v1 is still the ONLY uuid4 / mint_id authority
    6. no duplicated clm_/lic_/dev_/eev_ literal outside identity_v1
    7. the reservation package imports no client subsystem
    8. the four mint factories consume a reservation
    9. R6 is resolved: a single-pass lifecycle reaches KnowledgeCandidate
   10. no truth / confidence / approval field is introduced
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.admission import (
    build_knowledge_candidate,
    knowledge_admission_service,
)
from core.governance.claim import mint_claim
from core.governance.events import (
    record_derivation_event,
    record_endorsement_event,
)
from core.governance.identity_v1 import IdentityError
from core.governance.identity.reservation_v1 import (
    KIND_CLAIM,
    KIND_DERIVATION_EVENT,
    KIND_ENDORSEMENT_EVENT,
    KIND_LICENCE,
    KINDS,
    REASON_CONSUMED,
    REASON_KIND_MISMATCH,
    REASON_RELEASED,
    REASON_UNKNOWN,
    STATE_CONSUMED,
    STATE_RELEASED,
    STATE_RESERVED,
    STATES,
    ReservationError,
    ReservationLedger,
    ReservedIdentity,
    consume_reservation,
    reservation_ledger,
    reserve_claim_id,
    reserve_derivation_event_id,
    reserve_endorsement_event_id,
    reserve_licence_id,
)
from core.governance.licence import mint_licence_record


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

IDENTITY_PREFIX_LITERALS = ("clm_", "lic_", "dev_", "eev_")

RESERVATION_DIR = GOVERNANCE_DIR / "identity"


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


def _fresh_claim(**overrides):

    fields = dict(
        content="a bed exists",
        origin="provider_payload",
        source_type="observation_evidence",
        claim_type="existence",
        original_scope="single_case",
    )

    fields.update(overrides)

    return mint_claim(**fields)


# ----------------------------------------------------------
# 1. reserve -> consume success
# ----------------------------------------------------------

def test_reserve_then_consume_succeeds():

    ledger = ReservationLedger()

    reservation = ledger.reserve(KIND_CLAIM)

    assert reservation.state == STATE_RESERVED

    assert ledger.is_reserved(reservation.identity) is True

    identity = ledger.consume(reservation, KIND_CLAIM)

    assert identity == reservation.identity

    assert ledger.is_consumed(reservation.identity) is True


def test_reserve_api_returns_a_reserved_handle():

    for reserve, kind in (
        (reserve_claim_id, KIND_CLAIM),
        (reserve_licence_id, KIND_LICENCE),
        (reserve_derivation_event_id, KIND_DERIVATION_EVENT),
        (reserve_endorsement_event_id, KIND_ENDORSEMENT_EVENT),
    ):

        reservation = reserve()

        assert isinstance(reservation, ReservedIdentity)

        assert reservation.kind == kind

        assert reservation.state == STATE_RESERVED


def test_reserved_identity_is_immutable():

    reservation = reserve_claim_id()

    with pytest.raises(FrozenInstanceError):

        reservation.state = STATE_CONSUMED

    assert ReservedIdentity.CREATES_IDENTITY is False

    assert ReservedIdentity.BINDS_OBJECT is False


def test_reserved_identity_refuses_an_unknown_kind():

    with pytest.raises(ReservationError):

        ReservedIdentity(identity="clm_x", kind="made_up")


# ----------------------------------------------------------
# 2. rejection cases
# ----------------------------------------------------------

def test_double_consume_is_rejected():

    ledger = ReservationLedger()

    reservation = ledger.reserve(KIND_CLAIM)

    ledger.consume(reservation, KIND_CLAIM)

    with pytest.raises(ReservationError) as error:

        ledger.consume(reservation, KIND_CLAIM)

    assert REASON_CONSUMED in str(error.value)


def test_released_consume_is_rejected():

    ledger = ReservationLedger()

    reservation = ledger.reserve(KIND_CLAIM)

    released = ledger.release(reservation)

    assert released.state == STATE_RELEASED

    assert ledger.is_released(reservation.identity) is True

    with pytest.raises(ReservationError) as error:

        ledger.consume(reservation, KIND_CLAIM)

    assert REASON_RELEASED in str(error.value)


def test_unknown_reservation_is_rejected():

    ledger = ReservationLedger()

    with pytest.raises(ReservationError) as error:

        ledger.consume(
            ReservedIdentity(identity="clm_never_reserved", kind=KIND_CLAIM),
            KIND_CLAIM,
        )

    assert REASON_UNKNOWN in str(error.value)


def test_forged_handle_is_rejected():

    # A handle whose id was never reserved cannot be consumed, even with the
    # correct kind — membership in the ledger is the authority.
    with pytest.raises(ReservationError) as error:

        reservation_ledger.consume(
            ReservedIdentity(identity="clm_forged_handle", kind=KIND_CLAIM),
            KIND_CLAIM,
        )

    assert REASON_UNKNOWN in str(error.value)


def test_wrong_kind_is_rejected():

    ledger = ReservationLedger()

    reservation = ledger.reserve(KIND_CLAIM)

    with pytest.raises(ReservationError) as error:

        ledger.consume(reservation, KIND_LICENCE)

    assert REASON_KIND_MISMATCH in str(error.value)


def test_non_handle_is_rejected():

    ledger = ReservationLedger()

    with pytest.raises(ReservationError):

        ledger.consume("clm_x", KIND_CLAIM)


def test_release_twice_is_rejected():

    ledger = ReservationLedger()

    reservation = ledger.reserve(KIND_CLAIM)

    ledger.release(reservation)

    with pytest.raises(ReservationError) as error:

        ledger.release(reservation)

    assert REASON_RELEASED in str(error.value)


def test_reserve_with_unknown_kind_is_rejected():

    ledger = ReservationLedger()

    with pytest.raises(ReservationError):

        ledger.reserve("made_up_kind")


def test_reservation_and_client_id_together_are_rejected():

    reservation = reserve_claim_id()

    with pytest.raises(IdentityError):

        mint_claim(
            content="x",
            origin="o",
            source_type="observation_evidence",
            claim_type="existence",
            original_scope="single_case",
            claim_id="clm_client",
            reservation=reservation,
        )

    licence_reservation = reserve_licence_id()

    with pytest.raises(IdentityError):

        mint_licence_record(
            target_claim_reference="clm_x",
            licence_state="unlicensed_hypothesis",
            licence_id="lic_client",
            reservation=licence_reservation,
        )

    event_reservation = reserve_derivation_event_id()

    with pytest.raises(IdentityError):

        record_derivation_event(
            input_references=("obs",),
            output_claim_reference="clm_x",
            operation_type="mint_from_proposal",
            event_id="dev_client",
            reservation=event_reservation,
        )


def test_client_id_rejection_is_preserved():

    with pytest.raises(IdentityError):

        mint_claim(
            content="x",
            origin="o",
            source_type="observation_evidence",
            claim_type="existence",
            original_scope="single_case",
            claim_id="clm_client",
        )

    with pytest.raises(IdentityError):

        mint_licence_record(
            target_claim_reference="clm_x",
            licence_state="unlicensed_hypothesis",
            licence_id="lic_client",
        )

    with pytest.raises(IdentityError):

        record_derivation_event(
            input_references=("obs",),
            output_claim_reference="clm_x",
            operation_type="mint_from_proposal",
            event_id="dev_client",
        )


# ----------------------------------------------------------
# 3. fresh mint without a reservation is unchanged
# ----------------------------------------------------------

def test_fresh_mint_without_a_reservation_is_unchanged():

    claim = _fresh_claim()

    assert claim.claim_id.startswith("clm_")

    record = mint_licence_record(
        target_claim_reference=claim.claim_id,
        licence_state="unlicensed_hypothesis",
    )

    assert record.licence_id.startswith("lic_")

    event = record_derivation_event(
        input_references=("obs",),
        output_claim_reference=claim.claim_id,
        operation_type="mint_from_proposal",
    )

    assert event.event_id.startswith("dev_")

    endorsement = record_endorsement_event(
        actor="human:teacher",
        target_claim_reference=claim.claim_id,
        previous_licence=None,
        new_licence="human_endorsed_hypothesis",
        act_type="endorsement",
        scope="single_case",
        ordering=1,
    )

    assert endorsement.event_id.startswith("eev_")


# ----------------------------------------------------------
# 4. the mint factories consume a reservation
# ----------------------------------------------------------

def test_mint_claim_consumes_a_reservation():

    reservation = reserve_claim_id()

    claim = _fresh_claim(reservation=reservation)

    assert claim.claim_id == reservation.identity

    assert reservation_ledger.is_consumed(reservation.identity) is True


def test_mint_licence_record_consumes_a_reservation():

    reservation = reserve_licence_id()

    record = mint_licence_record(
        target_claim_reference="clm_x",
        licence_state="unlicensed_hypothesis",
        reservation=reservation,
    )

    assert record.licence_id == reservation.identity

    assert reservation_ledger.is_consumed(reservation.identity) is True


def test_record_derivation_event_consumes_a_reservation():

    reservation = reserve_derivation_event_id()

    event = record_derivation_event(
        input_references=("obs",),
        output_claim_reference="clm_x",
        operation_type="mint_from_proposal",
        reservation=reservation,
    )

    assert event.event_id == reservation.identity


def test_record_endorsement_event_consumes_a_reservation():

    reservation = reserve_endorsement_event_id()

    event = record_endorsement_event(
        actor="human:teacher",
        target_claim_reference="clm_x",
        previous_licence=None,
        new_licence="human_endorsed_hypothesis",
        act_type="endorsement",
        scope="single_case",
        ordering=1,
        reservation=reservation,
    )

    assert event.event_id == reservation.identity


def test_consume_reservation_helper_uses_the_shared_ledger():

    reservation = reserve_claim_id()

    assert consume_reservation(reservation, KIND_CLAIM) == reservation.identity


# ----------------------------------------------------------
# 5. R6 is resolved — single-pass lifecycle
# ----------------------------------------------------------

def test_r6_single_pass_lifecycle_reaches_a_candidate():

    # 1. reserve the claim id BEFORE the claim exists
    reserved = reserve_claim_id()

    # 2. a licence targets the reserved id
    licence = mint_licence_record(
        target_claim_reference=reserved.identity,
        licence_state="candidate_for_learning",
    )

    # 3. the claim is minted consuming the reservation AND carrying the licence
    claim = _fresh_claim(
        licence_reference=licence.licence_id,
        reservation=reserved,
    )

    assert claim.claim_id == reserved.identity

    assert claim.licence_reference == licence.licence_id

    # 4. admission now matches, with NO bridge and NO duplicate claim
    candidate = build_knowledge_candidate(
        source_claim_reference=claim.claim_id,
        licence_reference=licence.licence_id,
        scope="single_case",
    )

    result = knowledge_admission_service.admit(
        candidate,
        claim=claim,
        known_claim_references=[claim.claim_id],
        known_licence_references=[licence.licence_id],
    )

    assert result.admitted is True

    assert result.candidate_reference.startswith("kcd_")


# ----------------------------------------------------------
# 6. hardening contracts preserved
# ----------------------------------------------------------

def test_uuid_and_mint_id_live_only_in_identity_v1():

    offenders = []

    for path in sorted(GOVERNANCE_DIR.rglob("*.py")):

        if "tests" in path.parts:

            continue

        for name in _called_names(path):

            if name in ("uuid4", "uuid1", "mint_id"):

                if path.name != "identity_v1.py":

                    offenders.append((path.relative_to(GOVERNANCE_DIR).as_posix(), name))

    assert offenders == [], "id generation leaked outside identity_v1: %r" % (
        offenders,
    )


def test_reservation_module_does_not_generate_ids_itself():

    called = _called_names(RESERVATION_DIR / "reservation_v1.py")

    assert "uuid4" not in called

    assert "mint_id" not in called


def test_no_duplicated_identity_prefix_literal():

    offenders = []

    for path in sorted(GOVERNANCE_DIR.rglob("*.py")):

        if "tests" in path.parts or path.name == "identity_v1.py":

            continue

        for literal in _string_literals(path):

            if literal in IDENTITY_PREFIX_LITERALS:

                offenders.append((path.relative_to(GOVERNANCE_DIR).as_posix(), literal))

    assert offenders == [], "an identity prefix literal was duplicated: %r" % (
        offenders,
    )


def test_reservation_package_has_no_client_imports():

    offenders = []

    for path in sorted(RESERVATION_DIR.rglob("*.py")):

        for root in _imported_roots(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if root == forbidden or root.startswith(forbidden + "."):

                    offenders.append((path.name, root))

    assert offenders == [], "the reservation package imported a client: %r" % (
        offenders,
    )


def test_reservation_imports_identity_v1_only():

    allowed = ("core.governance", "core.governance.identity_v1")

    offenders = []

    for path in sorted(RESERVATION_DIR.rglob("*.py")):

        for root in _imported_roots(path):

            if not root.startswith("core."):

                continue

            if not any(root == area or root.startswith(area + ".") for area in allowed):

                offenders.append((path.name, root))

    assert offenders == [], "the reservation package imported outside identity: %r" % (
        offenders,
    )


def test_no_truth_field_is_introduced():

    reservation = reserve_claim_id()

    payload = reservation.to_dict()

    for field in ("truth", "confidence", "certainty", "approval", "probability"):

        assert field not in payload


def test_kinds_and_states_are_closed():

    assert KINDS == (
        "claim",
        "licence",
        "derivation_event",
        "endorsement_event",
    )

    assert STATES == ("reserved", "consumed", "released")
