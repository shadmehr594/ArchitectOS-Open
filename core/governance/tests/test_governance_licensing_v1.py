"""Claim Governance licensing V1 — isolated boundary self-checks.

PASS expected
    * a valid claim receives a valid licence record
    * identity is minted internally
    * the validator is called
    * the result is immutable

FAIL expected
    * a client supplied licence_id is rejected
    * a forbidden licence is rejected
    * truth fields are rejected
    * an invalid transition is rejected
    * an unknown claim reference is rejected
    * the service cannot create knowledge
    * the service cannot create a claim
    * the service cannot bypass the validator
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.licensing import (
    FORBIDDEN_REQUESTED_LICENCES,
    FORBIDDEN_REQUEST_FIELDS,
    LicenceAssignmentRequest,
    LicenceAssignmentRequestError,
    LicenceAssignmentResult,
    LicenceAssignmentResultError,
    build_licence_assignment_request,
    build_licence_assignment_result,
    licence_assignment_service,
)


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

LICENSING_DIR = GOVERNANCE_DIR / "licensing"


TARGET = "clm_0123456789abcdef"


# ----------------------------------------------------------
# helpers
# ----------------------------------------------------------

def _request(**overrides):

    fields = {
        "target_claim_reference": TARGET,
        "requested_licence": "human_endorsed_hypothesis",
        "basis_reference": "basis_1",
        "actor_reference": "human:teacher",
    }

    fields.update(overrides)

    return build_licence_assignment_request(**fields)


# ----------------------------------------------------------
# PASS
# ----------------------------------------------------------

def test_valid_claim_receives_a_valid_licence_record():

    result = licence_assignment_service.assign_licence(
        _request(), previous_licence="unlicensed_hypothesis"
    )

    assert isinstance(result, LicenceAssignmentResult)

    assert result.assigned is True

    assert str(result.licence_reference).startswith("lic_")

    assert result.target_claim_reference == TARGET

    assert "assigned" in result.reason


def test_identity_is_minted_internally():

    first = licence_assignment_service.assign_licence(
        _request(), previous_licence="unlicensed_hypothesis"
    )

    second = licence_assignment_service.assign_licence(
        _request(), previous_licence="unlicensed_hypothesis"
    )

    assert first.licence_reference != second.licence_reference

    # minted by governance, never supplied
    assert str(first.licence_reference).startswith("lic_")


def test_result_is_immutable():

    result = licence_assignment_service.assign_licence(
        _request(), previous_licence="unlicensed_hypothesis"
    )

    with pytest.raises(FrozenInstanceError):

        result.assigned = False


def test_result_declares_its_boundary():

    assert LicenceAssignmentResult.CREATES_CLAIMS is False

    assert LicenceAssignmentResult.DECIDES_TRUTH is False

    assert LicenceAssignmentResult.CREATES_KNOWLEDGE is False

    payload = licence_assignment_service.assign_licence(
        _request(), previous_licence="unlicensed_hypothesis"
    ).to_dict()

    for key in ("creates_claims", "decides_truth", "creates_knowledge"):

        assert payload[key] is False


# ----------------------------------------------------------
# FAIL: identity injection
# ----------------------------------------------------------

def test_client_supplied_licence_id_is_rejected():

    for field in ("licence_id", "license_id"):

        with pytest.raises(LicenceAssignmentRequestError):

            build_licence_assignment_request(
                target_claim_reference=TARGET,
                requested_licence="human_endorsed_hypothesis",
                **{field: "lic_forged"},
            )

    with pytest.raises(TypeError):

        licence_assignment_service.assign_licence(
            _request(),
            previous_licence="unlicensed_hypothesis",
            licence_id="lic_forged",
        )


def test_client_supplied_claim_id_is_rejected():

    with pytest.raises(LicenceAssignmentRequestError):

        build_licence_assignment_request(
            target_claim_reference=TARGET,
            requested_licence="human_endorsed_hypothesis",
            claim_id="clm_forged",
        )


# ----------------------------------------------------------
# FAIL: forbidden licences
# ----------------------------------------------------------

def test_forbidden_licence_is_rejected():

    for forbidden in (
        "fact",
        "truth",
        "verified_truth",
        "probability",
        "confidence",
        "certainty",
    ):

        assert forbidden in FORBIDDEN_REQUESTED_LICENCES

        with pytest.raises(LicenceAssignmentRequestError):

            build_licence_assignment_request(
                target_claim_reference=TARGET,
                requested_licence=forbidden,
            )


def test_service_denies_a_forbidden_licence_even_if_constructed():

    request = _request()

    # bypass the constructor guard to simulate a malformed request
    object.__setattr__(request, "requested_licence", "truth")

    result = licence_assignment_service.assign_licence(
        request, previous_licence="unlicensed_hypothesis"
    )

    assert result.assigned is False

    assert result.licence_reference is None

    assert "unknown licence state" in result.reason


# ----------------------------------------------------------
# FAIL: truth fields
# ----------------------------------------------------------

def test_truth_fields_are_rejected():

    for field in (
        "truth",
        "truth_status",
        "verified_truth",
        "approval",
        "approved",
        "confidence",
        "confidence_as_truth",
        "certainty",
        "probability",
        "knowledge_status",
    ):

        assert field in FORBIDDEN_REQUEST_FIELDS

        with pytest.raises(LicenceAssignmentRequestError):

            build_licence_assignment_request(
                target_claim_reference=TARGET,
                requested_licence="human_endorsed_hypothesis",
                **{field: "forged"},
            )


def test_result_rejects_authority_fields():

    for field in ("truth", "approved", "confidence", "knowledge_status", "licence_id"):

        with pytest.raises(LicenceAssignmentResultError):

            build_licence_assignment_result(
                assigned=True,
                licence_reference="lic_x",
                target_claim_reference=TARGET,
                reason="ok",
                **{field: "forged"},
            )


# ----------------------------------------------------------
# FAIL: transitions and claim references
# ----------------------------------------------------------

def test_invalid_transition_is_rejected():

    result = licence_assignment_service.assign_licence(
        _request(), previous_licence="heuristic_candidate"
    )

    assert result.assigned is False

    assert result.licence_reference is None

    assert "not defined" in result.reason


def test_unknown_previous_licence_is_rejected():

    result = licence_assignment_service.assign_licence(
        _request(), previous_licence="made_up_state"
    )

    assert result.assigned is False

    assert "unknown previous_licence" in result.reason


def test_unknown_claim_reference_is_rejected():

    not_a_claim = licence_assignment_service.assign_licence(
        _request(target_claim_reference="sleeping_element"),
        previous_licence="unlicensed_hypothesis",
    )

    assert not_a_claim.assigned is False

    assert "not a claim reference" in not_a_claim.reason

    unresolved = licence_assignment_service.assign_licence(
        _request(),
        previous_licence="unlicensed_hypothesis",
        known_claim_references=("clm_other",),
    )

    assert unresolved.assigned is False

    assert "unknown claim reference" in unresolved.reason


def test_non_request_is_rejected():

    result = licence_assignment_service.assign_licence(
        "not a request", previous_licence="unlicensed_hypothesis"
    )

    assert result.assigned is False

    assert "requires a LicenceAssignmentRequest" in result.reason


def test_request_is_immutable():

    request = _request()

    with pytest.raises(FrozenInstanceError):

        request.requested_licence = "candidate_for_learning"


def test_service_has_no_mutable_state():

    from core.governance.licensing import LicenceAssignmentService

    service = LicenceAssignmentService()

    with pytest.raises(AttributeError):

        service.some_new_state = 1


# ----------------------------------------------------------
# FAIL: the service must not act beyond licensing
# ----------------------------------------------------------

def _parse(path):

    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _identifiers(tree):

    names = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Name):

            names.append(node.id)

        elif isinstance(node, ast.Attribute):

            names.append(node.attr)

        elif isinstance(node, ast.keyword):

            if node.arg:

                names.append(node.arg)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

            names.append(node.name)

            names.extend(arg.arg for arg in node.args.args)

    return names


def _called_names(path):

    names = []

    for node in ast.walk(_parse(path)):

        if isinstance(node, ast.Call):

            func = node.func

            if isinstance(func, ast.Name):

                names.append(func.id)

            elif isinstance(func, ast.Attribute):

                names.append(func.attr)

    return names


def test_service_cannot_create_a_claim():

    offenders = []

    for path in sorted(LICENSING_DIR.rglob("*.py")):

        for name in _identifiers(_parse(path)):

            if name in ("mint_claim", "Claim", "new_claim_id"):

                offenders.append((str(path), name))

    assert offenders == [], (
        "the licensing boundary created or touched a claim: %r" % (offenders,)
    )


def test_service_cannot_create_knowledge():

    offenders = []

    for path in sorted(LICENSING_DIR.rglob("*.py")):

        for name in _identifiers(_parse(path)):

            if name in (
                "KnowledgeCandidate",
                "TeachingCandidate",
                "mint_knowledge",
                "create_knowledge",
            ):

                offenders.append((str(path), name))

    assert offenders == [], (
        "the licensing boundary created knowledge: %r" % (offenders,)
    )


def test_service_creates_no_event_directly():

    offenders = []

    for path in sorted(LICENSING_DIR.rglob("*.py")):

        for name in _called_names(path):

            if name in (
                "record_derivation_event",
                "record_endorsement_event",
            ):

                offenders.append((str(path), name))

    assert offenders == [], (
        "the licensing boundary created an event: %r" % (offenders,)
    )


def test_service_does_not_bypass_the_validator():

    calls = []

    for path in sorted(LICENSING_DIR.rglob("*.py")):

        calls.extend(
            name
            for name in _called_names(path)
            if name == "validate_licence_transition"
        )

    assert calls == ["validate_licence_transition"], (
        "the licensing boundary must call the validator exactly once: %r"
        % (calls,)
    )


def test_service_mints_the_licence_internally():

    calls = []

    for path in sorted(LICENSING_DIR.rglob("*.py")):

        calls.extend(
            name
            for name in _called_names(path)
            if name == "mint_licence_record"
        )

    assert calls == ["mint_licence_record"], (
        "the licensing boundary must mint exactly one licence record: %r"
        % (calls,)
    )


# ----------------------------------------------------------
# dependency proof
# ----------------------------------------------------------

def _imported_modules(path):

    modules = []

    for node in ast.walk(_parse(path)):

        if isinstance(node, ast.Import):

            modules.extend(alias.name for alias in node.names)

        elif isinstance(node, ast.ImportFrom):

            if node.module:

                modules.append(node.module)

    return modules


def test_licensing_imports_no_client_subsystem():

    offenders = []

    for path in sorted(LICENSING_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if module == forbidden or module.startswith(forbidden + "."):

                    offenders.append((str(path), module))

    assert offenders == [], (
        "the licensing boundary imported a client subsystem: %r" % (offenders,)
    )


def test_licensing_imports_governance_only():

    offenders = []

    for path in sorted(LICENSING_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            if module.startswith("core.") and not module.startswith(
                "core.governance."
            ):

                offenders.append((str(path), module))

    assert offenders == [], (
        "the licensing boundary imported outside governance: %r" % (offenders,)
    )


def test_no_reverse_import_of_licensing():

    offenders = []

    for area in (
        "claim",
        "licence",
        "events",
        "proposal",
        "lineage",
        "validation",
        "act_classifier",
        "endorsement",
        "adapters",
        "intake",
        "minting",
    ):

        for path in sorted((GOVERNANCE_DIR / area).rglob("*.py")):

            for module in _imported_modules(path):

                if module.startswith("core.governance.licensing"):

                    offenders.append((str(path), module))

    assert offenders == [], (
        "a governance module imported licensing (direction reversed): %r"
        % (offenders,)
    )
