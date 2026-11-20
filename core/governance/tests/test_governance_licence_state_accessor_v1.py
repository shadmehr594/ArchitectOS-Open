"""Licence State Accessor (G3) — isolated self-checks.

Verifies the read model:
    1. a licensed claim resolves from its LicenceRecord
    2. an endorsement event alone resolves a state (no licence artefact)
    3. a record + an agreeing event do not conflict
    4. a missing licence resolves safely
    5. an invalid / missing / unresolved claim reference is rejected
    6. conflicting states are reported deterministically, never reconciled
    7. the view is immutable and declares no authority
    8. the accessor has NO creation side effects
    9. AST dependency checks: no client imports, no id minting, no duplicated
       prefix literal, no reverse imports
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.accessors import (
    REASON_CONFLICT,
    REASON_FROM_EVENT,
    REASON_FROM_RECORD,
    REASON_INVALID_CLAIM,
    REASON_MISSING_CLAIM,
    REASON_MISSING_LICENCE,
    REASON_UNRESOLVED_CLAIM,
    LicenceStateView,
    LicenceStateViewError,
    resolve_licence_state,
)
from core.governance.claim import mint_claim
from core.governance.events import record_endorsement_event
from core.governance.identity.reservation_v1 import reservation_ledger
from core.governance.licence import mint_licence_record


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

ACCESSORS_DIR = GOVERNANCE_DIR / "accessors"

ACCESSOR_MODULE = ACCESSORS_DIR / "licence_state_accessor_v1.py"

IDENTITY_PREFIX_LITERALS = ("clm_", "lic_", "dev_", "eev_")


def _claim():

    return mint_claim(
        content="a bed exists",
        origin="provider_payload",
        source_type="observation_evidence",
        claim_type="existence",
        original_scope="single_case",
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
# 1. a licensed claim resolves from its LicenceRecord
# ----------------------------------------------------------

def test_licensed_claim_resolves_from_its_record():

    claim = _claim()

    record = mint_licence_record(
        target_claim_reference=claim.claim_id,
        licence_state="candidate_for_learning",
    )

    view = resolve_licence_state(
        claim.claim_id,
        licence_records=[record],
    )

    assert view.licence_state == "candidate_for_learning"

    assert view.licence_reference == record.licence_id

    assert view.reason == REASON_FROM_RECORD

    assert view.resolved is True


def test_unrelated_records_are_ignored():

    claim = _claim()

    other = mint_licence_record(
        target_claim_reference="clm_other",
        licence_state="candidate_for_learning",
    )

    view = resolve_licence_state(claim.claim_id, licence_records=[other])

    assert view.licence_state is None

    assert view.reason == REASON_MISSING_LICENCE


# ----------------------------------------------------------
# 2. an endorsement event alone resolves a state
# ----------------------------------------------------------

def test_endorsement_event_resolves_a_state_without_a_licence_artefact():

    claim = _claim()

    event = record_endorsement_event(
        actor="human:teacher",
        target_claim_reference=claim.claim_id,
        previous_licence="unlicensed_hypothesis",
        new_licence="human_endorsed_hypothesis",
        act_type="endorsement",
        scope="single_case",
        ordering=1,
    )

    view = resolve_licence_state(claim.claim_id, endorsement_events=[event])

    assert view.licence_state == "human_endorsed_hypothesis"

    assert view.licence_reference is None

    assert view.reason == REASON_FROM_EVENT


# ----------------------------------------------------------
# 3. agreeing record + event do not conflict
# ----------------------------------------------------------

def test_agreeing_record_and_event_prefer_the_record_reference():

    claim = _claim()

    record = mint_licence_record(
        target_claim_reference=claim.claim_id,
        licence_state="human_endorsed_hypothesis",
    )

    event = record_endorsement_event(
        actor="human:teacher",
        target_claim_reference=claim.claim_id,
        previous_licence="unlicensed_hypothesis",
        new_licence="human_endorsed_hypothesis",
        act_type="endorsement",
        scope="single_case",
        ordering=1,
    )

    view = resolve_licence_state(
        claim.claim_id,
        licence_records=[record],
        endorsement_events=[event],
    )

    assert view.licence_state == "human_endorsed_hypothesis"

    assert view.licence_reference == record.licence_id

    assert view.reason == REASON_FROM_RECORD


# ----------------------------------------------------------
# 4. missing licence resolves safely
# ----------------------------------------------------------

def test_missing_licence_resolves_safely():

    claim = _claim()

    view = resolve_licence_state(claim.claim_id)

    assert view.resolved is False

    assert view.licence_state is None

    assert view.licence_reference is None

    assert view.reason == REASON_MISSING_LICENCE


# ----------------------------------------------------------
# 5. reference validation
# ----------------------------------------------------------

def test_invalid_reference_is_rejected():

    for value in ("au2_claim_001", "unlicensed_hypothesis", "abc"):

        view = resolve_licence_state(value)

        assert view.resolved is False

        assert view.reason == REASON_INVALID_CLAIM


def test_missing_reference_is_rejected():

    for value in (None, "", "   "):

        view = resolve_licence_state(value)

        assert view.reason == REASON_MISSING_CLAIM


def test_unresolved_reference_is_rejected():

    view = resolve_licence_state(
        "clm_abc", known_claim_references=["clm_other"]
    )

    assert view.reason == REASON_UNRESOLVED_CLAIM


def test_resolved_reference_passes_the_known_set():

    claim = _claim()

    record = mint_licence_record(
        target_claim_reference=claim.claim_id,
        licence_state="unlicensed_hypothesis",
    )

    view = resolve_licence_state(
        claim.claim_id,
        licence_records=[record],
        known_claim_references=[claim.claim_id],
    )

    assert view.resolved is True


# ----------------------------------------------------------
# 6. conflicting states are reported deterministically
# ----------------------------------------------------------

def test_conflicting_states_are_reported_not_reconciled():

    claim = _claim()

    first = mint_licence_record(
        target_claim_reference=claim.claim_id,
        licence_state="unlicensed_hypothesis",
    )

    second = mint_licence_record(
        target_claim_reference=claim.claim_id,
        licence_state="heuristic_candidate",
    )

    view = resolve_licence_state(
        claim.claim_id,
        licence_records=[first, second],
    )

    assert view.resolved is False

    assert view.licence_state is None

    assert view.licence_reference is None

    assert view.reason.startswith(REASON_CONFLICT)


def test_conflict_resolution_is_deterministic():

    claim = _claim()

    first = mint_licence_record(
        target_claim_reference=claim.claim_id,
        licence_state="unlicensed_hypothesis",
    )

    second = mint_licence_record(
        target_claim_reference=claim.claim_id,
        licence_state="heuristic_candidate",
    )

    forward = resolve_licence_state(
        claim.claim_id, licence_records=[first, second]
    )

    reverse = resolve_licence_state(
        claim.claim_id, licence_records=[second, first]
    )

    assert forward == reverse

    assert forward.reason == reverse.reason


# ----------------------------------------------------------
# 7. the view is immutable and authority-free
# ----------------------------------------------------------

def test_view_is_immutable():

    view = resolve_licence_state("clm_abc")

    with pytest.raises(FrozenInstanceError):

        view.licence_state = "heuristic_candidate"


def test_view_declares_no_authority():

    assert LicenceStateView.CREATES_OBJECTS is False

    assert LicenceStateView.MINTS_IDENTITIES is False

    assert LicenceStateView.CREATES_EVENTS is False

    assert LicenceStateView.MUTATES_CLAIMS is False

    assert LicenceStateView.ASSIGNS_LICENCES is False

    assert LicenceStateView.DECIDES_TRUTH is False


def test_view_rejects_an_unknown_state():

    with pytest.raises(LicenceStateViewError):

        LicenceStateView("clm_abc", None, "made_up_state", "x")


def test_view_to_dict_has_no_truth_field():

    payload = resolve_licence_state("clm_abc").to_dict()

    for field in ("truth", "confidence", "certainty", "approval"):

        assert field not in payload


# ----------------------------------------------------------
# 8. no creation side effects
# ----------------------------------------------------------

def test_resolve_has_no_creation_side_effects():

    claim = _claim()

    record = mint_licence_record(
        target_claim_reference=claim.claim_id,
        licence_state="candidate_for_learning",
    )

    before = reservation_ledger.count()

    resolve_licence_state(claim.claim_id, licence_records=[record])

    assert reservation_ledger.count() == before

    # the claim is untouched
    assert claim.licence_reference is None


def test_accessor_calls_no_creation_factory():

    forbidden_calls = (
        "mint_claim",
        "mint_licence_record",
        "record_derivation_event",
        "record_endorsement_event",
        "Claim",
        "LicenceRecord",
        "reserve_claim_id",
        "reserve_licence_id",
        "reserve_derivation_event_id",
        "reserve_endorsement_event_id",
    )

    called = _called_names(ACCESSOR_MODULE)

    offenders = [name for name in called if name in forbidden_calls]

    assert offenders == []


# ----------------------------------------------------------
# 9. AST dependency checks
# ----------------------------------------------------------

def test_accessor_has_no_client_imports():

    offenders = []

    for path in sorted(ACCESSORS_DIR.rglob("*.py")):

        for root in _imported_roots(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if root == forbidden or root.startswith(forbidden + "."):

                    offenders.append((path.name, root))

    assert offenders == []


def test_accessor_imports_only_licence_and_lineage():

    allowed = (
        "core.governance.accessors",
        "core.governance.licence",
        "core.governance.lineage",
    )

    offenders = []

    for path in sorted(ACCESSORS_DIR.rglob("*.py")):

        for root in _imported_roots(path):

            if not root.startswith("core."):

                continue

            if not any(root == area or root.startswith(area + ".") for area in allowed):

                offenders.append((path.name, root))

    assert offenders == []


def test_accessor_does_not_mint_ids():

    called = _called_names(ACCESSOR_MODULE)

    for name in ("uuid4", "uuid1", "mint_id"):

        assert name not in called


def test_accessor_duplicates_no_prefix_literal():

    for path in sorted(ACCESSORS_DIR.rglob("*.py")):

        for literal in _string_literals(path):

            assert literal not in IDENTITY_PREFIX_LITERALS


def test_no_governance_module_imports_accessors():

    offenders = []

    for path in sorted(GOVERNANCE_DIR.rglob("*.py")):

        parts = path.parts

        if "accessors" in parts or "tests" in parts:

            continue

        for root in _imported_roots(path):

            if root == "core.governance.accessors" or root.startswith(
                "core.governance.accessors."
            ):

                offenders.append((path.name, root))

    assert offenders == []
