"""ARCHITECTURAL-CHANGE-ORCHESTRATOR-01F-A acceptance tests."""
from __future__ import annotations

from copy import deepcopy
import json

from shapely.geometry import Polygon

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeStrategy,
    ExecutionReadinessResult,
    GEOMETRY_REALIZATION_STATUS_REALIZED,
    GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT,
    GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
    GEOMETRY_REALIZATION_STATUS_STALE_PARENT,
    GEOMETRY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY,
    READINESS_STATUS_READY,
    STRATEGY_APPLICABILITY_APPLICABLE,
    dumps_contract,
    loads_contract,
)
from core.architecture.reasoning.architectural_change_space_geometry_realizer_v1 import (
    candidate_semantic_hash,
    realize_selected_space_geometry_strategy,
)


def _space(space_id, polygon, *, minimum_area=None, required=True):
    geometry = Polygon(polygon)
    value = {
        "space_id": space_id,
        "floor": "R1",
        "polygon": [list(point) for point in geometry.exterior.coords],
        "area_m2": geometry.area,
        "perimeter_m": geometry.length,
        "centroid": [geometry.centroid.x, geometry.centroid.y],
        "interior_point": [geometry.representative_point().x, geometry.representative_point().y],
        "boundary_ids": [],
        "required": required,
    }
    if minimum_area is not None:
        value["minimum_area_m2"] = minimum_area
    return value


def _candidate():
    value = {
        "candidate_id": "candidate-space-boundary-01",
        "candidate_version": "7",
        "space_boundary_graphs": {
            "R1": {
                "floor": "R1",
                "spaces": [
                    _space("space:kitchen", [[0, 0], [2, 0], [2, 4], [0, 4]], minimum_area=8),
                    _space("space:living", [[2, 0], [6, 0], [6, 4], [2, 4]], minimum_area=10),
                    _space("space:private_hall", [[0, 4], [6, 4], [6, 5], [0, 5]], minimum_area=5),
                ],
                "virtual_closures": [],
                "unresolved": [],
            }
        },
        "access_graph": {
            "status": "RESOLVED",
            "nodes": [
                {"id": "space:kitchen", "floor": "R1"},
                {"id": "space:living", "floor": "R1"},
                {"id": "space:private_hall", "floor": "R1"},
            ],
            "edges": [
                {"edge_id": "door:kitchen-hall", "from": "space:kitchen", "to": "space:private_hall", "kind": "DOOR_PORTAL"},
                {"edge_id": "door:living-hall", "from": "space:living", "to": "space:private_hall", "kind": "DOOR_PORTAL"},
            ],
        },
        "hard_constraints": [{"constraint_id": "program_complete", "severity": "hard"}],
        "protected_constraints": [],
        "satisfied_prerequisites": [],
    }
    value["candidate_hash"] = candidate_semantic_hash(value)
    return value


def _strategy(*, strategy_type="ADJACENT_AREA_TRANSFER", transfer=None, increase=4.0):
    evidence = {
        "execution_family": "SPACE_BOUNDARY_REALIZATION",
        "operation": "AREA_TRANSFER",
        "target_space_id": "space:kitchen",
        "source_space_id": "space:living",
        "transfer_polygon": transfer or [[2, 0], [3, 0], [3, 4], [2, 4]],
        "increase_area_m2": increase,
    }
    return ArchitecturalChangeStrategy(
        strategy_id=f"plan-kitchen:strategy:{strategy_type.lower()}",
        plan_id="plan-kitchen",
        strategy_type=strategy_type,
        target_entities=("space:kitchen",),
        proposed_semantic_actions=("increase_space_area(kitchen)", "transfer_adjacent_available_area"),
        required_tradeoffs=("adjacent_space_area_and_usability",),
        preserved_constraints=("circulation_continuity", "living_usability", "target_access"),
        prerequisites=(),
        expected_impacts=("increased_kitchen_capacity",),
        risks=("insufficient_transferable_area",),
        required_rechecks=("access", "circulation", "openings"),
        applicability_status=STRATEGY_APPLICABILITY_APPLICABLE,
        evidence=("shared_boundary_verified",),
        provenance={"phase": "01E", "area_transfer": evidence},
    )


def _readiness():
    return ExecutionReadinessResult(
        plan_id="plan-kitchen",
        readiness_status=READINESS_STATUS_READY,
        unresolved_dependencies=(),
        constraint_conflicts=(),
        preservation_requirements=("circulation_continuity",),
        required_checks_before_execution=("geometry_validity",),
        rejection_reasons=(),
        evidence=("resolved_space_boundary_graph",),
    )


def _run(candidate=None, strategy=None, **expected):
    candidate = candidate or _candidate()
    parent_id = expected.pop("expected_parent_id", candidate["candidate_id"])
    parent_version = expected.pop("expected_parent_version", candidate["candidate_version"])
    parent_hash = expected.pop("expected_parent_hash", candidate_semantic_hash(candidate))
    return realize_selected_space_geometry_strategy(
        strategy or _strategy(), _readiness(), candidate,
        expected_parent_id=parent_id,
        expected_parent_version=parent_version,
        expected_parent_hash=parent_hash,
        **expected,
    )


def _spaces(candidate):
    return {item["space_id"]: item for item in candidate["space_boundary_graphs"]["R1"]["spaces"]}


def test_kitchen_area_transfer_commits_new_derived_candidate_and_auditable_delta():
    parent = _candidate()
    derived, result = _run(parent)

    assert result.status == GEOMETRY_REALIZATION_STATUS_REALIZED
    assert derived is not None and derived is not parent
    assert derived["parent_candidate_id"] == parent["candidate_id"]
    assert derived["candidate_id"] == result.derived_candidate_id
    assert result.parent_hash == candidate_semantic_hash(parent)
    assert result.derived_hash == candidate_semantic_hash(derived)
    assert result.applied_operations == ("AREA_TRANSFER",)
    assert len(result.geometry_changes) == 2
    changes = {item.space_id: item for item in result.geometry_changes}
    assert changes["space:kitchen"].before_area == 8
    assert changes["space:kitchen"].after_area == 12
    assert changes["space:living"].before_area == 16
    assert changes["space:living"].after_area == 12
    assert changes["space:kitchen"].before_geometry["contract"] == "SpacePolygon"
    assert changes["space:kitchen"].affected_neighbors == ("space:living",)


def test_parent_is_byte_and_semantically_equivalent_before_and_after_success():
    parent = _candidate()
    before = deepcopy(parent)
    before_bytes = json.dumps(parent, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    before_hash = candidate_semantic_hash(parent)

    derived, _ = _run(parent)

    assert derived is not None
    assert parent == before
    assert json.dumps(parent, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() == before_bytes
    assert candidate_semantic_hash(parent) == before_hash


def test_changed_polygons_are_valid_non_overlapping_and_preserve_unrelated_space():
    parent = _candidate()
    derived, result = _run(parent)
    spaces = _spaces(derived)
    polygons = {key: Polygon(value["polygon"]) for key, value in spaces.items()}

    assert all(polygon.is_valid and polygon.is_simple and polygon.area > 0 for polygon in polygons.values())
    assert all(
        first.intersection(second).area == 0
        for index, first in enumerate(polygons.values())
        for second in list(polygons.values())[index + 1:]
    )
    assert spaces["space:private_hall"] == _spaces(parent)["space:private_hall"]
    assert result.preserved_entities == ("space:private_hall",)
    assert all(check["passed"] is True for check in result.geometry_checks)


def test_result_is_deterministic_and_contract_round_trips_stably():
    first_derived, first = _run()
    second_derived, second = _run()

    assert first_derived == second_derived
    assert first == second
    assert dumps_contract(first) == dumps_contract(second)
    assert loads_contract(dumps_contract(first)) == first
    for delta in first.geometry_changes:
        assert loads_contract(dumps_contract(delta)) == delta


def test_stale_parent_identity_version_or_hash_is_rejected_without_clone():
    parent = _candidate()
    derived, result = _run(parent, expected_parent_hash="0" * 64)

    assert derived is None
    assert result.status == GEOMETRY_REALIZATION_STATUS_STALE_PARENT
    assert result.geometry_changes == ()
    assert result.provenance["commit"] is False


def test_protected_or_hard_constrained_transfer_space_is_rejected():
    parent = _candidate()
    parent["protected_constraints"] = [
        {"constraint_id": "living_boundary_fixed", "entity_id": "space:living", "protected": True}
    ]
    parent["candidate_hash"] = candidate_semantic_hash(parent)
    derived, result = _run(parent)

    assert derived is None
    assert result.status == GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT
    assert "protected_or_hard_constrained_space_boundary" in result.failures


def test_adjacency_and_daylight_strategy_families_are_unsupported_and_create_no_geometry():
    for strategy_type in ("DIRECT_PRIVATE_RELATIONSHIP", "DAYLIGHT_EXPOSURE_RELATIONSHIP"):
        derived, result = _run(strategy=_strategy(strategy_type=strategy_type))
        assert derived is None
        assert result.status == GEOMETRY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY
        assert result.geometry_changes == ()


def test_missing_explicit_transfer_evidence_is_rejected_without_guessing():
    base = _strategy()
    strategy = ArchitecturalChangeStrategy(**{
        **base.__dict__,
        "provenance": {"phase": "01E"},
    })
    derived, result = _run(strategy=strategy)

    assert derived is None
    assert result.status == GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY
    assert result.failures == ("insufficient_area_transfer_execution_evidence",)


def test_insufficient_transferable_geometry_rejects_required_space_deletion():
    whole_donor = [[2, 0], [6, 0], [6, 4], [2, 4]]
    derived, result = _run(strategy=_strategy(transfer=whole_donor, increase=16.0))

    assert derived is None
    assert result.status == GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY
    assert result.geometry_changes == ()
    assert "area_transfer_would_fragment_or_delete_space" in result.failures


def test_failed_geometry_gate_rolls_back_and_parent_remains_unchanged():
    parent = _candidate()
    before = deepcopy(parent)
    invalid_bow_tie = [[2, 0], [3, 4], [3, 0], [2, 4]]
    derived, result = _run(parent, strategy=_strategy(transfer=invalid_bow_tie, increase=4.0))

    assert derived is None
    assert result.status == GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY
    assert result.provenance["commit"] is False
    assert parent == before


def test_minimum_area_and_access_preservation_constraints_are_enforced():
    parent = _candidate()
    _spaces(parent)["space:living"]["minimum_area_m2"] = 13
    parent["candidate_hash"] = candidate_semantic_hash(parent)
    derived, result = _run(parent)

    assert derived is None
    assert result.status == GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT
    assert result.failures == ("minimum_area_violated:space:living",)
