"""ARCHITECTURAL-CHANGE-ORCHESTRATOR-01C acceptance tests."""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import inspect
import json

import pytest

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeIntent,
    DesignChangeImpact,
    PLANNING_STATUS_GEOMETRY_DEPENDENT,
    PLANNING_STATUS_INSUFFICIENT_EVIDENCE,
    PLANNING_STATUS_PLANNABLE,
    PLANNING_STATUS_REJECTED_BY_CONSTRAINT,
    PLANNING_STATUS_SITE_DEPENDENT,
    dumps_contract,
    loads_contract,
)
from core.architecture.reasoning import architectural_change_planner_v1 as module
from core.architecture.reasoning.architectural_change_planner_v1 import (
    plan_architectural_change,
)


@pytest.fixture
def snapshot():
    return {
        "nodes": [
            {"node_id": "space:kitchen", "space_type": "OPEN_KITCHEN"},
            {"node_id": "space:living", "space_type": "LIVING_RECEPTION"},
            {"node_id": "space:master_bedroom", "space_type": "MASTER_BEDROOM_SLEEPING"},
            {"node_id": "space:bathroom", "space_type": "FAMILY_BATHROOM"},
        ],
        "edges": [
            {"edge_id": "relation:kitchen-living", "type": "adjacency"},
            {"edge_id": "relation:master-bath", "type": "adjacency"},
        ],
        "geometry_status": {"state": "pending"},
        "adjacency_status": {"state": "available"},
        "topology_status": {"state": "available"},
    }


def _intent(intent_id, change_type, targets, *, direction=None, preference=None, text="ignored"):
    return ArchitecturalChangeIntent(
        change_intent_id=intent_id,
        change_type=change_type,
        targets=targets,
        direction=direction,
        preference=preference,
        user_text=text,
    )


def _impact(intent, *, status="FEASIBLE_PENDING_GEOMETRY", risks=(), reasons=()):
    return DesignChangeImpact(
        change_intent_id=intent.change_intent_id,
        affected_spaces=intent.targets,
        required_rechecks=("quality_gate",),
        risk_flags=risks,
        feasibility_status=status,
        feasibility_reasons=reasons,
        evidence=("semantic_snapshot",),
        confidence="medium",
    )


def _hash(value):
    document = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def test_kitchen_resize_is_declarative_and_geometry_dependent(snapshot):
    intent = _intent("kitchen-grow", "resize_space", ("space:kitchen",), direction="increase", text="آشپزخانه رو بزرگ‌تر کن")
    plan = plan_architectural_change(intent, _impact(intent), snapshot)

    assert "increase_space_area(kitchen)" in plan.proposed_operations
    assert {"living_usability", "circulation_continuity", "target_access"} <= set(plan.preserve_constraints)
    assert {"geometry_availability", "adjacency_availability"} <= set(plan.prerequisites)
    assert plan.planning_status == PLANNING_STATUS_GEOMETRY_DEPENDENT


def test_master_bathroom_relation_preserves_privacy_access_and_circulation(snapshot):
    intent = _intent("master-bath", "change_relation", ("space:master_bedroom", "space:bathroom"), direction="closer", text="مستر رو به حمام نزدیک‌تر کن")
    plan = plan_architectural_change(intent, _impact(intent), snapshot)

    assert "strengthen_adjacency(master_bedroom,bathroom)" in plan.proposed_operations
    assert {"reevaluate_privacy", "reevaluate_access", "preserve_circulation_continuity"} <= set(plan.proposed_operations)
    assert {"topology_availability", "geometry_availability"} <= set(plan.prerequisites)
    assert {"privacy", "target_access", "circulation_continuity"} <= set(plan.preserve_constraints)
    assert plan.planning_status == PLANNING_STATUS_GEOMETRY_DEPENDENT


def test_living_daylight_defers_facade_and_site_without_guessing_direction(snapshot):
    intent = _intent("living-light", "improve_quality", ("space:living",), preference="daylight", text="پذیرایی نور بیشتری بگیره")
    impact = _impact(intent, status="FEASIBLE_PENDING_SITE", risks=("site_orientation_dependency",), reasons=("site_orientation_evidence_missing",))
    plan = plan_architectural_change(intent, impact, snapshot)

    assert {"improve_daylight(living)", "identify_window_opportunity(living)", "reevaluate_privacy"} <= set(plan.proposed_operations)
    assert plan.planning_status == PLANNING_STATUS_SITE_DEPENDENT
    assert {"facade_evidence", "site_orientation_evidence"} <= set(plan.deferred_dependencies)
    assert "privacy" in plan.preserve_constraints
    assert not any(direction in dumps_contract(plan).lower() for direction in ("north", "south", "east", "west"))


def test_hard_protected_constraint_rejects_plan(snapshot):
    intent = _intent("blocked", "resize_space", ("space:kitchen",), direction="increase")
    blocked = deepcopy(snapshot)
    blocked["constraint_conflicts"] = [{
        "constraint_id": "protected_core_boundary",
        "severity": "hard",
        "status": "violated",
        "protected": True,
    }]
    plan = plan_architectural_change(intent, _impact(intent), blocked)

    assert plan.planning_status == PLANNING_STATUS_REJECTED_BY_CONSTRAINT
    assert "hard_constraint_conflict:protected_core_boundary" in plan.planning_reasons


def test_missing_target_evidence_is_insufficient(snapshot):
    intent = _intent("missing", "resize_space", ("space:unknown",), direction="increase")
    impact = _impact(intent, status="UNKNOWN", risks=("missing_target_evidence",), reasons=("target_entities_not_found_in_snapshot",))
    plan = plan_architectural_change(intent, impact, snapshot)

    assert plan.planning_status == PLANNING_STATUS_INSUFFICIENT_EVIDENCE
    assert "target_evidence_missing" in plan.planning_reasons


def test_planner_ignores_user_text_and_is_deterministic(snapshot):
    first_intent = _intent("stable", "resize_space", ("space:kitchen",), direction="increase", text="unrelated")
    second_intent = _intent("stable", "resize_space", ("space:kitchen",), direction="increase", text="متن کاملاً متفاوت")
    impact = _impact(first_intent)

    first = plan_architectural_change(first_intent, impact, snapshot)
    second = plan_architectural_change(second_intent, impact, deepcopy(snapshot))

    assert first == second
    assert dumps_contract(first) == dumps_contract(second)
    assert loads_contract(dumps_contract(first)) == first


def test_resolved_prerequisites_make_plan_plannable(snapshot):
    intent = _intent("ready", "resize_space", ("space:kitchen",), direction="increase")
    ready = deepcopy(snapshot)
    ready["geometry_status"] = {"state": "resolved"}
    plan = plan_architectural_change(intent, _impact(intent), ready)

    assert plan.planning_status == PLANNING_STATUS_PLANNABLE
    assert plan.planning_reasons == ("semantic_plan_ready",)


def test_inputs_remain_unchanged_by_copy_and_hash(snapshot):
    intent = _intent("immutable", "change_relation", ("space:master_bedroom", "space:bathroom"), direction="closer")
    impact = _impact(intent)
    intent_before, impact_before, snapshot_before = deepcopy(intent), deepcopy(impact), deepcopy(snapshot)
    snapshot_hash = _hash(snapshot)

    plan_architectural_change(intent, impact, snapshot)

    assert intent == intent_before
    assert impact == impact_before
    assert snapshot == snapshot_before
    assert _hash(snapshot) == snapshot_hash


def test_planner_has_no_generator_or_spatial_edit_api():
    source = inspect.getsource(module)
    lowered = source.lower()
    forbidden = (
        "house" + "diffusion", "gs" + "diff", "generator", "create_variant",
        "move_wall", "move_polygon", "create_door", "create_window",
        "site_fit", "ifc", "render",
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
