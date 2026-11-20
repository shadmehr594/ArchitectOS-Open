"""Runtime Lifecycle Executor V1 — isolated self-checks.

PASS
    1. the complete A1..A8 lifecycle reaches admission
    2. the A2 (supplied proposal) path works
    3. every id originates from governance
    4. licence ordering is preserved (A5 targets the reserved claim id)
    5. claim.creation_event is populated
    6. the returned LicenceRecord is the source of the resolved licence state
    7. the registry is appended exactly once
    8. admission succeeds

DENIAL
    9. proposal rejection (A3)
   10. licence denial (A5)
   11. mint rejection (A6)
   12. registry conflict (A7)
   13. admission denial (A8) — preserved verbatim

HARDENING
   14. the runtime creates no identity
   15. the runtime constructs no governance object
   16. no truth / confidence / approval field
   17. no governance module imports the runtime
   18. no persistence
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.runtime.lifecycle_executor_v1 import (
    LifecycleExecutor,
    LifecycleResult,
    STAGE_A3,
    STAGE_A5,
    STAGE_A6,
    STAGE_A7,
    STAGE_A8,
    STATUS_ADMITTED,
    STATUS_DENIED,
    STATUS_ERROR,
)


RUNTIME_MODULE = (
    Path(__file__).resolve().parents[1] / "lifecycle_executor_v1.py"
)

GOVERNANCE_DIR = Path(__file__).resolve().parents[2] / "governance"


def _auv2():

    return {
        "interpretation_states": {"primary": {"claim_id": "au2_claim_001"}},
        "semantic_space": {"label": "a bed exists"},
        "claim_trace": [
            {
                "claim_id": "au2_claim_001",
                "label": "a bed exists",
                "claim_type": "existence",
                "source_evidence": ["obs_bed_region"],
                "interpretation_basis": ["observed"],
            }
        ],
        "non_claims": ["no geometry asserted"],
    }


def _run(executor=None, **overrides):

    fields = dict(
        source_type="observation_evidence",
        origin="provider_payload",
        basis_reference="teacher_review",
        actor_reference="human:teacher",
    )

    fields.update(overrides)

    executor = executor if executor is not None else LifecycleExecutor()

    return executor.run(_auv2(), language="en", **fields)


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

def test_complete_lifecycle_reaches_admission():

    executor = LifecycleExecutor()

    result = _run(executor)

    assert result.completed is True

    assert result.status == STATUS_ADMITTED

    assert result.stage == STAGE_A8

    assert result.admission is not None

    assert result.admission.admitted is True


def test_proposal_fields_path_works():

    result = LifecycleExecutor().run(
        proposal_fields={
            "proposed_content": "a bed exists",
            "proposed_claim_type": "existence",
            "trigger_references": ("obs_bed_region",),
        },
        source_type="observation_evidence",
        origin="provider_payload",
    )

    assert result.completed is True

    assert result.stage == STAGE_A8


def test_every_id_originates_from_governance():

    result = _run()

    assert result.proposal_reference.startswith("prp_")

    assert result.claim_reference.startswith("clm_")

    assert result.derivation_event_reference.startswith("dev_")

    assert result.licence_reference.startswith("lic_")

    assert result.candidate_reference.startswith("kcd_")


def test_licence_ordering_is_preserved(monkeypatch):

    import core.runtime.lifecycle_executor_v1 as executor_module

    captured = []

    real_service = executor_module.licence_assignment_service

    class _Spy:

        def assign_licence(self, request, **kwargs):

            captured.append(request)

            return real_service.assign_licence(request, **kwargs)

    monkeypatch.setattr(executor_module, "licence_assignment_service", _Spy())

    result = _run()

    assert result.completed is True

    # the licence targeted the SAME id the claim was minted with, so the
    # assignment necessarily ran before the mint
    assert len(captured) == 1

    assert captured[0].target_claim_reference == result.claim_reference


def test_claim_creation_event_is_populated():

    executor = LifecycleExecutor()

    result = _run(executor)

    entry = executor.registry.lookup_by_claim(result.claim_reference)

    assert entry is not None

    # the registry holds the derivation-event reference of the claim's event
    assert entry.derivation_event_reference == result.derivation_event_reference


def test_licence_record_is_the_source_of_the_resolved_state():

    result = _run()

    assert result.licence_state == "candidate_for_learning"

    # the state was resolved through G3 from the returned LicenceRecord
    assert result.licence_reference is not None


def test_registry_is_appended_exactly_once():

    executor = LifecycleExecutor()

    _run(executor)

    assert executor.registry.count() == 1

    assert executor.registry.known_claim_references() == (
        executor.registry.snapshot()[0].claim_reference,
    )

    assert executor.registry.known_licence_references() == (
        executor.registry.snapshot()[0].licence_reference,
    )


def test_admission_succeeds_with_registry_known_sets():

    executor = LifecycleExecutor()

    result = _run(executor)

    assert result.admission.admitted is True

    assert result.admission.candidate_reference == result.candidate_reference


# ==========================================================
# DENIAL
# ==========================================================

def test_proposal_rejection_is_terminal():

    result = LifecycleExecutor().run(
        proposal_fields={
            "proposed_content": "x",
            "trigger_references": ("obs_1",),
            "uncertainty": "not a mapping",
        },
        source_type="observation_evidence",
        origin="origin",
    )

    assert result.completed is False

    assert result.status == STATUS_DENIED

    assert result.stage == STAGE_A3

    assert "uncertainty" in result.reason


def test_licence_denial_is_terminal():

    result = _run(requested_licence="heuristic_candidate")

    assert result.completed is False

    assert result.status == STATUS_DENIED

    assert result.stage == STAGE_A5

    assert result.claim_reference is None


def test_mint_rejection_is_terminal():

    result = _run(source_type="made_up_source")

    assert result.completed is False

    assert result.stage == STAGE_A6

    assert result.status == STATUS_ERROR

    assert result.error_type == "ClaimVocabularyError"


def test_registry_conflict_is_terminal(monkeypatch):

    import core.runtime.lifecycle_executor_v1 as executor_module

    from core.governance.identity.reservation_v1 import reserve_claim_id

    from core.governance.registry import ReferenceRegistry

    reservation = reserve_claim_id()

    monkeypatch.setattr(executor_module, "reserve_claim_id", lambda: reservation)

    registry = ReferenceRegistry()

    # a DIFFERENT entry already exists for the claim the executor will mint
    registry.append(
        {"claim_reference": reservation.identity, "licence_reference": "lic_other"}
    )

    result = LifecycleExecutor(registry=registry).run(
        _auv2(),
        source_type="observation_evidence",
        origin="provider_payload",
    )

    assert result.completed is False

    assert result.status == STATUS_DENIED

    assert result.stage == STAGE_A7

    # the pre-existing entry was not overwritten
    assert registry.count() == 1

    assert registry.lookup_by_claim(reservation.identity).licence_reference == "lic_other"


def test_admission_denial_is_preserved_verbatim(monkeypatch):

    import core.runtime.lifecycle_executor_v1 as executor_module

    from core.governance.admission.knowledge_admission_result_v1 import (
        build_knowledge_admission_result,
    )

    denial = build_knowledge_admission_result(
        admitted=False,
        candidate_reference=None,
        reason="stub: eligibility denied by governance",
    )

    class _Stub:

        def admit(self, *args, **kwargs):

            return denial

    monkeypatch.setattr(executor_module, "knowledge_admission_service", _Stub())

    result = _run()

    assert result.completed is False

    assert result.stage == STAGE_A8

    assert result.reason == "stub: eligibility denied by governance"


# ==========================================================
# HARDENING
# ==========================================================

def test_runtime_creates_no_identity():

    called = _called_names(RUNTIME_MODULE)

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


def test_runtime_constructs_no_governance_object():

    called = _called_names(RUNTIME_MODULE)

    for name in (
        "Claim",
        "LicenceRecord",
        "DerivationEvent",
        "EndorsementEvent",
        "InterpretationProposal",
        "KnowledgeCandidate",
    ):

        assert name not in called


def test_runtime_result_carries_no_truth_field():

    result = _run()

    payload = result.to_dict()

    for field in ("truth", "confidence", "certainty", "approval", "probability"):

        assert field not in payload

    assert LifecycleResult.CREATES_IDENTITY is False

    assert LifecycleResult.CREATES_OBJECTS is False

    assert LifecycleResult.DECIDES_TRUTH is False

    assert LifecycleResult.PERSISTS is False


def test_runtime_result_is_immutable():

    result = _run()

    with pytest.raises(FrozenInstanceError):

        result.completed = False


def test_no_governance_module_imports_the_runtime():

    offenders = []

    for path in sorted(GOVERNANCE_DIR.rglob("*.py")):

        for root in _imported_roots(path):

            if root == "core.runtime" or root.startswith("core.runtime."):

                offenders.append((path.name, root))

    assert offenders == [], "governance imported the runtime: %r" % (offenders,)


def test_runtime_does_not_persist():

    source = RUNTIME_MODULE.read_text(encoding="utf-8")

    for token in ("open(", "json.dump", "pickle", "sqlite3", "shelve", "Path("):

        assert token not in source


def test_runtime_imports_only_governance_and_stdlib():

    offenders = []

    for root in _imported_roots(RUNTIME_MODULE):

        if root.startswith("core.") and not root.startswith("core.governance"):

            offenders.append(root)

    assert offenders == [], "runtime imported outside governance: %r" % (offenders,)


def test_ordering_counter_is_runtime_owned():

    executor = LifecycleExecutor()

    assert executor.next_ordering() == 1

    assert executor.next_ordering() == 2
