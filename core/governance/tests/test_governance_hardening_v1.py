"""Governance Hardening V1 — isolated self-checks.

Verifies the hardening contracts:
    1. the identity registry is immutable
    2. the reference prefixes have a single source of truth (no duplicated
       "clm_"/"lic_"/"dev_"/"eev_" literals outside identity_v1)
    3. the licence-reference validation boundary checks shape/existence only,
       and creates no LicenceRecord and mutates no Claim
    4. the admission boundary and the minting boundary both use that boundary
    5. the event factories reject an empty input set and a missing ordering
    6. the hardening module imports no client subsystem
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance import identity_v1
from core.governance.admission import knowledge_admission_service
from core.governance.events import (
    EventError,
    record_derivation_event,
    record_endorsement_event,
)
from core.governance.identity_v1 import (
    CLAIM_REFERENCE_PREFIX,
    DERIVATION_EVENT_PREFIX,
    ENDORSEMENT_EVENT_PREFIX,
    GOVERNANCE_ID_PREFIXES,
    LICENCE_REFERENCE_PREFIX,
    LINEAGE_REFERENCE_PREFIXES,
    is_claim_reference,
    is_event_reference,
    is_governance_id,
    is_licence_reference,
    is_lineage_reference,
)
from core.governance.intake import proposal_intake_service
from core.governance.licence import (
    RULE_CODES as LICENCE_RULE_CODES,
    LicenceReferenceValidation,
    LicenceReferenceValidationError,
    validate_licence_reference,
)
from core.governance.lineage import lineage_reference_v1 as lineage_ref
from core.governance.minting import claim_minting_service
from core.governance.proposal import build_proposal


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

HARDENING_MODULE = GOVERNANCE_DIR / "licence" / "licence_reference_validation_v1.py"

DUPLICATED_PREFIX_LITERALS = (
    CLAIM_REFERENCE_PREFIX,
    LICENCE_REFERENCE_PREFIX,
    DERIVATION_EVENT_PREFIX,
    ENDORSEMENT_EVENT_PREFIX,
)


def _string_literals(path):

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


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


def _proposal_and_receipt():

    proposal = build_proposal(
        proposed_content="a bed exists",
        proposed_claim_type="existence",
        trigger_references=("obs_bed_1",),
    )

    return proposal, proposal_intake_service.submit_proposal(proposal)


# ----------------------------------------------------------
# 1. the identity registry is immutable
# ----------------------------------------------------------

def test_identity_registry_is_a_read_only_mapping():

    assert isinstance(identity_v1._ID_KINDS, MappingProxyType)


def test_identity_registry_rejects_mutation():

    with pytest.raises(TypeError):

        identity_v1._ID_KINDS["claim"] = "xxx_"

    with pytest.raises(TypeError):

        del identity_v1._ID_KINDS["licence"]


def test_identity_registry_content_is_unchanged():

    assert dict(identity_v1._ID_KINDS) == {
        "claim": CLAIM_REFERENCE_PREFIX,
        "licence": LICENCE_REFERENCE_PREFIX,
        "derivation_event": DERIVATION_EVENT_PREFIX,
        "endorsement_event": ENDORSEMENT_EVENT_PREFIX,
    }


# ----------------------------------------------------------
# 2. the prefixes have a single source of truth
# ----------------------------------------------------------

def test_no_module_duplicates_a_governance_prefix_literal():

    offenders = []

    for path in sorted(GOVERNANCE_DIR.rglob("*.py")):

        parts = path.parts

        if "tests" in parts or path.name == "identity_v1.py":

            continue

        for literal in _string_literals(path):

            if literal in DUPLICATED_PREFIX_LITERALS:

                offenders.append((str(path), literal))

    assert offenders == [], "a governance prefix literal was duplicated: %r" % (
        offenders,
    )


def test_lineage_reexports_the_canonical_prefixes():

    assert lineage_ref.CLAIM_REFERENCE_PREFIX is CLAIM_REFERENCE_PREFIX

    assert lineage_ref.DERIVATION_EVENT_PREFIX is DERIVATION_EVENT_PREFIX

    assert lineage_ref.ENDORSEMENT_EVENT_PREFIX is ENDORSEMENT_EVENT_PREFIX

    assert lineage_ref.is_claim_reference is is_claim_reference


def test_prefix_sets_are_consistent():

    assert GOVERNANCE_ID_PREFIXES == (
        CLAIM_REFERENCE_PREFIX,
        LICENCE_REFERENCE_PREFIX,
        DERIVATION_EVENT_PREFIX,
        ENDORSEMENT_EVENT_PREFIX,
    )

    # A licence is NOT a lineage node.
    assert LICENCE_REFERENCE_PREFIX not in LINEAGE_REFERENCE_PREFIXES


# ----------------------------------------------------------
# 3. shape predicates
# ----------------------------------------------------------

def test_shape_predicates():

    assert is_claim_reference("clm_abc") is True

    assert is_claim_reference("lic_abc") is False

    assert is_licence_reference("lic_abc") is True

    assert is_licence_reference("clm_abc") is False

    assert is_event_reference("dev_abc") is True

    assert is_event_reference("eev_abc") is True

    assert is_event_reference("clm_abc") is False

    assert is_governance_id("lic_abc") is True

    assert is_governance_id("au2_claim_001") is False

    assert is_lineage_reference("clm_abc") is True

    assert is_lineage_reference("lic_abc") is False


# ----------------------------------------------------------
# 4. the licence-reference validation boundary
# ----------------------------------------------------------

def test_licence_validation_accepts_a_well_formed_reference():

    result = validate_licence_reference("lic_abc123")

    assert result.valid is True

    assert result.licence_reference == "lic_abc123"

    assert result.rule_code == "allowed"


def test_licence_validation_rejects_a_missing_reference():

    for value in (None, "", "   "):

        result = validate_licence_reference(value)

        assert result.valid is False

        assert result.rule_code == "missing_licence_reference"


def test_licence_validation_rejects_a_malformed_reference():

    for value in ("unlicensed_hypothesis", "clm_abc", "abc"):

        result = validate_licence_reference(value)

        assert result.valid is False

        assert result.rule_code == "invalid_licence_reference"


def test_licence_validation_checks_existence_only_when_a_set_is_supplied():

    assert validate_licence_reference("lic_abc").valid is True

    unresolved = validate_licence_reference(
        "lic_abc", known_licence_references=["lic_other"]
    )

    assert unresolved.valid is False

    assert unresolved.rule_code == "unresolved_licence_reference"

    resolved = validate_licence_reference(
        "lic_abc", known_licence_references=["lic_abc"]
    )

    assert resolved.valid is True


def test_licence_validation_result_is_immutable_and_truth_free():

    result = validate_licence_reference("lic_abc")

    with pytest.raises(FrozenInstanceError):

        result.valid = False

    assert LicenceReferenceValidation.CREATES_LICENCE is False

    assert LicenceReferenceValidation.MUTATES_CLAIM is False

    assert LicenceReferenceValidation.ASSIGNS_TRUTH is False

    payload = result.to_dict()

    for forbidden in ("truth", "confidence", "certainty", "approval"):

        assert forbidden not in payload


def test_licence_validation_rejects_an_unknown_rule_code():

    with pytest.raises(LicenceReferenceValidationError):

        LicenceReferenceValidation(
            valid=True,
            licence_reference="lic_abc",
            reason="x",
            rule_code="made_up",
        )


def test_licence_validation_rule_codes_are_closed():

    assert LICENCE_RULE_CODES == (
        "allowed",
        "missing_licence_reference",
        "invalid_licence_reference",
        "unresolved_licence_reference",
    )


def test_licence_validation_never_creates_a_licence_or_a_claim():

    forbidden_calls = (
        "mint_licence_record",
        "LicenceRecord",
        "mint_claim",
        "Claim",
        "record_derivation_event",
        "record_endorsement_event",
    )

    called = _called_names(HARDENING_MODULE)

    offenders = [name for name in called if name in forbidden_calls]

    assert offenders == [], "the licence boundary called a factory: %r" % (
        offenders,
    )


def test_licence_validation_has_no_client_imports():

    offenders = []

    for root in _imported_roots(HARDENING_MODULE):

        for forbidden in FORBIDDEN_IMPORT_ROOTS:

            if root == forbidden or root.startswith(forbidden + "."):

                offenders.append(root)

    assert offenders == [], "the licence boundary imported a client: %r" % (
        offenders,
    )


def test_licence_validation_declares_no_prefix_literal():

    literals = _string_literals(HARDENING_MODULE)

    assert LICENCE_REFERENCE_PREFIX not in literals


# ----------------------------------------------------------
# 5. the admission boundary uses the canonical validator
# ----------------------------------------------------------

def test_admission_uses_the_canonical_licence_rule_codes():

    unresolved = knowledge_admission_service.admit(
        {"source_claim_reference": "clm_abc", "licence_reference": "lic_x"},
        known_licence_references=["lic_other"],
    )

    assert unresolved.admitted is False

    assert unresolved.reason.startswith("unresolved_licence_reference")

    malformed = knowledge_admission_service.admit(
        {"source_claim_reference": "clm_abc", "licence_reference": "garbage"}
    )

    assert malformed.admitted is False

    assert malformed.reason.startswith("invalid_licence_reference")


def test_admission_module_no_longer_declares_a_licence_prefix():

    admission_module = (
        GOVERNANCE_DIR / "admission" / "knowledge_admission_service_v1.py"
    )

    assert LICENCE_REFERENCE_PREFIX not in _string_literals(admission_module)


# ----------------------------------------------------------
# 6. the minting boundary shape-checks a supplied licence reference
# ----------------------------------------------------------

def test_minting_rejects_a_malformed_licence_reference():

    proposal, receipt = _proposal_and_receipt()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal,
        receipt,
        source_type="observation_evidence",
        origin="provider_payload",
        licence_reference="not_a_licence",
    )

    assert result.created is False


def test_minting_accepts_a_well_formed_licence_reference():

    proposal, receipt = _proposal_and_receipt()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal,
        receipt,
        source_type="observation_evidence",
        origin="provider_payload",
        licence_reference="lic_abc123",
    )

    assert result.created is True

    assert result.claim.licence_reference == "lic_abc123"


def test_minting_still_accepts_no_licence_reference():

    proposal, receipt = _proposal_and_receipt()

    result = claim_minting_service.mint_claim_from_proposal(
        proposal,
        receipt,
        source_type="observation_evidence",
        origin="provider_payload",
    )

    assert result.created is True

    assert result.claim.licence_reference is None


def test_minting_probe_is_derived_from_the_canonical_prefix():

    import core.governance.minting.claim_minting_service_v1 as minting_module

    assert minting_module._CLAIM_SHAPE_PROBE.startswith(CLAIM_REFERENCE_PREFIX)

    assert CLAIM_REFERENCE_PREFIX not in _string_literals(
        GOVERNANCE_DIR / "minting" / "claim_minting_service_v1.py"
    )


# ----------------------------------------------------------
# 7. tightened event factory guards
# ----------------------------------------------------------

def test_derivation_event_rejects_an_empty_input_set():

    with pytest.raises(EventError):

        record_derivation_event(
            input_references=(),
            output_claim_reference="clm_abc",
            operation_type="mint_from_proposal",
        )


def test_derivation_event_still_accepts_a_non_empty_input_set():

    event = record_derivation_event(
        input_references=("obs_a",),
        output_claim_reference="clm_abc",
        operation_type="mint_from_proposal",
    )

    assert event.input_references == ("obs_a",)


def test_endorsement_event_rejects_a_missing_ordering():

    with pytest.raises(EventError):

        record_endorsement_event(
            actor="human:teacher",
            target_claim_reference="clm_abc",
            previous_licence="unlicensed_hypothesis",
            new_licence="human_endorsed_hypothesis",
            act_type="endorsement",
            scope="single_case",
            ordering=None,
        )


def test_endorsement_event_still_accepts_an_ordering():

    event = record_endorsement_event(
        actor="human:teacher",
        target_claim_reference="clm_abc",
        previous_licence="unlicensed_hypothesis",
        new_licence="human_endorsed_hypothesis",
        act_type="endorsement",
        scope="single_case",
        ordering=1,
    )

    assert event.ordering == 1
