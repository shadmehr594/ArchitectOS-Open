"""ARCHITECTURAL-CHANGE-ORCHESTRATOR-01E acceptance tests."""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import inspect
import json

import pytest

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeStrategy,
    DeclarativeChangePlan,
    ExecutionReadinessResult,
    PLANNING_STATUS_PLANNABLE,
    READINESS_STATUS_BLOCKED_CONSTRAINT,
    READINESS_STATUS_BLOCKED_GEOMETRY,
    READINESS_STATUS_BLOCKED_SITE,
    READINESS_STATUS_INSUFFICIENT_EVIDENCE,
    READINESS_STATUS_READY,
    READINESS_STATUS_READY_WITH_PREREQUISITES,
    STRATEGY_APPLICABILITY_WITH_PREREQUISITES,
    STRATEGY_GENERATION_STATUS_BLOCKED_READINESS,
    STRATEGY_GENERATION_STATUS_GENERATED,
    dumps_contract,
    loads_contract,
)
from core.architecture.reasoning import architectural_change_strategy_generator_v1 as module
from core.architecture.reasoning.architectural_change_strategy_generator_v1 import (
    generate_architectural_change_strategies,
)


def _plan(plan_id, operations, targets, *, preserves=(), prerequisites=()):
    return DeclarativeChangePlan(
        plan_id=plan_id,
        intent_id=f"intent:{plan_id}",
        proposed_operations=operations,
        target_entities=targets,
        preserve_constraints=preserves,
        prerequisites=prerequisites,
        rejection_conditions=("protected_constraint_violation",),
        required_rechecks=("quality_gate",),
        deferred_dependencies=(),
        planning_status=PLANNING_STATUS_PLANNABLE,
        planning_reasons=("semantic_plan_ready",),
        evidence=("semantic_snapshot",),
        provenance={"phase": "01C"},
    )


def _readiness(plan, status=READINESS_STATUS_READY, *, unresolved=(), reasons=()):
    return ExecutionReadinessResult(
        plan_id=plan.plan_id,
        readiness_status=status,
        unresolved_dependencies=unresolved,
        constraint_conflicts=(),
        preservation_requirements=("external_footprint",),
        required_checks_before_execution=("strategy_quality",),
        rejection_reasons=reasons,
        evidence=("readiness_evidence",),
        provenance={"phase": "01D"},
    )


def _snapshot():
    return {
        "snapshot_id": "plan-snapshot-01",
        "hard_constraints": ("program_complete",),
        "protected_constraints": [
            {"constraint_id": "protected_structural_core", "status": "active"}
        ],
    }


def _hash(value):
    document = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def test_kitchen_resize_produces_three_semantic_constraint_preserving_options():
    plan = _plan(
        "kitchen-resize",
        ("increase_space_area(kitchen)", "preserve_circulation_continuity", "reevaluate_openings"),
        ("space:kitchen",),
        preserves=("living_usability", "circulation_continuity", "target_access"),
    )
    result = generate_architectural_change_strategies(plan, _readiness(plan), _snapshot())

    assert result.generation_status == STRATEGY_GENERATION_STATUS_GENERATED
    assert tuple(item.strategy_type for item in result.strategies) == (
        "ADJACENT_AREA_TRANSFER", "SERVICE_BAND_REALLOCATION", "RELATIONSHIP_RECONFIGURATION",
    )
    for strategy in result.strategies:
        assert {"living_usability", "circulation_continuity", "target_access"} <= set(strategy.preserved_constraints)
        assert {"living_minimum_usability", "circulation", "access"} <= set(strategy.required_rechecks)
        assert strategy.risks
        assert strategy.strategy_rank_hint is None


def test_master_bath_adjacency_has_comparable_private_access_paths():
    plan = _plan(
        "master-bath",
        ("strengthen_adjacency(master_bedroom,bathroom)", "reevaluate_privacy", "reevaluate_access"),
        ("space:master_bedroom", "space:bathroom"),
        preserves=("privacy", "circulation_continuity", "target_access"),
    )
    result = generate_architectural_change_strategies(plan, _readiness(plan), _snapshot())

    assert len(result.strategies) == 2
    assert all("privacy" in item.preserved_constraints for item in result.strategies)
    assert all({"privacy", "circulation", "access"} <= set(item.required_rechecks) for item in result.strategies)


def test_living_daylight_ready_generates_semantic_opportunities():
    plan = _plan(
        "living-daylight",
        ("improve_daylight(living)", "identify_window_opportunity(living)"),
        ("space:living",),
        preserves=("privacy", "circulation_continuity"),
    )
    result = generate_architectural_change_strategies(plan, _readiness(plan), _snapshot())

    assert len(result.strategies) == 2
    assert {item.strategy_type for item in result.strategies} == {
        "DAYLIGHT_EXPOSURE_RELATIONSHIP", "FACADE_OPPORTUNITY_RELATIONSHIP",
    }


@pytest.mark.parametrize("status", (
    READINESS_STATUS_BLOCKED_SITE,
    READINESS_STATUS_BLOCKED_GEOMETRY,
    READINESS_STATUS_BLOCKED_CONSTRAINT,
    READINESS_STATUS_INSUFFICIENT_EVIDENCE,
))
def test_blocked_readiness_returns_zero_strategies_and_preserves_reason(status):
    plan = _plan("blocked", ("improve_daylight(living)",), ("space:living",))
    readiness = _readiness(
        plan, status, unresolved=("site_orientation_evidence",), reasons=("readiness_gate_rejected",)
    )
    result = generate_architectural_change_strategies(plan, readiness, _snapshot())

    assert result.generation_status == STRATEGY_GENERATION_STATUS_BLOCKED_READINESS
    assert result.strategies == ()
    assert f"readiness_status:{status}" in result.blocker_reasons
    assert "unresolved_dependency:site_orientation_evidence" in result.blocker_reasons


def test_ready_with_prerequisites_carries_them_on_every_strategy():
    plan = _plan(
        "conditional-kitchen",
        ("increase_space_area(kitchen)",),
        ("space:kitchen",),
        prerequisites=("stakeholder_confirmation",),
    )
    readiness = _readiness(
        plan,
        READINESS_STATUS_READY_WITH_PREREQUISITES,
        unresolved=("stakeholder_confirmation",),
        reasons=("nonblocking_prerequisite:stakeholder_confirmation",),
    )
    result = generate_architectural_change_strategies(plan, readiness, _snapshot())

    assert result.strategies
    assert all(item.prerequisites == ("stakeholder_confirmation",) for item in result.strategies)
    assert all(item.applicability_status == STRATEGY_APPLICABILITY_WITH_PREREQUISITES for item in result.strategies)


def test_order_is_deterministic_inputs_are_immutable_and_result_round_trips():
    plan = _plan(
        "stable", ("increase_space_area(kitchen)",), ("space:kitchen",),
        preserves=("hard_program_constraint",),
    )
    readiness = _readiness(plan)
    snapshot = _snapshot()
    before = (deepcopy(plan), deepcopy(readiness), deepcopy(snapshot))
    snapshot_hash = _hash(snapshot)

    first = generate_architectural_change_strategies(plan, readiness, snapshot)
    second = generate_architectural_change_strategies(plan, readiness, deepcopy(snapshot))

    assert (plan, readiness, snapshot) == before
    assert _hash(snapshot) == snapshot_hash
    assert first == second
    assert dumps_contract(first) == dumps_contract(second)
    assert loads_contract(dumps_contract(first)) == first
    restored_strategy = loads_contract(dumps_contract(first.strategies[0]))
    assert isinstance(restored_strategy, ArchitecturalChangeStrategy)
    assert restored_strategy == first.strategies[0]
    assert all("hard_program_constraint" in item.preserved_constraints for item in first.strategies)
    assert all("program_complete" in item.preserved_constraints for item in first.strategies)
    assert all("protected_structural_core" in item.preserved_constraints for item in first.strategies)


def test_module_has_no_producer_dependency_or_spatial_payload_fields():
    source = inspect.getsource(module)
    lowered = source.lower()
    forbidden = (
        "house" + "diffusion", "gs" + "diff", "move_wall", "polygon", "coordinate",
        "create_door", "create_window", "site_fit", "structure", "bim", "ifc", "render",
    )
    assert all(term not in lowered for term in forbidden)

    imports = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert imports <= {
        "__future__", "collections.abc", "typing",
        "core.architecture.contracts.architectural_change_contracts_v1",
    }

    contract_fields = set(ArchitecturalChangeStrategy.__dataclass_fields__)
    assert not contract_fields & {"coordinates", "polygon", "walls", "doors", "windows", "geometry"}
