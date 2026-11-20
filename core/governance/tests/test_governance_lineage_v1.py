"""Claim Governance lineage V1 — isolated boundary self-checks.

PASS expected
    * lineage references are immutable
    * the lineage view derives from existing objects
    * missing references are rejected
    * self references are rejected
    * no client imports (and claim/events never import lineage)

FAIL expected (i.e. the guard must raise)
    * mutation attempt
    * external lineage injection
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.claim import mint_claim
from core.governance.events import (
    record_derivation_event,
    record_endorsement_event,
)
from core.governance.lineage import (
    DagCheckReport,
    LineageReference,
    LineageReferenceError,
    LineageView,
    LineageViewError,
    build_lineage_reference,
    check_dag,
)


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

LINEAGE_DIR = GOVERNANCE_DIR / "lineage"


# ----------------------------------------------------------
# helpers
# ----------------------------------------------------------

def _claim(**overrides):

    fields = {
        "content": "a bed exists",
        "origin": "provider_payload",
        "source_type": "observation_evidence",
        "claim_type": "existence",
        "original_scope": "single_case",
    }

    fields.update(overrides)

    return mint_claim(**fields)


# ----------------------------------------------------------
# 1. the reference value object
# ----------------------------------------------------------

def test_lineage_reference_is_immutable():

    reference = build_lineage_reference(
        trigger_references=("sleeping_element",),
    )

    with pytest.raises(FrozenInstanceError):

        reference.trigger_references = ("other",)


def test_lineage_reference_has_no_authority():

    reference = build_lineage_reference()

    assert LineageReference.AUTHORITY is False

    assert LineageReference.CREATES_CLAIMS is False

    assert LineageReference.CHANGES_CLAIMS is False

    assert LineageReference.STORES_LINEAGE is False

    payload = reference.to_dict()

    assert payload["authority"] is False

    assert payload["creates_claims"] is False

    assert payload["changes_claims"] is False


def test_lineage_reference_rejects_empty_and_unknown_kinds():

    with pytest.raises(LineageReferenceError):

        build_lineage_reference(trigger_references=("",))

    with pytest.raises(LineageReferenceError):

        build_lineage_reference(made_up_kind=("x",))


def test_lineage_reference_deduplicates():

    reference = build_lineage_reference(
        evidence_references=("a", "a", "b"),
    )

    assert reference.evidence_references == ("a", "b")


# ----------------------------------------------------------
# 2. the derived view
# ----------------------------------------------------------

def test_lineage_view_derives_from_existing_objects():

    parent = _claim(content="a bed exists")

    child = _claim(
        content="this space may be a sleeping area",
        source_type="generated_hypothesis",
        claim_type="semantic_space",
        lineage_reference=(parent.claim_id,),
    )

    event = record_derivation_event(
        input_references=(parent.claim_id, "sleeping_element"),
        output_claim_reference=child.claim_id,
        operation_type="mint_from_proposal",
        licence_check_result="allowed",
    )

    endorsement = record_endorsement_event(
        actor="human:teacher",
        target_claim_reference=child.claim_id,
        previous_licence="unlicensed_hypothesis",
        new_licence="human_endorsed_hypothesis",
        act_type="endorsement",
        scope="single_case",
        ordering=1,
    )

    reference = build_lineage_reference(
        parent_claim_references=(parent.claim_id,),
        trigger_references=("sleeping_element",),
        evidence_references=("provider_phrase_1",),
    )

    view = LineageView(
        claims=(parent, child),
        derivation_events=(event,),
        endorsement_events=(endorsement,),
        references={child.claim_id: reference},
    )

    assert view.exists(child.claim_id) is True

    assert view.parents(child.claim_id) == (parent.claim_id,)

    assert view.trigger_references(child.claim_id) == ("sleeping_element",)

    assert view.evidence_references(child.claim_id) == ("provider_phrase_1",)

    assert [
        item.event_id for item in view.derivation_events(child.claim_id)
    ] == [event.event_id]

    assert [
        item.event_id for item in view.endorsement_events(child.claim_id)
    ] == [endorsement.event_id]

    created = view.what_created(child.claim_id)

    assert created["derived"] is True

    assert created["read_only"] is True

    assert created["parents"] == [parent.claim_id]

    connected = view.connected(child.claim_id)

    assert connected["derivation_events"] == [event.event_id]

    assert connected["endorsement_events"] == [endorsement.event_id]

    assert view.to_dict()["stores_lineage_state"] is False


def test_lineage_view_falls_back_to_the_claim_reference():

    parent = _claim()

    child = _claim(
        source_type="generated_hypothesis",
        claim_type="semantic_space",
        lineage_reference=(parent.claim_id,),
    )

    view = LineageView(claims=(parent, child))

    assert view.parents(child.claim_id) == (parent.claim_id,)

    assert view.trigger_references(child.claim_id) == ()


def test_lineage_view_is_read_only():

    view = LineageView()

    with pytest.raises(LineageViewError):

        view._claims = {}

    with pytest.raises(LineageViewError):

        del view._claims


# ----------------------------------------------------------
# 3. DAG safety
# ----------------------------------------------------------

def test_missing_reference_rejected():

    child = _claim(
        source_type="generated_hypothesis",
        claim_type="semantic_space",
        lineage_reference=("clm_does_not_exist",),
    )

    report = check_dag(claims=(child,))

    assert isinstance(report, DagCheckReport)

    assert report.ok is False

    assert any(
        item.code == "missing_reference" for item in report.violations
    )


def test_self_reference_rejected():

    claim = _claim()

    reference = build_lineage_reference(
        parent_claim_references=(claim.claim_id,),
    )

    report = check_dag(
        claims=(claim,),
        references={claim.claim_id: reference},
    )

    assert report.ok is False

    assert any(
        item.code == "self_reference" for item in report.violations
    )


def test_forward_reference_rejected():

    child = _claim(
        source_type="generated_hypothesis",
        claim_type="semantic_space",
    )

    # The event declares itself as the claim's creation event AND takes the
    # claim as an input — a forward reference.
    event = record_derivation_event(
        input_references=(child.claim_id,),
        output_claim_reference=child.claim_id,
        operation_type="mint_from_proposal",
    )

    linked = _claim(
        source_type="generated_hypothesis",
        claim_type="semantic_space",
        creation_event=event.event_id,
    )

    report = check_dag(claims=(child, linked), derivation_events=(event,))

    assert report.ok is False

    assert any(
        item.code == "forward_reference" for item in report.violations
    )


def test_event_target_must_resolve():

    event = record_endorsement_event(
        actor="human:teacher",
        target_claim_reference="clm_missing",
        previous_licence="unlicensed_hypothesis",
        new_licence="human_endorsed_hypothesis",
        act_type="endorsement",
        scope="single_case",
        ordering=1,
    )

    report = check_dag(endorsement_events=(event,))

    assert report.ok is False

    assert any(
        item.code == "missing_reference" for item in report.violations
    )


def test_well_formed_lineage_passes():

    parent = _claim()

    child = _claim(
        source_type="generated_hypothesis",
        claim_type="semantic_space",
        lineage_reference=(parent.claim_id,),
    )

    event = record_derivation_event(
        input_references=(parent.claim_id, "sleeping_element"),
        output_claim_reference=child.claim_id,
        operation_type="mint_from_proposal",
        licence_check_result="allowed",
    )

    report = check_dag(
        claims=(parent, child),
        derivation_events=(event,),
    )

    assert report.ok is True

    assert report.violations == ()

    assert report.read_only is True


# ----------------------------------------------------------
# 4. external lineage injection
# ----------------------------------------------------------

def test_external_lineage_injection_rejected():

    with pytest.raises(LineageViewError):

        LineageView(
            claims=(),
            references={
                "clm_x": {"parent_claim_references": ["clm_y"]},
            },
        )


def test_injected_reference_that_does_not_resolve_is_a_violation():

    claim = _claim()

    injected = build_lineage_reference(
        parent_claim_references=("clm_injected",),
    )

    report = check_dag(
        claims=(claim,),
        references={claim.claim_id: injected},
    )

    assert report.ok is False

    assert any(
        item.code == "missing_reference" for item in report.violations
    )


# ----------------------------------------------------------
# 5. dependency proof
# ----------------------------------------------------------

def _imported_modules(path):

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    modules = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            modules.extend(alias.name for alias in node.names)

        elif isinstance(node, ast.ImportFrom):

            if node.module:

                modules.append(node.module)

    return modules


def test_lineage_imports_no_client_subsystem():

    offenders = []

    for path in sorted(LINEAGE_DIR.rglob("*.py")):

        for module in _imported_modules(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if module == forbidden or module.startswith(forbidden + "."):

                    offenders.append((str(path), module))

    assert offenders == [], (
        "lineage imported a client subsystem: %r" % (offenders,)
    )


def test_claim_and_events_never_import_lineage():

    offenders = []

    for area in ("claim", "events", "licence", "proposal"):

        for path in sorted((GOVERNANCE_DIR / area).rglob("*.py")):

            for module in _imported_modules(path):

                if module.startswith("core.governance.lineage"):

                    offenders.append((str(path), module))

    assert offenders == [], (
        "a source module imported lineage (direction reversed): %r"
        % (offenders,)
    )
