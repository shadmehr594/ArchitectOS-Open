"""Licence Assignment Result Hardening V1 — isolated self-checks.

Proves that the governance-owned LicenceRecord is exposed through
LicenceAssignmentResult without weakening any rule:

    1. a successful assignment exposes the EXACT LicenceRecord
    2. a denial exposes licence_record=None
    3. to_dict() is unchanged and does NOT serialise the object
    4. the result stays immutable and authority-free
    5. the exposed record feeds the G3 accessor with the SAME licence id
    6. no new identity generation; import boundaries unchanged
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.accessors import resolve_licence_state
from core.governance.licence import LicenceRecord
from core.governance.licensing import (
    LicenceAssignmentResult,
    build_licence_assignment_request,
    licence_assignment_service,
)


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

LICENSING_DIR = GOVERNANCE_DIR / "licensing"

RESULT_MODULE = LICENSING_DIR / "licence_assignment_result_v1.py"

SERVICE_MODULE = LICENSING_DIR / "licence_assignment_service_v1.py"

TO_DICT_KEYS = {
    "contract",
    "version",
    "assigned",
    "licence_reference",
    "target_claim_reference",
    "reason",
    "creates_claims",
    "decides_truth",
    "creates_knowledge",
}


def _request(claim_reference="clm_abc", licence="candidate_for_learning"):

    return build_licence_assignment_request(
        target_claim_reference=claim_reference,
        requested_licence=licence,
        basis_reference="teacher_review",
        actor_reference="human:teacher",
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


# ----------------------------------------------------------
# 1. success exposes the exact record
# ----------------------------------------------------------

def test_successful_assignment_exposes_the_exact_licence_record():

    result = licence_assignment_service.assign_licence(
        _request(), previous_licence="unlicensed_hypothesis"
    )

    assert result.assigned is True

    assert isinstance(result.licence_record, LicenceRecord)

    assert result.licence_record.licence_id == result.licence_reference

    assert result.licence_record.target_claim_reference == "clm_abc"

    assert result.licence_record.licence_state == "candidate_for_learning"


def test_exposed_record_is_the_governance_minted_one():

    result = licence_assignment_service.assign_licence(
        _request(), previous_licence="unlicensed_hypothesis"
    )

    assert result.licence_record.licence_id.startswith("lic_")

    assert result.licence_record.licence_id == result.licence_reference


# ----------------------------------------------------------
# 2. denial exposes None
# ----------------------------------------------------------

def test_denial_exposes_no_record():

    # an illegal transition (heuristic_candidate -> human_endorsed_hypothesis)
    result = licence_assignment_service.assign_licence(
        _request(licence="human_endorsed_hypothesis"),
        previous_licence="heuristic_candidate",
    )

    assert result.assigned is False

    assert result.licence_record is None

    assert result.licence_reference is None


def test_denial_for_a_bad_request_also_exposes_none():

    result = licence_assignment_service.assign_licence(
        "not a request", previous_licence="unlicensed_hypothesis"
    )

    assert result.assigned is False

    assert result.licence_record is None


# ----------------------------------------------------------
# 3. to_dict() unchanged and excludes the object
# ----------------------------------------------------------

def test_to_dict_is_unchanged_and_excludes_the_record():

    result = licence_assignment_service.assign_licence(
        _request(), previous_licence="unlicensed_hypothesis"
    )

    payload = result.to_dict()

    assert set(payload) == TO_DICT_KEYS

    assert "licence_record" not in payload

    assert isinstance(payload["licence_reference"], str)


def test_to_dict_is_truth_free():

    payload = licence_assignment_service.assign_licence(
        _request(), previous_licence="unlicensed_hypothesis"
    ).to_dict()

    for field in ("truth", "confidence", "certainty", "approval", "probability"):

        assert field not in payload


# ----------------------------------------------------------
# 4. immutability and authority
# ----------------------------------------------------------

def test_result_remains_immutable():

    result = licence_assignment_service.assign_licence(
        _request(), previous_licence="unlicensed_hypothesis"
    )

    with pytest.raises(FrozenInstanceError):

        result.licence_record = None


def test_result_declares_no_authority():

    assert LicenceAssignmentResult.CREATES_CLAIMS is False

    assert LicenceAssignmentResult.DECIDES_TRUTH is False

    assert LicenceAssignmentResult.CREATES_KNOWLEDGE is False


def test_builder_still_refuses_forbidden_fields():

    from core.governance.licensing.licence_assignment_result_v1 import (
        LicenceAssignmentResultError,
        build_licence_assignment_result,
    )

    for field in ("truth", "confidence", "approval", "licence_id", "claim_id"):

        with pytest.raises(LicenceAssignmentResultError):

            build_licence_assignment_result(
                assigned=True,
                licence_reference="lic_x",
                target_claim_reference="clm_x",
                reason="r",
                **{field: "forged"},
            )


def test_builder_accepts_the_record_field():

    from core.governance.licensing.licence_assignment_result_v1 import (
        build_licence_assignment_result,
    )

    result = build_licence_assignment_result(
        assigned=True,
        licence_reference="lic_x",
        target_claim_reference="clm_x",
        reason="r",
        licence_record=None,
    )

    assert result.licence_record is None


# ----------------------------------------------------------
# 5. the exposed record feeds G3 with the same id
# ----------------------------------------------------------

def test_exposed_record_resolves_through_the_g3_accessor():

    result = licence_assignment_service.assign_licence(
        _request(), previous_licence="unlicensed_hypothesis"
    )

    view = resolve_licence_state(
        result.target_claim_reference,
        licence_records=[result.licence_record],
    )

    assert view.resolved is True

    assert view.licence_state == "candidate_for_learning"

    # the SAME licence id — no second record, no fabrication
    assert view.licence_reference == result.licence_reference


# ----------------------------------------------------------
# 6. no new identity generation; import boundaries unchanged
# ----------------------------------------------------------

def test_result_module_generates_no_identity():

    called = _called_names(RESULT_MODULE)

    for name in ("uuid4", "uuid1", "mint_id", "new_licence_id", "mint_licence_record"):

        assert name not in called


def test_result_module_imports_only_stdlib():

    offenders = [
        root for root in _imported_roots(RESULT_MODULE) if root.startswith("core.")
    ]

    assert offenders == []


def test_licensing_has_no_client_imports():

    offenders = []

    for path in sorted(LICENSING_DIR.rglob("*.py")):

        for root in _imported_roots(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if root == forbidden or root.startswith(forbidden + "."):

                    offenders.append((path.name, root))

    assert offenders == []


def test_service_still_mints_exactly_once():

    called = _called_names(SERVICE_MODULE)

    assert called.count("mint_licence_record") == 1

    assert "validate_licence_transition" in called
