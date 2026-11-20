"""ARCHITECTURAL-CHANGE-ORCHESTRATOR-01F-C acceptance tests."""
from __future__ import annotations

from copy import deepcopy
import json

from shapely.geometry import LineString, Polygon

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeStrategy,
    ExecutionReadinessResult,
    OPENING_ACCESS_REALIZATION_STATUS_REALIZED,
    OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS,
    OPENING_ACCESS_REALIZATION_STATUS_REJECTED_CONSTRAINT,
    OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
    OPENING_ACCESS_REALIZATION_STATUS_STALE_PARENT,
    OPENING_ACCESS_REALIZATION_STATUS_UNSUPPORTED_STRATEGY,
    READINESS_STATUS_READY,
    STRATEGY_APPLICABILITY_APPLICABLE,
    dumps_contract,
    loads_contract,
)
from core.architecture.reasoning.architectural_change_opening_access_realizer_v1 import (
    realize_selected_opening_access_strategy,
)
from core.architecture.reasoning.architectural_change_space_geometry_realizer_v1 import (
    candidate_semantic_hash,
)


def _space(space_id, polygon, *, circulation_role=None):
    geometry = Polygon(polygon)
    record = {
        "space_id": space_id,
        "floor": "R1",
        "polygon": [list(point) for point in geometry.exterior.coords],
        "area_m2": geometry.area,
        "required": True,
    }
    if circulation_role:
        record["circulation_role"] = circulation_role
    return record


def _portal(opening_id, side_a, side_b, points):
    width = LineString(points).length
    return {
        "opening_id": opening_id,
        "floor": "R1",
        "kind": "DOOR",
        "constituent_source_handles": [],
        "host_wall_pair_id": f"boundary:{side_a}:{side_b}",
        "host_face_a": None,
        "host_face_b": None,
        "threshold": points,
        "centerline": points,
        "clear_width_m": width,
        "side_a": side_a,
        "side_b": side_b,
        "traversable": True,
        "exposure": "INTERIOR",
        "confidence": 1.0,
        "geometric_evidence": {"source": "fixture"},
        "status": "RESOLVED",
    }


def _candidate():
    spaces = [
        _space("space:master", [[0, 0], [4, 0], [4, 4], [0, 4]]),
        _space("space:bathroom", [[4, 0], [6, 0], [6, 4], [4, 4]]),
        _space("space:private_hall", [[0, 4], [6, 4], [6, 5], [0, 5]], circulation_role="PRIVATE_CIRCULATION"),
    ]
    portals = [
        _portal("portal:master-hall", "space:master", "space:private_hall", [[1, 4], [2, 4]]),
        _portal("portal:bath-hall", "space:bathroom", "space:private_hall", [[4.5, 4], [5.5, 4]]),
    ]
    value = {
        "candidate_id": "candidate-private-suite-01f-c",
        "candidate_version": "10",
        "space_boundary_graphs": {"R1": {"floor": "R1", "spaces": spaces, "virtual_closures": [], "unresolved": []}},
        "opening_host_graphs": {"R1": {"floor": "R1", "openings": portals, "unresolved": []}},
        "access_graph": {
            "status": "RESOLVED",
            "nodes": [
                {"id": "space:master", "semantic_class": "BEDROOM"},
                {"id": "space:bathroom", "semantic_class": "BATHROOM"},
                {"id": "space:private_hall", "semantic_class": "CIRCULATION"},
            ],
            "edges": [
                {"edge_id": "portal:master-hall", "from": "space:master", "to": "space:private_hall", "kind": "DOOR_PORTAL"},
                {"edge_id": "portal:bath-hall", "from": "space:bathroom", "to": "space:private_hall", "kind": "DOOR_PORTAL"},
            ],
        },
        "hard_constraints": [{"constraint_id": "program_complete", "severity": "hard"}],
        "protected_constraints": [],
        "satisfied_prerequisites": [],
    }
    value["candidate_hash"] = candidate_semantic_hash(value)
    return value


def _strategy(*, strategy_type="PRIVATE_ACCESS_REALIZATION", operation="CREATE_DIRECT_ACCESS_INTERFACE", evidence=True):
    realization = {
        "execution_family": "OPENING_ACCESS_REALIZATION",
        "operation": operation,
        "interface_id": "portal:master-private-bath",
        "target_space_pair": ["space:master", "space:bathroom"],
        "shared_boundary_ref": "shared-boundary:master:bathroom",
        "boundary_segment": [[4, 0], [4, 4]],
        "width_m": 1.0,
        "width_source": "explicit_strategy_requirement:clear_width_m",
        "position_fraction": 0.5,
        "position_source": "explicit_strategy_evidence:position_fraction",
        "reason": "realize_direct_private_access_on_proved_shared_boundary",
    }
    return ArchitecturalChangeStrategy(
        strategy_id="plan-master-bath:strategy:private-access",
        plan_id="plan-master-bath",
        strategy_type=strategy_type,
        target_entities=("space:master", "space:bathroom"),
        proposed_semantic_actions=("create_direct_private_access_interface",),
        required_tradeoffs=("private_zone_relationships",),
        preserved_constraints=("privacy", "circulation_continuity", "target_access"),
        prerequisites=(),
        expected_impacts=("direct_private_access",),
        risks=("opening_collision", "circulation_blockage"),
        required_rechecks=("privacy", "circulation", "access"),
        applicability_status=STRATEGY_APPLICABILITY_APPLICABLE,
        evidence=("proved_shared_boundary", "explicit_opening_width_and_position"),
        provenance={"phase": "01E", **({"opening_access_realization": realization} if evidence else {})},
    )


def _readiness():
    return ExecutionReadinessResult(
        plan_id="plan-master-bath",
        readiness_status=READINESS_STATUS_READY,
        unresolved_dependencies=(),
        constraint_conflicts=(),
        preservation_requirements=("circulation_continuity", "target_access"),
        required_checks_before_execution=("opening_geometry", "access", "circulation"),
        rejection_reasons=(),
        evidence=("resolved_space_boundary_graph", "resolved_opening_host_graph", "resolved_access_graph"),
    )


def _run(candidate=None, strategy=None, readiness=None, **expected):
    candidate = candidate or _candidate()
    return realize_selected_opening_access_strategy(
        strategy or _strategy(), readiness or _readiness(), candidate,
        expected_parent_id=expected.get("expected_parent_id", candidate["candidate_id"]),
        expected_parent_version=expected.get("expected_parent_version", candidate["candidate_version"]),
        expected_parent_hash=expected.get("expected_parent_hash", candidate_semantic_hash(candidate)),
    )


def _opening(candidate, opening_id="portal:master-private-bath"):
    return next(item for item in candidate["opening_host_graphs"]["R1"]["openings"] if item["opening_id"] == opening_id)


def _edge(candidate, edge_id="portal:master-private-bath"):
    return next(item for item in candidate["access_graph"]["edges"] if item["edge_id"] == edge_id)


def test_successful_opening_access_realization_is_geometric_and_semantically_bound():
    derived, result = _run()
    assert derived is not None and result.status == OPENING_ACCESS_REALIZATION_STATUS_REALIZED
    opening = _opening(derived)
    edge = _edge(derived)
    assert opening["centerline"] == [[4.0, 1.5], [4.0, 2.5]]
    assert {opening["side_a"], opening["side_b"]} == {"space:master", "space:bathroom"}
    assert {edge["from"], edge["to"]} == {"space:master", "space:bathroom"}
    assert edge["opening_binding"] == opening["opening_id"]
    delta = result.opening_access_changes[0]
    assert delta.before_interface is None and delta.after_interface["centerline"] == opening["centerline"]
    assert delta.source_of_width.startswith("explicit_strategy_requirement")


def test_parent_is_byte_and_semantically_unchanged_and_child_identity_is_new():
    parent = _candidate()
    before = json.dumps(parent, sort_keys=True, separators=(",", ":"))
    before_hash = candidate_semantic_hash(parent)
    derived, result = _run(parent)
    assert json.dumps(parent, sort_keys=True, separators=(",", ":")) == before
    assert candidate_semantic_hash(parent) == before_hash == result.parent_hash
    assert derived is not parent and derived["parent_candidate_id"] == parent["candidate_id"]
    assert result.derived_hash == candidate_semantic_hash(derived)


def test_opening_is_inside_actual_shared_boundary_without_overlap_or_corner_collision():
    derived, result = _run()
    line = LineString(_opening(derived)["centerline"])
    master = Polygon(derived["space_boundary_graphs"]["R1"]["spaces"][0]["polygon"])
    bath = Polygon(derived["space_boundary_graphs"]["R1"]["spaces"][1]["polygon"])
    shared = master.boundary.intersection(bath.boundary)
    assert line.difference(shared).is_empty and line.boundary.distance(shared.boundary) > 0
    assert all(item["passed"] for item in result.geometry_checks)


def test_access_graph_and_circulation_are_preserved_and_no_bim_object_is_created():
    derived, result = _run()
    assert len(derived["access_graph"]["edges"]) == 3
    assert all(item["passed"] for item in result.access_checks + result.circulation_checks)
    assert not any(key in derived for key in ("bim_doors", "doors", "door_objects", "windows", "window_objects"))
    assert result.provenance["physical_bim_object_created"] is False


def test_deterministic_result_and_contract_round_trip():
    first_candidate, first = _run()
    second_candidate, second = _run()
    assert first_candidate == second_candidate and first == second
    assert loads_contract(dumps_contract(first)) == first
    assert dumps_contract(loads_contract(dumps_contract(first))) == dumps_contract(first)


def test_stale_parent_hash_rejected_without_child():
    derived, result = _run(expected_parent_hash="stale")
    assert derived is None and result.status == OPENING_ACCESS_REALIZATION_STATUS_STALE_PARENT
    assert result.opening_access_changes == () and result.derived_hash is None


def test_protected_wall_or_interface_rejected():
    parent = _candidate()
    parent["protected_constraints"] = [{
        "constraint_id": "protected-master-bath-wall",
        "severity": "hard",
        "protected": True,
        "boundary_ref": "shared-boundary:master:bathroom",
    }]
    parent["candidate_hash"] = candidate_semantic_hash(parent)
    derived, result = _run(parent)
    assert derived is None and result.status == OPENING_ACCESS_REALIZATION_STATUS_REJECTED_CONSTRAINT


def test_area_topology_and_daylight_strategy_families_are_unsupported():
    for strategy_type in ("AREA_TRANSFER", "STRENGTHEN_ADJACENCY", "DAYLIGHT_WINDOW_REALIZATION"):
        derived, result = _run(strategy=_strategy(strategy_type=strategy_type))
        assert derived is None and result.status == OPENING_ACCESS_REALIZATION_STATUS_UNSUPPORTED_STRATEGY


def test_missing_width_or_position_evidence_is_rejected_without_guessing():
    for missing in ("width_m", "position_fraction"):
        strategy = _strategy()
        evidence = strategy.provenance["opening_access_realization"]
        evidence.pop(missing)
        derived, result = _run(strategy=strategy)
        assert derived is None and result.status == OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY


def test_non_shared_boundary_is_rejected():
    strategy = _strategy()
    strategy.provenance["opening_access_realization"]["target_space_pair"] = ["space:master", "space:private_hall"]
    strategy.provenance["opening_access_realization"]["boundary_segment"] = [[4, 0], [4, 4]]
    strategy = ArchitecturalChangeStrategy(**{
        **strategy.__dict__, "target_entities": ("space:master", "space:private_hall")
    })
    derived, result = _run(strategy=strategy)
    assert derived is None and result.status == OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY


def test_overlap_and_corner_collision_are_rejected():
    overlap = _candidate()
    overlap["opening_host_graphs"]["R1"]["openings"].append(
        _portal("portal:existing-shared", "space:master", "space:bathroom", [[4, 1.75], [4, 2.25]])
    )
    overlap["candidate_hash"] = candidate_semantic_hash(overlap)
    derived, result = _run(overlap)
    assert derived is None and result.status == OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY

    corner_strategy = _strategy()
    corner_strategy.provenance["opening_access_realization"]["position_fraction"] = 0.125
    derived, result = _run(strategy=corner_strategy)
    assert derived is None and result.status == OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY


def test_failed_access_gate_rolls_back_all_opening_and_edge_changes():
    parent = _candidate()
    parent["access_graph"]["edges"] = []
    parent["candidate_hash"] = candidate_semantic_hash(parent)
    before = deepcopy(parent)
    derived, result = _run(parent)
    assert derived is None and result.status == OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS
    assert parent == before
    assert not any(item["opening_id"] == "portal:master-private-bath" for item in parent["opening_host_graphs"]["R1"]["openings"])


def test_relocate_and_rebind_existing_portal_keep_geometry_and_access_consistent():
    parent = _candidate()
    parent["opening_host_graphs"]["R1"]["openings"].append(
        _portal("portal:master-private-bath", "space:master", "space:bathroom", [[4, 0.75], [4, 1.75]])
    )
    parent["access_graph"]["edges"].append({
        "edge_id": "portal:master-private-bath", "from": "space:master", "to": "space:bathroom", "kind": "DOOR_PORTAL"
    })
    parent["candidate_hash"] = candidate_semantic_hash(parent)
    relocate = _strategy(operation="RELOCATE_ACCESS_INTERFACE")
    derived, result = _run(parent, relocate)
    assert result.status == OPENING_ACCESS_REALIZATION_STATUS_REALIZED
    assert _opening(derived)["centerline"] == [[4.0, 1.5], [4.0, 2.5]]
    assert result.opening_access_changes[0].before_interface["centerline"] == [[4, 0.75], [4, 1.75]]

    rebind_parent = deepcopy(parent)
    rebind_strategy = _strategy(operation="REBIND_EXISTING_PORTAL")
    evidence = rebind_strategy.provenance["opening_access_realization"]
    evidence.pop("width_m")
    evidence.pop("position_fraction")
    evidence.pop("width_source")
    evidence.pop("position_source")
    derived, result = _run(rebind_parent, rebind_strategy)
    assert result.status == OPENING_ACCESS_REALIZATION_STATUS_REALIZED
    assert _opening(derived)["centerline"] == [[4.0, 0.75], [4.0, 1.75]]


def test_missing_canonical_graph_or_incomplete_existing_binding_is_rejected():
    parent = _candidate()
    parent.pop("opening_host_graphs")
    parent["candidate_hash"] = candidate_semantic_hash(parent)
    derived, result = _run(parent)
    assert derived is None and result.status == OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS

    parent = _candidate()
    strategy = _strategy(operation="REBIND_EXISTING_PORTAL")
    derived, result = _run(parent, strategy)
    assert derived is None and result.status == OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS
