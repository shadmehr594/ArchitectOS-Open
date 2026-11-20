"""ARCHITECTURAL-CHANGE-ORCHESTRATOR-01F-D acceptance tests."""
from __future__ import annotations

import ast
from copy import deepcopy
import inspect
import json

from shapely.geometry import Polygon

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeStrategy,
    ExecutionReadinessResult,
    MultiRealizerTransactionPlan,
    MultiRealizerTransactionResult,
    READINESS_STATUS_READY,
    STRATEGY_APPLICABILITY_APPLICABLE,
    TRANSACTION_STATUS_COMMITTED,
    TRANSACTION_STATUS_REJECTED_DEPENDENCY_ORDER,
    TRANSACTION_STATUS_REJECTED_STEP_FAILURE,
    TRANSACTION_STATUS_STALE_PARENT,
    TRANSACTION_STATUS_UNSUPPORTED_STRATEGY_SEQUENCE,
    dumps_contract,
    loads_contract,
)
from core.architecture.reasoning import architectural_change_multi_realizer_transaction_coordinator_v1 as module
from core.architecture.reasoning.architectural_change_multi_realizer_transaction_coordinator_v1 import (
    execute_multi_realizer_transaction,
)
from core.architecture.reasoning.architectural_change_space_geometry_realizer_v1 import (
    candidate_semantic_hash,
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
        "interior_point": [geometry.representative_point().x, geometry.representative_point().y],
        "boundary_ids": [f"boundary:{space_id}"],
        "minimum_area_m2": minimum_area if minimum_area is not None else geometry.area,
        "minimum_width_m": 1.0,
        "required": True,
    }
    if circulation_role:
        value["circulation_role"] = circulation_role
    return value


def _candidate():
    spaces = [
        _space("space:master", [[0, 0], [4, 0], [4, 4], [0, 4]]),
        _space("space:guest_bath", [[4, 0], [6, 0], [6, 2], [4, 2]]),
        _space("space:storage", [[4, 2], [6, 2], [6, 4], [4, 4]]),
        _space("space:bathroom", [[6, 0], [8, 0], [8, 2], [6, 2]]),
        _space("space:closet", [[6, 2], [8, 2], [8, 4], [6, 4]]),
        _space("space:private_hall", [[0, 4], [8, 4], [8, 5], [0, 5]], circulation_role="PRIVATE_CIRCULATION"),
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
        "candidate_id": "candidate-01f-d",
        "candidate_version": "11",
        "space_boundary_graphs": {"R1": {"floor": "R1", "spaces": spaces, "virtual_closures": [], "unresolved": []}},
        "opening_host_graphs": {"R1": {"floor": "R1", "openings": [
            {"opening_id": "portal:guest-master", "kind": "DOOR", "side_a": "space:guest_bath", "side_b": "space:master"},
            {"opening_id": "portal:bath-guest", "kind": "DOOR", "side_a": "space:bathroom", "side_b": "space:guest_bath"},
        ], "unresolved": []}},
        "access_graph": {
            "status": "RESOLVED",
            "nodes": [{"id": item["space_id"], "semantic_class": "SPACE"} for item in spaces],
            "edges": edges,
        },
        "hard_constraints": [{"constraint_id": "program_complete", "severity": "hard"}],
        "protected_constraints": [],
        "satisfied_prerequisites": [],
    }
    value["candidate_hash"] = candidate_semantic_hash(value)
    return value


def _strategy(strategy_id, plan_id, strategy_type, targets, actions, provenance, preserved=("circulation_continuity",)):
    return ArchitecturalChangeStrategy(
        strategy_id=strategy_id,
        plan_id=plan_id,
        strategy_type=strategy_type,
        target_entities=targets,
        proposed_semantic_actions=actions,
        required_tradeoffs=("bounded_existing_plan_change",),
        preserved_constraints=preserved,
        prerequisites=(),
        expected_impacts=("declared_change",),
        risks=("transaction_failure",),
        required_rechecks=("geometry", "access", "circulation"),
        applicability_status=STRATEGY_APPLICABILITY_APPLICABLE,
        evidence=("explicit_execution_evidence",),
        provenance=provenance,
    )


def _bundle(*, fail_b=False, fail_c=False):
    area = _strategy(
        "strategy-a", "plan-a", "ADJACENT_AREA_TRANSFER", ("space:kitchen",),
        ("increase_space_area(kitchen)", "transfer_adjacent_available_area"),
        {"area_transfer": {
            "execution_family": "SPACE_BOUNDARY_REALIZATION", "operation": "AREA_TRANSFER",
            "target_space_id": "space:kitchen", "source_space_id": "space:living",
            "transfer_polygon": [[12, 0], [13, 0], [13, 4], [12, 4]], "increase_area_m2": 4,
        }},
    )
    topology = _strategy(
        "strategy-b", "plan-b", "DIRECT_PRIVATE_RELATIONSHIP", ("space:master", "space:bathroom"),
        ("strengthen_master_bath_adjacency", "prioritize_private_access_relationship"),
        {"topology_realization": {
            "execution_family": "ADJACENCY_TOPOLOGY_REALIZATION", "operation": "PERMUTE_EXISTING_SPACE_GEOMETRY",
            "relation_id": "relation:master-private-bath", "target_space_id": "space:master",
            "desired_adjacent_space_id": "space:bathroom",
            "relocation_space_id": "space:missing" if fail_b else "space:guest_bath",
            "allowed_affected_spaces": ["space:master", "space:bathroom", "space:guest_bath", "space:storage", "space:closet"],
            "minimum_shared_boundary_m": 1.5,
        }},
        preserved=("privacy", "circulation_continuity", "target_access"),
    )
    opening = _strategy(
        "strategy-c", "plan-c", "CREATE_DIRECT_ACCESS_INTERFACE", ("space:master", "space:bathroom"),
        ("create_direct_private_access_interface",),
        {"opening_access_realization": {
            "execution_family": "OPENING_ACCESS_REALIZATION", "operation": "CREATE_DIRECT_ACCESS_INTERFACE",
            "interface_id": "portal:master-private-bath", "target_space_pair": ["space:master", "space:bathroom"],
            "shared_boundary_ref": "shared-boundary:master:bathroom", "boundary_segment": [[4, 0], [4, 2]],
            "width_m": 3.0 if fail_c else 1.0, "width_source": "explicit_strategy_requirement:clear_width_m",
            "position_fraction": 0.5, "position_source": "explicit_strategy_evidence:position_fraction",
        }},
        preserved=("privacy", "circulation_continuity", "target_access"),
    )
    return (area, topology, opening)


def _readiness(strategies):
    return {
        item.strategy_id: ExecutionReadinessResult(
            plan_id=item.plan_id,
            readiness_status=READINESS_STATUS_READY,
            unresolved_dependencies=(), constraint_conflicts=(),
            preservation_requirements=item.preserved_constraints,
            required_checks_before_execution=("geometry", "access", "circulation"),
            rejection_reasons=(), evidence=("resolved_canonical_graphs",),
        )
        for item in strategies
    }


def _plan(candidate, strategies=None, *, steps=None, dependencies=(("strategy-a", "strategy-b"), ("strategy-b", "strategy-c"))):
    strategies = strategies or _bundle()
    return MultiRealizerTransactionPlan(
        transaction_id="transaction-01f-d-a-b-c",
        parent_candidate_id=candidate["candidate_id"],
        parent_candidate_hash=candidate_semantic_hash(candidate),
        parent_candidate_version=candidate["candidate_version"],
        ordered_strategy_ids=tuple(item.strategy_id for item in strategies),
        ordered_realizer_steps=steps or (
            "SPACE_BOUNDARY_REALIZATION", "ADJACENCY_TOPOLOGY_REALIZATION", "OPENING_ACCESS_REALIZATION",
        ),
        dependency_edges=dependencies,
        provenance={"phase": "01F-D", "selected_bundle": True},
    )


def _run(*, candidate=None, strategies=None, plan=None):
    candidate = candidate or _candidate()
    strategies = strategies or _bundle()
    plan = plan or _plan(candidate, strategies)
    return execute_multi_realizer_transaction(plan, strategies, _readiness(strategies), candidate)


def test_a_b_c_success_has_one_final_commit_and_rooted_lineage():
    parent = _candidate()
    final, result = _run(candidate=parent)
    assert final is not None and result.commit_status == TRANSACTION_STATUS_COMMITTED
    assert len(result.step_results) == 3
    assert tuple(item.realization_status for item in result.step_results) == ("REALIZED", "REALIZED", "REALIZED")
    assert final["parent_candidate_id"] == parent["candidate_id"]
    assert final["derivation"]["lineage_root_parent_candidate_id"] == parent["candidate_id"]
    assert final["derivation"]["ordered_strategy_ids"] == ["strategy-a", "strategy-b", "strategy-c"]
    assert final["derivation"]["single_final_commit"] is True
    assert final["derivation"]["intermediate_candidates_committed"] is False
    assert result.final_candidate_hash == candidate_semantic_hash(final)
    assert len(result.aggregate_deltas) == 4


def test_single_selected_strategy_uses_same_atomic_commit_gate():
    parent = _candidate()
    strategies = (_bundle()[0],)
    plan = _plan(parent, strategies, steps=("SPACE_BOUNDARY_REALIZATION",), dependencies=())
    final, result = _run(candidate=parent, strategies=strategies, plan=plan)
    assert final is not None and result.commit_status == TRANSACTION_STATUS_COMMITTED
    assert len(result.step_results) == 1
    assert final["parent_candidate_id"] == parent["candidate_id"]
    assert final["derivation"]["ordered_realizer_steps"] == ["SPACE_BOUNDARY_REALIZATION"]


def test_a_success_b_failure_rolls_back_whole_transaction():
    parent = _candidate()
    before = deepcopy(parent)
    strategies = _bundle(fail_b=True)
    final, result = _run(candidate=parent, strategies=strategies)
    assert final is None and result.commit_status == TRANSACTION_STATUS_REJECTED_STEP_FAILURE
    assert result.failed_step_index == 1 and len(result.step_results) == 2
    assert result.final_candidate_id is None
    assert parent == before


def test_a_b_success_c_failure_rolls_back_whole_transaction():
    parent = _candidate()
    before_bytes = json.dumps(parent, sort_keys=True, separators=(",", ":")).encode()
    strategies = _bundle(fail_c=True)
    final, result = _run(candidate=parent, strategies=strategies)
    assert final is None and result.commit_status == TRANSACTION_STATUS_REJECTED_STEP_FAILURE
    assert result.failed_step_index == 2 and len(result.step_results) == 3
    assert json.dumps(parent, sort_keys=True, separators=(",", ":")).encode() == before_bytes


def test_unsupported_daylight_bundle_is_rejected_in_preflight_with_zero_mutation():
    parent = _candidate()
    strategy = _strategy(
        "strategy-daylight", "plan-daylight", "DAYLIGHT_WINDOW_REALIZATION", ("space:living",),
        ("add_window",), {"execution_evidence": {"operation": "ADD_WINDOW"}},
    )
    plan = _plan(parent, (strategy,), steps=("OPENING_ACCESS_REALIZATION",), dependencies=())
    before = deepcopy(parent)
    final, result = _run(candidate=parent, strategies=(strategy,), plan=plan)
    assert final is None and result.commit_status == TRANSACTION_STATUS_UNSUPPORTED_STRATEGY_SEQUENCE
    assert result.step_results == () and parent == before


def test_stale_parent_rejects_before_execution():
    parent = _candidate()
    strategies = _bundle()
    plan = _plan(parent, strategies)
    parent["candidate_version"] = "12"
    final, result = _run(candidate=parent, strategies=strategies, plan=plan)
    assert final is None and result.commit_status == TRANSACTION_STATUS_STALE_PARENT
    assert result.step_results == ()


def test_invalid_dependency_order_rejects_before_execution():
    parent = _candidate()
    strategies = _bundle()
    plan = _plan(parent, strategies, dependencies=(("strategy-c", "strategy-b"),))
    final, result = _run(candidate=parent, strategies=strategies, plan=plan)
    assert final is None and result.commit_status == TRANSACTION_STATUS_REJECTED_DEPENDENCY_ORDER
    assert result.step_results == ()


def test_same_bundle_is_deterministic_in_step_order_hashes_and_final_hash():
    first_final, first = _run()
    second_final, second = _run()
    assert first_final == second_final
    assert first.final_candidate_hash == second.final_candidate_hash
    assert tuple(item.derived_candidate_hash for item in first.step_results) == tuple(
        item.derived_candidate_hash for item in second.step_results
    )


def test_transaction_plan_and_result_round_trip_stably():
    parent = _candidate()
    strategies = _bundle()
    plan = _plan(parent, strategies)
    final, result = _run(candidate=parent, strategies=strategies, plan=plan)
    assert final is not None
    assert loads_contract(dumps_contract(plan)) == plan
    restored = loads_contract(dumps_contract(result))
    assert isinstance(restored, MultiRealizerTransactionResult)
    assert restored == result
    assert dumps_contract(restored) == dumps_contract(result)


def test_original_parent_remains_byte_and_semantically_equivalent_after_commit():
    parent = _candidate()
    before = deepcopy(parent)
    before_bytes = json.dumps(parent, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    before_hash = candidate_semantic_hash(parent)
    final, _ = _run(candidate=parent)
    assert final is not None and parent == before
    assert json.dumps(parent, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() == before_bytes
    assert candidate_semantic_hash(parent) == before_hash


def test_downstream_steps_receive_accumulated_preserved_constraints():
    final, result = _run()
    assert final is not None
    assert result.step_results[1].provenance["inherited_preserved_constraints"] == ["circulation_continuity"]
    assert set(result.step_results[2].provenance["inherited_preserved_constraints"]) >= {
        "circulation_continuity", "privacy", "target_access",
    }
    assert all(item["passed"] for item in result.invariant_checks)


def test_coordinator_has_no_chat_llm_memory_voice_provider_render_or_bim_dependencies():
    tree = ast.parse(inspect.getsource(module))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module.lower())
    forbidden = ("chat", "llm", "memory", "voice", "provider", "render", "comfyui", "bim", "ifc")
    assert not [name for name in imported if any(token in name for token in forbidden)]
