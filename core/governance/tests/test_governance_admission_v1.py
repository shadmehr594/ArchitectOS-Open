"""Knowledge Admission boundary V1 — isolated boundary self-checks.

Verifies the invariants the boundary claims:
    1. the result is immutable and carries exactly three fields
    2. the result can never carry truth / approval / certainty / scope / licence
    3. the service is stateless
    4. the service refuses a non-candidate input and forbidden authority fields
    5. the service validates the claim reference, licence reference and lineage
    6. the service delegates eligibility to the TransitionValidator
    7. the service never creates a Claim, a LicenceRecord or an event
    8. the service imports no client subsystem
    9. no sibling governance module imports admission (no reverse dependency)
   10. an unsettled rule yields an explicit NOT_IMPLEMENTED boundary result
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.admission import (
    KnowledgeAdmissionResult,
    KnowledgeAdmissionResultError,
    KnowledgeCandidate,
    build_knowledge_admission_result,
    build_knowledge_candidate,
    knowledge_admission_service,
)
from core.governance.admission.knowledge_admission_result_v1 import (
    ALLOWED_RESULT_FIELDS,
    FORBIDDEN_RESULT_FIELDS,
    NOT_IMPLEMENTED_REASON_PREFIX,
    not_implemented_admission_result,
)
from core.governance.claim import mint_claim
from core.governance.validation import TransitionResult


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

ADMISSION_DIR = GOVERNANCE_DIR / "admission"

SERVICE_PATH = ADMISSION_DIR / "knowledge_admission_service_v1.py"


# ----------------------------------------------------------
# helpers
# ----------------------------------------------------------

def _claim(*, scope="single_case", licence_reference="lic_abc123", lineage=()):

    return mint_claim(
        content="a bed exists",
        origin="provider_payload",
        source_type="observation_evidence",
        claim_type="existence",
        original_scope=scope,
        lineage_reference=lineage,
        licence_reference=licence_reference,
    )


def _input(claim_id, *, licence="lic_abc123", scope="single_case", lineage=()):

    return {
        "source_claim_reference": claim_id,
        "licence_reference": licence,
        "scope": scope,
        "lineage_reference": list(lineage),
    }


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


# ----------------------------------------------------------
# 1. result is immutable with exactly three fields
# ----------------------------------------------------------

def test_result_allowed_fields_are_exactly_three():

    assert ALLOWED_RESULT_FIELDS == (
        "admitted",
        "candidate_reference",
        "reason",
    )


def test_result_is_immutable():

    result = build_knowledge_admission_result(
        admitted=True,
        candidate_reference="kcd_x",
        reason="ok",
    )

    with pytest.raises(FrozenInstanceError):

        result.admitted = False


def test_result_carries_no_authority_flags():

    result = build_knowledge_admission_result(
        admitted=True,
        candidate_reference="kcd_x",
        reason="ok",
    )

    assert KnowledgeAdmissionResult.CREATES_TRUTH is False

    assert KnowledgeAdmissionResult.APPROVES_FACT is False

    assert KnowledgeAdmissionResult.ESCALATES_SCOPE is False

    assert KnowledgeAdmissionResult.CREATES_LICENCE is False

    assert KnowledgeAdmissionResult.MUTATES_CLAIM is False


def test_result_to_dict_never_exposes_a_forbidden_field():

    payload = build_knowledge_admission_result(
        admitted=True,
        candidate_reference="kcd_x",
        reason="ok",
    ).to_dict()

    for field in FORBIDDEN_RESULT_FIELDS:

        assert field not in payload


# ----------------------------------------------------------
# 2. the result refuses authority-bearing fields
# ----------------------------------------------------------

def test_result_refuses_forbidden_fields():

    for field in (
        "truth",
        "truth_status",
        "verified_truth",
        "certainty",
        "probability",
        "confidence",
        "confidence_as_truth",
        "approval",
        "approved",
        "scope",
        "scope_escalation",
        "licence",
        "licence_reference",
        "licence_id",
        "created_licence",
    ):

        assert field in FORBIDDEN_RESULT_FIELDS

        with pytest.raises(KnowledgeAdmissionResultError):

            build_knowledge_admission_result(
                admitted=True,
                candidate_reference="kcd_x",
                reason="ok",
                **{field: "forged"},
            )


def test_result_refuses_unknown_field():

    with pytest.raises(KnowledgeAdmissionResultError):

        build_knowledge_admission_result(
            admitted=True,
            candidate_reference="kcd_x",
            reason="ok",
            made_up_field=1,
        )


def test_not_implemented_result_is_explicit_and_negative():

    result = not_implemented_admission_result("some rule")

    assert result.admitted is False

    assert result.candidate_reference is None

    assert result.reason.startswith(NOT_IMPLEMENTED_REASON_PREFIX)


# ----------------------------------------------------------
# 3. the service is stateless
# ----------------------------------------------------------

def test_service_is_stateless():

    assert type(knowledge_admission_service).__slots__ == ()


def test_service_holds_no_state_between_calls():

    claim = _claim()

    first = knowledge_admission_service.admit(
        _input(claim.claim_id),
        claim=claim,
        known_claim_references=[claim.claim_id],
    )

    second = knowledge_admission_service.admit(
        _input(claim.claim_id),
        claim=claim,
        known_claim_references=[claim.claim_id],
    )

    assert first == second


# ----------------------------------------------------------
# 4. input type and forbidden authority fields
# ----------------------------------------------------------

def test_admit_rejects_non_candidate_input():

    result = knowledge_admission_service.admit("not a candidate")

    assert result.admitted is False

    assert result.reason.startswith("candidate_not_typed")


def test_admit_rejects_a_forbidden_authority_field():

    for field in ("truth", "confidence", "certainty", "approval"):

        payload = _input("clm_abc")

        payload[field] = "forged"

        result = knowledge_admission_service.admit(payload)

        assert result.admitted is False

        assert result.reason.startswith("forbidden_authority_field")


def test_admit_rejects_a_client_supplied_candidate_reference():

    payload = _input("clm_abc")

    payload["candidate_reference"] = "kcd_forged"

    result = knowledge_admission_service.admit(payload)

    assert result.admitted is False

    assert result.reason.startswith("forbidden_authority_field")


def test_admit_rejects_an_unknown_input_field():

    payload = _input("clm_abc")

    payload["made_up_field"] = 1

    result = knowledge_admission_service.admit(payload)

    assert result.admitted is False

    assert result.reason.startswith("unknown_input_field")


# ----------------------------------------------------------
# 5. claim / licence / lineage validation
# ----------------------------------------------------------

def test_admit_rejects_a_missing_claim_reference():

    result = knowledge_admission_service.admit(
        {"licence_reference": "lic_abc123", "scope": "single_case"}
    )

    assert result.admitted is False

    assert result.reason.startswith("missing_claim_reference")


def test_admit_rejects_a_non_claim_shaped_reference():

    result = knowledge_admission_service.admit(
        _input("au2_claim_001")
    )

    assert result.admitted is False

    assert result.reason.startswith("invalid_claim_reference")


def test_admit_rejects_an_unresolved_claim_reference():

    result = knowledge_admission_service.admit(
        _input("clm_missing"),
        known_claim_references=["clm_other"],
    )

    assert result.admitted is False

    assert result.reason.startswith("unresolved_reference")


def test_admit_rejects_a_missing_licence_reference():

    result = knowledge_admission_service.admit(
        {"source_claim_reference": "clm_abc", "scope": "single_case"}
    )

    assert result.admitted is False

    assert result.reason.startswith("missing_licence_reference")


def test_admit_rejects_a_non_licence_shaped_reference():

    result = knowledge_admission_service.admit(
        _input("clm_abc", licence="unlicensed_hypothesis")
    )

    assert result.admitted is False

    assert result.reason.startswith("invalid_licence_reference")


def test_admit_rejects_an_unresolved_licence_reference():

    result = knowledge_admission_service.admit(
        _input("clm_abc"),
        known_licence_references=["lic_other"],
    )

    assert result.admitted is False

    assert result.reason.startswith("unresolved_licence_reference")


def test_admit_rejects_a_self_parent():

    result = knowledge_admission_service.admit(
        _input("clm_abc", lineage=["clm_abc"])
    )

    assert result.admitted is False

    assert result.reason.startswith("claim_lineage_incomplete")


def test_admit_rejects_a_non_claim_parent():

    result = knowledge_admission_service.admit(
        _input("clm_abc", lineage=["obs_element_1"])
    )

    assert result.admitted is False

    assert result.reason.startswith("claim_lineage_incomplete")


def test_admit_rejects_an_unresolved_parent():

    result = knowledge_admission_service.admit(
        _input("clm_abc", lineage=["clm_parent"]),
        known_claim_references=["clm_abc"],
    )

    assert result.admitted is False

    assert result.reason.startswith("claim_lineage_incomplete")


def test_admit_rejects_a_bare_string_lineage():

    result = knowledge_admission_service.admit(
        {
            "source_claim_reference": "clm_abc",
            "licence_reference": "lic_abc123",
            "scope": "single_case",
            "lineage_reference": "clm_parent",
        }
    )

    assert result.admitted is False

    assert result.reason.startswith("invalid_lineage")


def test_admit_rejects_an_unknown_scope():

    result = knowledge_admission_service.admit(
        _input("clm_abc", scope="universal")
    )

    assert result.admitted is False

    assert result.reason.startswith("unknown_scope")


# ----------------------------------------------------------
# 6. eligibility is delegated to the TransitionValidator
# ----------------------------------------------------------

def test_admit_returns_not_implemented_without_a_claim():

    result = knowledge_admission_service.admit(_input("clm_abc"))

    assert result.admitted is False

    assert result.candidate_reference is None

    assert result.reason.startswith(NOT_IMPLEMENTED_REASON_PREFIX)


def test_admit_delegates_eligibility_to_the_validator(monkeypatch):

    import core.governance.admission.knowledge_admission_service_v1 as service_module

    seen = []

    class _Spy:

        def can_be_candidate(self, claim, *, known_claim_ids=None):

            seen.append(claim)

            return TransitionResult.allow("spy")

    monkeypatch.setattr(service_module, "transition_validator", _Spy())

    claim = _claim()

    result = service_module.knowledge_admission_service.admit(
        _input(claim.claim_id),
        claim=claim,
        known_claim_references=[claim.claim_id],
    )

    assert len(seen) == 1

    assert result.admitted is True


def test_admit_propagates_a_validator_denial():

    # A claim-like object that passes the service's own checks but that the
    # settled validator rule rejects (unknown source_type).
    fake = SimpleNamespace(
        claim_id="clm_fake",
        source_type="made_up_source",
        claim_type="existence",
        original_scope="single_case",
        licence_reference="lic_abc123",
        lineage_reference=(),
    )

    result = knowledge_admission_service.admit(
        _input("clm_fake"),
        claim=fake,
    )

    assert result.admitted is False

    assert result.reason.startswith("claim_not_typed")


def test_admit_rejects_scope_escalation():

    claim = _claim(scope="single_case")

    result = knowledge_admission_service.admit(
        _input(claim.claim_id, scope="general"),
        claim=claim,
        known_claim_references=[claim.claim_id],
    )

    assert result.admitted is False

    assert result.reason.startswith("scope_escalation")


def test_admit_rejects_a_claim_reference_mismatch():

    claim = _claim()

    result = knowledge_admission_service.admit(
        _input("clm_other"),
        claim=claim,
        known_claim_references=["clm_other", claim.claim_id],
    )

    assert result.admitted is False

    assert result.reason.startswith("claim_reference_mismatch")


def test_admit_rejects_a_licence_reference_mismatch():

    claim = _claim(licence_reference="lic_abc123")

    result = knowledge_admission_service.admit(
        _input(claim.claim_id, licence="lic_other"),
        claim=claim,
        known_claim_references=[claim.claim_id],
    )

    assert result.admitted is False

    assert result.reason.startswith("licence_reference_mismatch")


# ----------------------------------------------------------
# 7. an eligible claim is admitted; a candidate is issued
# ----------------------------------------------------------

def test_admit_admits_an_eligible_claim():

    claim = _claim()

    result = knowledge_admission_service.admit(
        _input(claim.claim_id),
        claim=claim,
        known_claim_references=[claim.claim_id],
    )

    assert result.admitted is True

    assert result.candidate_reference.startswith("kcd_")

    assert KnowledgeAdmissionResult.CREATES_TRUTH is False


def test_admit_is_deterministic():

    claim = _claim()

    first = knowledge_admission_service.admit(
        _input(claim.claim_id),
        claim=claim,
        known_claim_references=[claim.claim_id],
    )

    second = knowledge_admission_service.admit(
        _input(claim.claim_id),
        claim=claim,
        known_claim_references=[claim.claim_id],
    )

    assert first.candidate_reference == second.candidate_reference


def test_admit_accepts_a_knowledge_candidate_input():

    claim = _claim()

    candidate = build_knowledge_candidate(
        source_claim_reference=claim.claim_id,
        licence_reference="lic_abc123",
        scope="single_case",
    )

    assert isinstance(candidate, KnowledgeCandidate)

    result = knowledge_admission_service.admit(
        candidate,
        claim=claim,
        known_claim_references=[claim.claim_id],
    )

    assert result.admitted is True

    assert result.candidate_reference == candidate.candidate_reference


def test_admit_accepts_a_declared_lineage():

    parent = _claim()

    child = _claim(lineage=(parent.claim_id,))

    result = knowledge_admission_service.admit(
        _input(child.claim_id, lineage=[parent.claim_id]),
        claim=child,
        known_claim_references=[child.claim_id, parent.claim_id],
    )

    assert result.admitted is True


# ----------------------------------------------------------
# 8. the service never creates a Claim, a LicenceRecord or an event
# ----------------------------------------------------------

def test_service_never_calls_a_creation_factory():

    forbidden_calls = (
        "mint_claim",
        "mint_licence_record",
        "record_derivation_event",
        "record_endorsement_event",
        "Claim",
        "LicenceRecord",
    )

    called = _called_names(SERVICE_PATH)

    offenders = [name for name in called if name in forbidden_calls]

    assert offenders == [], "admission called a creation factory: %r" % (
        offenders,
    )


def test_service_never_imports_events():

    roots = _imported_roots(SERVICE_PATH)

    offenders = [
        root
        for root in roots
        if root == "core.governance.events"
        or root.startswith("core.governance.events.")
    ]

    assert offenders == [], "admission imported events: %r" % (offenders,)


# ----------------------------------------------------------
# 9. dependency direction
# ----------------------------------------------------------

def test_admission_has_no_client_imports():

    offenders = []

    for path in sorted(ADMISSION_DIR.rglob("*.py")):

        for root in _imported_roots(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if root == forbidden or root.startswith(forbidden + "."):

                    offenders.append((str(path), root))

    assert offenders == [], "admission imported a client subsystem: %r" % (
        offenders,
    )


def test_no_sibling_module_imports_admission():

    offenders = []

    for path in sorted(GOVERNANCE_DIR.rglob("*.py")):

        parts = path.parts

        if "admission" in parts or "tests" in parts:

            continue

        for root in _imported_roots(path):

            if root == "core.governance.admission" or root.startswith(
                "core.governance.admission."
            ):

                offenders.append((str(path), root))

    assert offenders == [], "a sibling module imported admission: %r" % (
        offenders,
    )
