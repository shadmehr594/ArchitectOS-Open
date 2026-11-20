"""ARCHITECTURAL-CHANGE-ORCHESTRATOR-01G end-to-end acceptance."""
from __future__ import annotations

from copy import deepcopy
import json

from shapely.geometry import LineString, Polygon

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeIntent,
    MultiRealizerTransactionPlan,
    READINESS_STATUS_BLOCKED_CONSTRAINT,
    READINESS_STATUS_READY,
    STRATEGY_GENERATION_STATUS_BLOCKED_READINESS,
    STRATEGY_GENERATION_STATUS_GENERATED,
    TRANSACTION_STATUS_COMMITTED,
    TRANSACTION_STATUS_REJECTED_STEP_FAILURE,
    TRANSACTION_STATUS_UNSUPPORTED_STRATEGY_SEQUENCE,
    dumps_contract,
    loads_contract,
)
from core.architecture.reasoning.architectural_change_impact_analyzer_v1 import (
    analyze_architectural_change_impact,
)
from core.architecture.reasoning.architectural_change_multi_realizer_transaction_coordinator_v1 import (
    execute_multi_realizer_transaction,
)
from core.architecture.reasoning.architectural_change_planner_v1 import (
    plan_architectural_change,
)
from core.architecture.reasoning.architectural_change_readiness_validator_v1 import (
    validate_declarative_plan_readiness,
)
from core.architecture.reasoning.architectural_change_selected_strategy_transaction_adapter_v1 import (
    prepare_explicitly_selected_transaction,
)
from core.architecture.reasoning.architectural_change_space_geometry_realizer_v1 import (
    candidate_semantic_hash,
)
from core.architecture.reasoning.architectural_change_strategy_generator_v1 import (
    generate_architectural_change_strategies,
)


def _space(space_id, polygon, *, minimum_area=None, circulation_role=None):
    geometry = Polygon(polygon)
    value = {
        "space_id": space_id,
        "floor": "R1",
        "polygon": [list(point) for point in geometry.exterior.coords],
        "area_m2": geometry.area,
        "perimeter_m": geometry.length,
        "centroid": [geometry.centroid.x, geometry.centroid.y],
        "interior_point": [
            geometry.representative_point().x,
            geometry.representative_point().y,
        ],
        "boundary_ids": [f"boundary:{space_id}"],
        "minimum_area_m2": minimum_area if minimum_area is not None else geometry.area,
        "minimum_width_m": 1.0,
        "required": True,
    }
    if circulation_role:
        value["circulation_role"] = circulation_role
    return value


def _parent_candidate():
    spaces = [
        _space("space:master", [[0, 0], [4, 0], [4, 4], [0, 4]]),
        _space("space:guest_bath", [[4, 0], [6, 0], [6, 2], [4, 2]]),
        _space("space:storage", [[4, 2], [6, 2], [6, 4], [4, 4]]),
        _space("space:bathroom", [[6, 0], [8, 0], [8, 2], [6, 2]]),
        _space("space:closet", [[6, 2], [8, 2], [8, 4], [6, 4]]),
        _space(
            "space:private_hall",
            [[0, 4], [8, 4], [8, 5], [0, 5]],
            circulation_role="PRIVATE_CIRCULATION",
        ),
        _space("space:kitchen", [[10, 0], [12, 0], [12, 4], [10, 4]], minimum_area=8),
        _space("space:living", [[12, 0], [16, 0], [16, 4], [12, 4]], minimum_area=10),
    ]
    edges = [
        {"edge_id": "portal:master-hall", "from": "space:master", "to": "space:private_hall", "kind": "DOOR_PORTAL"},
        {"edge_id": "portal:guest-master", "from": "space:guest_bath", "to": "space:master", "kind": "DOOR_PORTAL"},
        {"edge_id": "portal:bath-guest", "from": "space:bathroom", "to": "space:guest_bath", "kind": "DOOR_PORTAL"},
        {"edge_id": "portal:storage-hall", "from": "space:storage", "to": "space:private_hall", "kind": "DOOR_PORTAL"},
        {"edge_id": "portal:closet-hall", "from": "space:closet", "to": "space:private_hall", "kind": "DOOR_PORTAL"},
        {"edge_id": "portal:kitchen-living", "from": "space:kitchen", "to": "space:living", "kind": "DOOR_PORTAL"},
        {"edge_id": "portal:living-hall", "from": "space:living", "to": "space:private_hall", "kind": "DOOR_PORTAL"},
    ]
    value = {
        "candidate_id": "candidate-01g-controlled-fixture",
        "candidate_version": "12",
        "space_boundary_graphs": {
            "R1": {"floor": "R1", "spaces": spaces, "virtual_closures": [], "unresolved": []}
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
        "access_graph": {
            "status": "RESOLVED",
            "nodes": [{"id": item["space_id"], "semantic_class": "SPACE"} for item in spaces],
            "edges": edges,
        },
        "hard_constraints": [{"constraint_id": "program_complete", "severity": "hard"}],
        "protected_constraints": [],
        "satisfied_prerequisites": [
            "geometry_availability",
            "adjacency_availability",
            "topology_availability",
            "daylight_evidence_availability",
            "facade_evidence",
            "site_orientation_evidence",
        ],
    }
    value["candidate_hash"] = candidate_semantic_hash(value)
    return value


def _semantic_snapshot(parent):
    spaces = deepcopy(parent["space_boundary_graphs"]["R1"]["spaces"])
    return {
        "spaces": spaces,
        "relations": deepcopy(parent["access_graph"]["edges"]),
        "openings": deepcopy(parent["opening_host_graphs"]["R1"]["openings"]),
        "private_circulation": [
            item for item in spaces if item.get("circulation_role") == "PRIVATE_CIRCULATION"
        ],
        "geometry_available": True,
        "adjacency_available": True,
        "topology_available": True,
        "daylight_evidence_available": True,
        "orientation": "controlled_fixture_north",
        "resolved_dependencies": [
            "geometry_availability",
            "adjacency_availability",
            "topology_availability",
            "daylight_evidence_availability",
            "facade_evidence",
            "site_orientation_evidence",
        ],
        "evidence_status": "verified",
        "validation_evidence": ["controlled_fixture_geometry_and_access_graphs"],
        "hard_constraints": deepcopy(parent["hard_constraints"]),
        "protected_constraints": deepcopy(parent["protected_constraints"]),
    }


def _run_semantic_chain(intent, snapshot):
    impact = analyze_architectural_change_impact(intent, snapshot)
    plan = plan_architectural_change(intent, impact, snapshot)
    readiness = validate_declarative_plan_readiness(plan, snapshot)
    generation = generate_architectural_change_strategies(plan, readiness, snapshot)
    return impact, plan, readiness, generation


def _select(generation, strategy_type):
    assert generation.generation_status == STRATEGY_GENERATION_STATUS_GENERATED
    return next(item for item in generation.strategies if item.strategy_type == strategy_type)


def _lineage(intent, impact, plan, readiness, generation, selected):
    return {
        "intent_id": intent.change_intent_id,
        "impact_intent_id": impact.change_intent_id,
        "plan_id": plan.plan_id,
        "readiness_plan_id": readiness.plan_id,
        "strategy_generation_plan_id": generation.plan_id,
        "selected_semantic_strategy_id": selected.strategy_id,
    }


def _canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _spaces(candidate):
    return {
        item["space_id"]: item
        for item in candidate["space_boundary_graphs"]["R1"]["spaces"]
    }


def _assert_geometry_valid(candidate):
    polygons = [Polygon(item["polygon"]) for item in _spaces(candidate).values()]
    assert all(item.is_valid and item.is_simple and item.area > 0 for item in polygons)
    assert all(
        first.intersection(second).area == 0
        for index, first in enumerate(polygons)
        for second in polygons[index + 1 :]
    )


def _assert_access_connected(candidate):
    required = {
        item["space_id"]
        for item in _spaces(candidate).values()
        if item.get("required", True)
    }
    adjacency = {item: set() for item in required}
    for edge in candidate["access_graph"]["edges"]:
        adjacency[edge["from"]].add(edge["to"])
        adjacency[edge["to"]].add(edge["from"])
    reached, frontier = set(), [next(iter(required))]
    while frontier:
        current = frontier.pop()
        if current not in reached:
            reached.add(current)
            frontier.extend(adjacency[current] - reached)
    assert reached == required


def _kitchen_intent(intent_id="intent-01g-a-kitchen-enlargement"):
    return ArchitecturalChangeIntent(
        change_intent_id=intent_id,
        change_type="resize_space",
        targets=("space:kitchen",),
        direction="increase",
        priority="normal",
        preserve_constraints=("circulation_continuity", "target_access"),
        user_text="آشپزخونه رو بزرگ‌تر کن",
        provenance={"source": "01G deterministic conceptual fixture", "llm_used": False},
    )


def _master_bath_intent(intent_id="intent-01g-b-master-bath-direct-access"):
    return ArchitecturalChangeIntent(
        change_intent_id=intent_id,
        change_type="change_relation",
        targets=("space:master", "space:bathroom"),
        direction="closer",
        preference="adjacency",
        priority="normal",
        preserve_constraints=("circulation_continuity", "privacy", "target_access"),
        user_text="حمام مستر رو نزدیک اتاق مستر کن و دسترسی مستقیم بده",
        provenance={"source": "01G deterministic conceptual fixture", "llm_used": False},
    )


def _area_binding():
    return ({
        "application_id": "strategy-application-01g-a-area-transfer",
        "realizer_step": "SPACE_BOUNDARY_REALIZATION",
        "evidence": {
            "execution_family": "SPACE_BOUNDARY_REALIZATION",
            "operation": "AREA_TRANSFER",
            "target_space_id": "space:kitchen",
            "source_space_id": "space:living",
            "transfer_polygon": [[12, 0], [13, 0], [13, 4], [12, 4]],
            "increase_area_m2": 4.0,
        },
    },)


def _master_bath_bindings(*, opening_width=1.0):
    return (
        {
            "application_id": "strategy-application-01g-b-topology",
            "realizer_step": "ADJACENCY_TOPOLOGY_REALIZATION",
            "evidence": {
                "execution_family": "ADJACENCY_TOPOLOGY_REALIZATION",
                "operation": "PERMUTE_EXISTING_SPACE_GEOMETRY",
                "relation_id": "relation:master-private-bath",
                "target_space_id": "space:master",
                "desired_adjacent_space_id": "space:bathroom",
                "relocation_space_id": "space:guest_bath",
                "allowed_affected_spaces": [
                    "space:master",
                    "space:bathroom",
                    "space:guest_bath",
                    "space:storage",
                    "space:closet",
                ],
                "minimum_shared_boundary_m": 1.5,
            },
        },
        {
            "application_id": "strategy-application-01g-b-opening",
            "realizer_step": "OPENING_ACCESS_REALIZATION",
            "evidence": {
                "execution_family": "OPENING_ACCESS_REALIZATION",
                "operation": "CREATE_DIRECT_ACCESS_INTERFACE",
                "interface_id": "portal:master-private-bath",
                "target_space_pair": ["space:master", "space:bathroom"],
                "shared_boundary_ref": "shared-boundary:master:bathroom",
                "boundary_segment": [[4, 0], [4, 2]],
                "width_m": opening_width,
                "width_source": "explicit_fixture_requirement:clear_width_m",
                "position_fraction": 0.5,
                "position_source": "explicit_fixture_evidence:position_fraction",
            },
        },
    )


def test_scenario_a_simple_kitchen_enlargement_full_chain_commits_once():
    parent = _parent_candidate()
    before = deepcopy(parent)
    before_bytes = _canonical_bytes(parent)
    before_hash = candidate_semantic_hash(parent)
    snapshot = _semantic_snapshot(parent)
    intent = _kitchen_intent()
    impact, plan, readiness, generation = _run_semantic_chain(intent, snapshot)
    selected = _select(generation, "ADJACENT_AREA_TRANSFER")
    lineage = _lineage(intent, impact, plan, readiness, generation, selected)
    transaction, applications, readiness_map = prepare_explicitly_selected_transaction(
        selected,
        readiness,
        parent,
        transaction_id="transaction-01g-a-kitchen-enlargement",
        execution_bindings=_area_binding(),
        lineage=lineage,
    )

    final, result = execute_multi_realizer_transaction(
        transaction, applications, readiness_map, parent
    )

    assert readiness.readiness_status == READINESS_STATUS_READY
    assert final is not None and result.commit_status == TRANSACTION_STATUS_COMMITTED
    assert len(result.step_results) == 1
    assert result.ordered_realizer_steps == ("SPACE_BOUNDARY_REALIZATION",)
    assert _canonical_bytes(parent) == before_bytes and parent == before
    assert candidate_semantic_hash(parent) == before_hash
    final_spaces = _spaces(final)
    assert Polygon(final_spaces["space:kitchen"]["polygon"]).area == 12.0
    assert Polygon(final_spaces["space:living"]["polygon"]).area == 12.0
    _assert_geometry_valid(final)
    _assert_access_connected(final)
    assert final["derivation"]["transaction_id"] == transaction.transaction_id
    assert final["derivation"]["ordered_strategy_ids"] == [applications[0].strategy_id]
    assert applications[0].provenance["acceptance_lineage"] == lineage
    assert final["derivation"]["single_final_commit"] is True
    assert final["derivation"]["intermediate_candidates_committed"] is False
    assert result.final_candidate_hash == candidate_semantic_hash(final)


def test_scenario_b_master_bath_adjacency_and_direct_access_full_chain():
    parent = _parent_candidate()
    before = deepcopy(parent)
    before_hash = candidate_semantic_hash(parent)
    intent = _master_bath_intent()
    impact, plan, readiness, generation = _run_semantic_chain(
        intent, _semantic_snapshot(parent)
    )
    selected = _select(generation, "DIRECT_PRIVATE_RELATIONSHIP")
    lineage = _lineage(intent, impact, plan, readiness, generation, selected)
    dependency = ((
        "strategy-application-01g-b-topology",
        "strategy-application-01g-b-opening",
    ),)
    transaction, applications, readiness_map = prepare_explicitly_selected_transaction(
        selected,
        readiness,
        parent,
        transaction_id="transaction-01g-b-master-bath",
        execution_bindings=_master_bath_bindings(),
        dependency_edges=dependency,
        lineage=lineage,
    )

    final, result = execute_multi_realizer_transaction(
        transaction, applications, readiness_map, parent
    )

    assert readiness.readiness_status == READINESS_STATUS_READY
    assert final is not None and result.commit_status == TRANSACTION_STATUS_COMMITTED
    assert result.ordered_realizer_steps == (
        "ADJACENCY_TOPOLOGY_REALIZATION",
        "OPENING_ACCESS_REALIZATION",
    )
    assert tuple(item.realization_status for item in result.step_results) == (
        "REALIZED",
        "REALIZED",
    )
    polygons = {key: Polygon(value["polygon"]) for key, value in _spaces(final).items()}
    shared = polygons["space:master"].boundary.intersection(
        polygons["space:bathroom"].boundary
    )
    assert shared.length >= 1.5
    opening = next(
        item
        for item in final["opening_host_graphs"]["R1"]["openings"]
        if item["opening_id"] == "portal:master-private-bath"
    )
    assert LineString(opening["centerline"]).difference(shared).is_empty
    access_edge = next(
        item
        for item in final["access_graph"]["edges"]
        if item["edge_id"] == "portal:master-private-bath"
    )
    assert access_edge["opening_binding"] == opening["opening_id"]
    assert not any(
        key in final for key in ("bim_doors", "door_leafs", "door_frames", "door_objects")
    )
    _assert_geometry_valid(final)
    _assert_access_connected(final)
    assert parent == before and candidate_semantic_hash(parent) == before_hash
    assert final["derivation"]["ordered_strategy_ids"] == [
        item.strategy_id for item in applications
    ]
    assert all(item.provenance["acceptance_lineage"] == lineage for item in applications)
    assert final["derivation"]["single_final_commit"] is True


def test_scenario_c_hard_circulation_constraint_rejects_before_realization():
    parent = _parent_candidate()
    before = deepcopy(parent)
    snapshot = _semantic_snapshot(parent)
    snapshot["hard_constraint_conflicts"] = [{
        "constraint_id": "protected_primary_circulation_route",
        "severity": "hard",
        "status": "violated",
        "protected": True,
    }]
    intent = _kitchen_intent("intent-01g-c-preserve-circulation")
    intent = ArchitecturalChangeIntent(**{
        **intent.__dict__,
        "user_text": "این تغییر رو انجام بده ولی مسیر رفت‌وآمد خراب نشه",
    })

    impact, plan, readiness, generation = _run_semantic_chain(intent, snapshot)

    assert impact.change_intent_id == intent.change_intent_id
    assert plan.intent_id == intent.change_intent_id
    assert readiness.plan_id == plan.plan_id
    assert readiness.readiness_status == READINESS_STATUS_BLOCKED_CONSTRAINT
    assert generation.generation_status == STRATEGY_GENERATION_STATUS_BLOCKED_READINESS
    assert generation.strategies == ()
    assert "protected_primary_circulation_route" in readiness.constraint_conflicts
    assert any(
        "protected_primary_circulation_route" in item
        for item in readiness.rejection_reasons + generation.blocker_reasons
    )
    assert parent == before and candidate_semantic_hash(parent) == before["candidate_hash"]


def test_scenario_d_unsupported_daylight_domain_rejected_before_mutation():
    parent = _parent_candidate()
    before = deepcopy(parent)
    intent = ArchitecturalChangeIntent(
        change_intent_id="intent-01g-d-daylight",
        change_type="improve_daylight",
        targets=("space:living",),
        direction="increase_daylight",
        soft_objectives=("daylight", "window_opportunity"),
        preserve_constraints=("privacy", "circulation_continuity"),
        user_text="نور روز فضای نشیمن را با پنجره بهتر کن",
        provenance={"source": "01G deterministic conceptual fixture", "llm_used": False},
    )
    impact, plan, readiness, generation = _run_semantic_chain(
        intent, _semantic_snapshot(parent)
    )
    selected = _select(generation, "DAYLIGHT_EXPOSURE_RELATIONSHIP")
    lineage = _lineage(intent, impact, plan, readiness, generation, selected)
    transaction = MultiRealizerTransactionPlan(
        transaction_id="transaction-01g-d-unsupported-daylight",
        parent_candidate_id=parent["candidate_id"],
        parent_candidate_hash=candidate_semantic_hash(parent),
        parent_candidate_version=parent["candidate_version"],
        ordered_strategy_ids=(selected.strategy_id,),
        ordered_realizer_steps=("OPENING_ACCESS_REALIZATION",),
        provenance={
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01G",
            "selection_mode": "EXPLICIT_CALLER_SELECTION",
            "acceptance_lineage": lineage,
        },
    )

    final, result = execute_multi_realizer_transaction(
        transaction, (selected,), {selected.strategy_id: readiness}, parent
    )

    assert readiness.readiness_status == READINESS_STATUS_READY
    assert final is None
    assert result.commit_status == TRANSACTION_STATUS_UNSUPPORTED_STRATEGY_SEQUENCE
    assert result.step_results == ()
    assert result.failed_step_index == 0
    assert "unsupported_strategy_realizer_step" in result.rollback_reason
    assert parent == before and candidate_semantic_hash(parent) == before["candidate_hash"]


def test_scenario_e_later_failure_rolls_back_successful_transaction_local_step():
    parent = _parent_candidate()
    before = deepcopy(parent)
    before_bytes = _canonical_bytes(parent)
    intent = _master_bath_intent("intent-01g-e-rollback")
    impact, plan, readiness, generation = _run_semantic_chain(
        intent, _semantic_snapshot(parent)
    )
    selected = _select(generation, "DIRECT_PRIVATE_RELATIONSHIP")
    lineage = _lineage(intent, impact, plan, readiness, generation, selected)
    dependency = ((
        "strategy-application-01g-b-topology",
        "strategy-application-01g-b-opening",
    ),)
    transaction, applications, readiness_map = prepare_explicitly_selected_transaction(
        selected,
        readiness,
        parent,
        transaction_id="transaction-01g-e-rollback",
        execution_bindings=_master_bath_bindings(opening_width=3.0),
        dependency_edges=dependency,
        lineage=lineage,
    )

    final, result = execute_multi_realizer_transaction(
        transaction, applications, readiness_map, parent
    )

    assert final is None
    assert result.commit_status == TRANSACTION_STATUS_REJECTED_STEP_FAILURE
    assert result.failed_step_index == 1
    assert result.failed_step_id == applications[1].strategy_id
    assert len(result.step_results) == 2
    assert result.step_results[0].realization_status == "REALIZED"
    assert result.step_results[0].provenance["transaction_local"] is True
    assert result.step_results[0].provenance["published"] is False
    assert result.step_results[1].realization_status == "REJECTED_OPENING_GEOMETRY"
    assert result.rollback_reason == (
        f"step_failed:{applications[1].strategy_id}:REJECTED_OPENING_GEOMETRY"
    )
    assert result.final_candidate_id is None and result.final_candidate_hash is None
    assert parent == before and _canonical_bytes(parent) == before_bytes
    assert candidate_semantic_hash(parent) == before["candidate_hash"]


def test_01g_transaction_plan_and_results_round_trip_and_are_deterministic():
    parent = _parent_candidate()
    intent = _kitchen_intent("intent-01g-serialization")
    impact, plan, readiness, generation = _run_semantic_chain(
        intent, _semantic_snapshot(parent)
    )
    selected = _select(generation, "ADJACENT_AREA_TRANSFER")
    prepared = prepare_explicitly_selected_transaction(
        selected,
        readiness,
        parent,
        transaction_id="transaction-01g-serialization",
        execution_bindings=_area_binding(),
        lineage=_lineage(intent, impact, plan, readiness, generation, selected),
    )
    transaction, applications, readiness_map = prepared
    first_final, first_result = execute_multi_realizer_transaction(
        transaction, applications, readiness_map, parent
    )
    second_final, second_result = execute_multi_realizer_transaction(
        transaction, applications, readiness_map, parent
    )

    assert loads_contract(dumps_contract(transaction)) == transaction
    assert loads_contract(dumps_contract(first_result)) == first_result
    assert first_final == second_final
    assert first_result == second_result
    assert first_result.final_candidate_hash == candidate_semantic_hash(first_final)
