"""ARCHITECTURAL-CHANGE-ORCHESTRATOR-01F-B acceptance tests."""
from __future__ import annotations

from copy import deepcopy
import json

from shapely.geometry import Polygon

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeStrategy,
    ExecutionReadinessResult,
    READINESS_STATUS_READY,
    STRATEGY_APPLICABILITY_APPLICABLE,
    TOPOLOGY_REALIZATION_STATUS_REALIZED,
    TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT,
    TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY,
    TOPOLOGY_REALIZATION_STATUS_STALE_PARENT,
    TOPOLOGY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY,
    dumps_contract,
    loads_contract,
)
from core.architecture.reasoning.architectural_change_adjacency_topology_realizer_v1 import (
    realize_selected_adjacency_topology_strategy,
)
from core.architecture.reasoning.architectural_change_space_geometry_realizer_v1 import (
    candidate_semantic_hash,
)


def _space(space_id, polygon, *, required=True, circulation_role=None):
    geometry = Polygon(polygon)
    value = {
        "space_id": space_id,
        "floor": "R1",
        "polygon": [list(point) for point in geometry.exterior.coords],
        "area_m2": geometry.area,
        "perimeter_m": geometry.length,
        "centroid": [geometry.centroid.x, geometry.centroid.y],
        "interior_point": [geometry.representative_point().x, geometry.representative_point().y],
        "boundary_ids": [f"boundary:{space_id}"],
        "minimum_area_m2": geometry.area,
        "minimum_width_m": min(geometry.bounds[2] - geometry.bounds[0], geometry.bounds[3] - geometry.bounds[1]),
        "required": required,
    }
    if circulation_role:
        value["circulation_role"] = circulation_role
    return value


def _candidate():
    value = {
        "candidate_id": "candidate-private-suite-01",
        "candidate_version": "9",
        "space_boundary_graphs": {
            "R1": {
                "floor": "R1",
                "spaces": [
                    _space("space:master", [[0, 0], [4, 0], [4, 4], [0, 4]]),
                    _space("space:guest_bath", [[4, 0], [6, 0], [6, 2], [4, 2]]),
                    _space("space:storage", [[4, 2], [6, 2], [6, 4], [4, 4]]),
                    _space("space:bathroom", [[6, 0], [8, 0], [8, 2], [6, 2]]),
                    _space("space:closet", [[6, 2], [8, 2], [8, 4], [6, 4]]),
                    _space("space:private_hall", [[0, 4], [8, 4], [8, 5], [0, 5]], circulation_role="PRIVATE_CIRCULATION"),
                ],
                "virtual_closures": [],
                "unresolved": [],
            }
        },
        "access_graph": {
            "status": "RESOLVED",
            "nodes": [
                {"id": "space:master", "semantic_class": "BEDROOM"},
                {"id": "space:guest_bath", "semantic_class": "BATHROOM"},
                {"id": "space:bathroom", "semantic_class": "BATHROOM"},
                {"id": "space:storage", "semantic_class": "STORAGE"},
                {"id": "space:closet", "semantic_class": "CLOSET"},
                {"id": "space:private_hall", "semantic_class": "CIRCULATION"},
            ],
            "edges": [
                {"edge_id": "portal:master-hall", "from": "space:master", "to": "space:private_hall", "kind": "DOOR_PORTAL"},
                {"edge_id": "portal:guest-master", "from": "space:guest_bath", "to": "space:master", "kind": "DOOR_PORTAL"},
                {"edge_id": "portal:bath-guest", "from": "space:bathroom", "to": "space:guest_bath", "kind": "DOOR_PORTAL"},
                {"edge_id": "portal:storage-hall", "from": "space:storage", "to": "space:private_hall", "kind": "DOOR_PORTAL"},
                {"edge_id": "portal:closet-hall", "from": "space:closet", "to": "space:private_hall", "kind": "DOOR_PORTAL"},
            ],
        },
        "opening_host_graphs": {
            "R1": {
                "floor": "R1",
                "openings": [
                    {"opening_id": "portal:guest-master", "kind": "DOOR", "side_a": "space:guest_bath", "side_b": "space:master"},
                    {"opening_id": "portal:bath-guest", "kind": "DOOR", "side_a": "space:bathroom", "side_b": "space:guest_bath"},
                ],
                "unresolved": [],
            }
        },
        "hard_constraints": [{"constraint_id": "program_complete", "severity": "hard"}],
        "protected_constraints": [],
        "satisfied_prerequisites": [],
    }
    value["candidate_hash"] = candidate_semantic_hash(value)
    return value


def _strategy(*, strategy_type="DIRECT_PRIVATE_RELATIONSHIP", evidence=True):
    topology = {
        "execution_family": "ADJACENCY_TOPOLOGY_REALIZATION",
        "operation": "PERMUTE_EXISTING_SPACE_GEOMETRY",
        "relation_id": "relation:master-private-bath",
        "target_space_id": "space:master",
        "desired_adjacent_space_id": "space:bathroom",
        "relocation_space_id": "space:guest_bath",
        "allowed_affected_spaces": ["space:master", "space:bathroom", "space:guest_bath", "space:storage", "space:closet"],
        "minimum_shared_boundary_m": 1.5,
        "reason": "swap_equal_service_cells_to_realize_private_adjacency",
    }
    return ArchitecturalChangeStrategy(
        strategy_id=f"plan-master-bath:strategy:{strategy_type.lower()}",
        plan_id="plan-master-bath",
        strategy_type=strategy_type,
        target_entities=("space:master", "space:bathroom"),
        proposed_semantic_actions=("strengthen_master_bath_adjacency", "prioritize_private_access_relationship"),
        required_tradeoffs=("private_zone_relationships",),
        preserved_constraints=("privacy", "circulation_continuity", "target_access"),
        prerequisites=(),
        expected_impacts=("stronger_master_bath_adjacency",),
        risks=("privacy_transition_conflict", "circulation_overlap"),
        required_rechecks=("privacy", "circulation", "access", "adjacency"),
        applicability_status=STRATEGY_APPLICABILITY_APPLICABLE,
        evidence=("existing_equal_service_cells", "existing_portal_topology"),
        provenance={"phase": "01E", **({"topology_realization": topology} if evidence else {})},
    )


def _readiness():
    return ExecutionReadinessResult(
        plan_id="plan-master-bath",
        readiness_status=READINESS_STATUS_READY,
        unresolved_dependencies=(),
        constraint_conflicts=(),
        preservation_requirements=("circulation_continuity", "target_access"),
        required_checks_before_execution=("topology", "access"),
        rejection_reasons=(),
        evidence=("resolved_space_boundary_graph", "resolved_access_graph"),
    )


def _run(candidate=None, strategy=None, readiness=None, **expected):
    candidate = candidate or _candidate()
    return realize_selected_adjacency_topology_strategy(
        strategy or _strategy(), readiness or _readiness(), candidate,
        expected_parent_id=expected.get("expected_parent_id", candidate["candidate_id"]),
        expected_parent_version=expected.get("expected_parent_version", candidate["candidate_version"]),
        expected_parent_hash=expected.get("expected_parent_hash", candidate_semantic_hash(candidate)),
    )


def _spaces(candidate):
    return {item["space_id"]: item for item in candidate["space_boundary_graphs"]["R1"]["spaces"]}


def _shared(candidate, first, second):
    spaces = _spaces(candidate)
    return Polygon(spaces[first]["polygon"]).boundary.intersection(Polygon(spaces[second]["polygon"]).boundary).length


def _opening_ids(candidate):
    return tuple(item["opening_id"] for item in candidate["opening_host_graphs"]["R1"]["openings"])


def test_successful_adjacency_topology_realization_records_physical_before_after_delta():
    parent = _candidate()
    derived, result = _run(parent)

    assert derived is not None and derived is not parent
    assert result.status == TOPOLOGY_REALIZATION_STATUS_REALIZED
    assert _shared(parent, "space:master", "space:bathroom") == 0
    assert _shared(derived, "space:master", "space:bathroom") == 2
    delta = result.topology_changes[0]
    assert delta.relation_id == "relation:master-private-bath"
    assert delta.before_relation["satisfied"] is False
    assert delta.after_relation["satisfied"] is True
    assert delta.after_relation["shared_boundary_m"] == 2
    assert result.applied_operations == ("PERMUTE_EXISTING_SPACE_GEOMETRY",)
    assert all(check["passed"] is True for check in result.topology_checks)
    assert all(check["passed"] is True for check in result.access_checks)


def test_parent_is_byte_and_semantically_equivalent_before_and_after_commit():
    parent = _candidate()
    before = deepcopy(parent)
    before_bytes = json.dumps(parent, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    before_hash = candidate_semantic_hash(parent)

    derived, _ = _run(parent)

    assert derived is not None
    assert parent == before
    assert json.dumps(parent, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() == before_bytes
    assert candidate_semantic_hash(parent) == before_hash


def test_geometry_access_and_circulation_are_valid_and_no_opening_is_created():
    parent = _candidate()
    derived, result = _run(parent)
    spaces = _spaces(derived)
    polygons = {space_id: Polygon(record["polygon"]) for space_id, record in spaces.items()}

    assert all(polygon.is_valid and polygon.is_simple and polygon.area > 0 for polygon in polygons.values())
    assert all(first.intersection(second).area == 0 for index, first in enumerate(polygons.values()) for second in list(polygons.values())[index + 1:])
    assert _opening_ids(derived) == _opening_ids(parent)
    assert len(derived["access_graph"]["edges"]) == len(parent["access_graph"]["edges"])
    assert not any(item.get("kind") == "WINDOW" for item in derived["opening_host_graphs"]["R1"]["openings"])
    assert "space:private_hall" in result.topology_changes[0].affected_circulation


def test_result_is_deterministic_and_contracts_round_trip_stably():
    first_derived, first = _run()
    second_derived, second = _run()

    assert first_derived == second_derived
    assert first == second
    assert loads_contract(dumps_contract(first)) == first
    assert loads_contract(dumps_contract(first.topology_changes[0])) == first.topology_changes[0]


def test_stale_parent_hash_is_rejected_without_derived_candidate():
    derived, result = _run(expected_parent_hash="0" * 64)

    assert derived is None
    assert result.status == TOPOLOGY_REALIZATION_STATUS_STALE_PARENT
    assert result.topology_changes == ()
    assert result.provenance["commit"] is False


def test_protected_entity_and_mandatory_adjacency_are_rejected():
    entity_parent = _candidate()
    entity_parent["protected_constraints"] = [{"constraint_id": "bath_fixed", "entity_id": "space:bathroom", "protected": True}]
    entity_parent["candidate_hash"] = candidate_semantic_hash(entity_parent)
    derived, result = _run(entity_parent)
    assert derived is None and result.status == TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT

    relation_parent = _candidate()
    relation_parent["protected_constraints"] = [{"constraint_id": "guest_master", "relation_pair": ["space:master", "space:guest_bath"], "protected": True}]
    relation_parent["candidate_hash"] = candidate_semantic_hash(relation_parent)
    derived, result = _run(relation_parent)
    assert derived is None and result.status == TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT
    assert result.failures == ("protected_mandatory_adjacency_would_be_lost",)


def test_space_transfer_daylight_and_opening_strategy_families_are_unsupported():
    for strategy_type in ("ADJACENT_AREA_TRANSFER", "DAYLIGHT_EXPOSURE_RELATIONSHIP", "CREATE_DOOR_OPENING"):
        derived, result = _run(strategy=_strategy(strategy_type=strategy_type))
        assert derived is None
        assert result.status == TOPOLOGY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY
        assert result.topology_changes == ()


def test_insufficient_topology_evidence_is_structured_rejection_not_label_success():
    derived, result = _run(strategy=_strategy(evidence=False))

    assert derived is None
    assert result.status == TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY
    assert result.failures == ("insufficient_topology_execution_evidence",)


def test_failed_topology_gate_rolls_back_without_parent_mutation():
    parent = _candidate()
    before = deepcopy(parent)
    strategy = _strategy()
    evidence = dict(strategy.provenance["topology_realization"])
    evidence["relocation_space_id"] = "space:closet"
    strategy = ArchitecturalChangeStrategy(**{**strategy.__dict__, "provenance": {"phase": "01E", "topology_realization": evidence}})

    derived, result = _run(parent, strategy=strategy)

    assert derived is None
    assert result.status == TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY
    assert parent == before
    assert result.provenance["commit"] is False


def test_failed_access_gate_rejects_and_rolls_back_without_parent_mutation():
    parent = _candidate()
    parent["access_graph"]["edges"] = [edge for edge in parent["access_graph"]["edges"] if "bath" not in edge["edge_id"]]
    parent["candidate_hash"] = candidate_semantic_hash(parent)
    before = deepcopy(parent)

    derived, result = _run(parent)

    assert derived is None
    assert result.status == TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT
    assert any("parent_access_invalid:sealed_required_space:space:bathroom" == item for item in result.failures)
    assert parent == before


def test_minimum_area_dimension_gate_rejects_swap_transactionally():
    parent = _candidate()
    _spaces(parent)["space:bathroom"]["minimum_width_m"] = 2.5
    parent["candidate_hash"] = candidate_semantic_hash(parent)

    derived, result = _run(parent)

    assert derived is None
    assert result.status == TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT
    assert result.failures == ("minimum_dimension_violated:space:bathroom",)
