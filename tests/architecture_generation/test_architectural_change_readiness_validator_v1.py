"""ARCHITECTURAL-CHANGE-ORCHESTRATOR-01D acceptance tests."""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import inspect
import json

import pytest

from core.architecture.contracts.architectural_change_contracts_v1 import (
    DeclarativeChangePlan,
    PLANNING_STATUS_GEOMETRY_DEPENDENT,
    PLANNING_STATUS_INSUFFICIENT_EVIDENCE,
    PLANNING_STATUS_PLANNABLE,
    PLANNING_STATUS_PLANNABLE_WITH_PREREQUISITES,
    PLANNING_STATUS_REJECTED_BY_CONSTRAINT,
    PLANNING_STATUS_SITE_DEPENDENT,
    READINESS_STATUS_BLOCKED_CONSTRAINT,
    READINESS_STATUS_BLOCKED_GEOMETRY,
    READINESS_STATUS_BLOCKED_SITE,
    READINESS_STATUS_INSUFFICIENT_EVIDENCE,
    READINESS_STATUS_READY,
    READINESS_STATUS_READY_WITH_PREREQUISITES,
    dumps_contract,
    loads_contract,
)
from core.architecture.reasoning import architectural_change_readiness_validator_v1 as module
from core.architecture.reasoning.architectural_change_readiness_validator_v1 import (
    validate_declarative_plan_readiness,
)


def _plan(
    plan_id: str,
    *,
    targets=("space:kitchen",),
    prerequisites=(),
    deferred=(),
    status=PLANNING_STATUS_PLANNABLE,
    evidence=("semantic_snapshot",),
):
    return DeclarativeChangePlan(
        plan_id=plan_id,
        intent_id=f"intent:{plan_id}",
        proposed_operations=("semantic_operation_that_must_not_be_executed",),
        target_entities=targets,
        preserve_constraints=("circulation_continuity",),
        prerequisites=prerequisites,
        rejection_conditions=("protected_constraint_violation",),
        required_rechecks=("quality_gate",),
        deferred_dependencies=deferred,
        planning_status=status,
        planning_reasons=("test_fixture",),
        evidence=evidence,
        provenance={"phase": "01C"},
    )


def _snapshot(**updates):
    value = {
        "nodes": [
            {"node_id": "space:kitchen"},
            {"node_id": "space:master_bedroom"},
            {"node_id": "space:bathroom"},
            {"node_id": "space:living"},
        ],
        "geometry_status": {"state": "resolved"},
        "topology_status": {"state": "resolved"},
        "orientation_status": {"state": "resolved"},
    }
    value.update(updates)
    return value


def _hash(value):
    document = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def test_kitchen_resize_with_unresolved_geometry_is_blocked_geometry():
    plan = _plan(
        "kitchen-resize",
        prerequisites=("geometry_availability",),
        status=PLANNING_STATUS_GEOMETRY_DEPENDENT,
    )
    result = validate_declarative_plan_readiness(
        plan, _snapshot(geometry_status={"state": "pending"})
    )

    assert result.readiness_status == READINESS_STATUS_BLOCKED_GEOMETRY
    assert "geometry_availability" in result.unresolved_dependencies


def test_master_bath_hard_protected_conflict_is_blocked_constraint():
    plan = _plan(
        "master-bath",
        targets=("space:master_bedroom", "space:bathroom"),
        prerequisites=("topology_availability",),
        status=PLANNING_STATUS_REJECTED_BY_CONSTRAINT,
    )
    snapshot = _snapshot(constraint_conflicts=[{
        "constraint_id": "protected_private_core",
        "severity": "hard",
        "status": "violated",
        "protected": True,
    }])
    result = validate_declarative_plan_readiness(plan, snapshot)

    assert result.readiness_status == READINESS_STATUS_BLOCKED_CONSTRAINT
    assert result.constraint_conflicts == ("protected_private_core",)


def test_living_daylight_without_orientation_is_blocked_site():
    plan = _plan(
        "living-daylight",
        targets=("space:living",),
        deferred=("site_orientation_evidence",),
        status=PLANNING_STATUS_SITE_DEPENDENT,
    )
    result = validate_declarative_plan_readiness(
        plan, _snapshot(orientation_status={"state": "missing"})
    )

    assert result.readiness_status == READINESS_STATUS_BLOCKED_SITE
    assert "site_orientation_evidence" in result.unresolved_dependencies


def test_missing_target_evidence_is_insufficient():
    plan = _plan(
        "missing-target",
        targets=("space:not_present",),
        status=PLANNING_STATUS_INSUFFICIENT_EVIDENCE,
    )
    result = validate_declarative_plan_readiness(plan, _snapshot())

    assert result.readiness_status == READINESS_STATUS_INSUFFICIENT_EVIDENCE
    assert "unresolved_target:space:not_present" in result.rejection_reasons


def test_nonblocking_prerequisite_is_ready_with_prerequisites():
    plan = _plan(
        "stakeholder-check",
        prerequisites=("stakeholder_confirmation",),
        status=PLANNING_STATUS_PLANNABLE_WITH_PREREQUISITES,
    )
    result = validate_declarative_plan_readiness(plan, _snapshot())

    assert result.readiness_status == READINESS_STATUS_READY_WITH_PREREQUISITES
    assert result.unresolved_dependencies == ("stakeholder_confirmation",)


def test_complete_plan_without_blocker_is_ready_and_preservation_is_summarized():
    plan = _plan("ready")
    snapshot = _snapshot(
        preservation_requirements=("external_footprint",),
        required_checks_before_execution=("strategy_quality",),
        validation_evidence=("constraint_snapshot",),
    )
    result = validate_declarative_plan_readiness(plan, snapshot)

    assert result.readiness_status == READINESS_STATUS_READY
    assert result.unresolved_dependencies == ()
    assert {"circulation_continuity", "external_footprint"} <= set(result.preservation_requirements)
    assert {"quality_gate", "strategy_quality"} <= set(result.required_checks_before_execution)


def test_rejected_plan_has_priority_over_other_blockers():
    plan = _plan(
        "priority",
        prerequisites=("geometry_availability",),
        deferred=("site_orientation_evidence",),
        status=PLANNING_STATUS_REJECTED_BY_CONSTRAINT,
    )
    result = validate_declarative_plan_readiness(
        plan,
        _snapshot(
            geometry_status={"state": "missing"},
            orientation_status={"state": "missing"},
        ),
    )
    assert result.readiness_status == READINESS_STATUS_BLOCKED_CONSTRAINT


def test_inputs_are_unchanged_and_output_is_deterministic_and_round_trips():
    plan = _plan("immutable", prerequisites=("geometry_availability",))
    snapshot = _snapshot(geometry_status={"state": "pending"})
    plan_before, snapshot_before = deepcopy(plan), deepcopy(snapshot)
    snapshot_hash = _hash(snapshot)

    first = validate_declarative_plan_readiness(plan, snapshot)
    second = validate_declarative_plan_readiness(plan, deepcopy(snapshot))

    assert plan == plan_before
    assert snapshot == snapshot_before
    assert _hash(snapshot) == snapshot_hash
    assert first == second
    assert dumps_contract(first) == dumps_contract(second)
    assert loads_contract(dumps_contract(first)) == first


def test_validator_does_not_import_or_call_spatial_execution_apis():
    source = inspect.getsource(module)
    lowered = source.lower()
    forbidden = (
        "house" + "diffusion", "gs" + "diff", "move_wall", "move_polygon",
        "create_door", "create_window", "site_fit", "structure", "ifc", "render",
        "coordinate_solving", "alternative_geometry",
    )
    assert all(term not in lowered for term in forbidden)
    assert "proposed_operations" not in source

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
