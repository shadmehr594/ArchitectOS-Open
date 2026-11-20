"""ARCHITECTURAL-CHANGE-ORCHESTRATOR-01H acceptance tests."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeStrategy,
    ExecutionReadinessResult,
    READINESS_STATUS_READY,
    STRATEGY_APPLICABILITY_APPLICABLE,
)
from core.architecture.contracts.architectural_change_window_daylight_contracts_v1 import (
    WINDOW_DAYLIGHT_STATUS_REALIZED,
    WINDOW_DAYLIGHT_STATUS_REALIZED_WITH_WARNINGS,
    WINDOW_DAYLIGHT_STATUS_REJECTED_DAYLIGHT_EVIDENCE,
    WINDOW_DAYLIGHT_STATUS_REJECTED_PRIVACY,
    WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY,
    WINDOW_DAYLIGHT_STATUS_STALE_PARENT,
    WINDOW_DAYLIGHT_STATUS_UNSUPPORTED_STRATEGY,
    dumps_contract,
    loads_contract,
)
from core.architecture.reasoning.architectural_change_selected_daylight_strategy_adapter_v1 import (
    bind_explicitly_selected_daylight_strategy,
)
from core.architecture.reasoning.architectural_change_space_geometry_realizer_v1 import (
    candidate_semantic_hash,
)
from core.architecture.reasoning.architectural_change_window_daylight_realizer_v1 import (
    realize_selected_window_daylight_strategy,
)


def _readiness() -> ExecutionReadinessResult:
    return ExecutionReadinessResult(
        plan_id="plan:daylight-01h",
        readiness_status=READINESS_STATUS_READY,
        unresolved_dependencies=(),
        constraint_conflicts=(),
        preservation_requirements=("privacy", "access", "circulation"),
        required_checks_before_execution=("window_geometry", "daylight", "privacy"),
        rejection_reasons=(),
        evidence=("target_space_resolved", "canonical_boundary_graphs_available"),
    )


def _selected_strategy(strategy_type="DAYLIGHT_EXPOSURE_RELATIONSHIP") -> ArchitecturalChangeStrategy:
    return ArchitecturalChangeStrategy(
        strategy_id=f"semantic:{strategy_type.lower()}",
        plan_id="plan:daylight-01h",
        strategy_type=strategy_type,
        target_entities=("space:living",),
        proposed_semantic_actions=("improve_daylight_opportunity",),
        required_tradeoffs=("daylight_exposure_and_privacy",),
        preserved_constraints=("privacy", "access", "circulation"),
        prerequisites=(),
        expected_impacts=("verified_exterior_window_opportunity",),
        risks=("privacy_exposure_conflict",),
        required_rechecks=("daylight", "privacy", "site_orientation"),
        applicability_status=STRATEGY_APPLICABILITY_APPLICABLE,
        evidence=("explicit_strategy_selection",),
    )


def _evidence(operation="CREATE_WINDOW_OPPORTUNITY", **changes):
    value = {
        "execution_family": "WINDOW_DAYLIGHT_REALIZATION",
        "operation": operation,
        "target_space_id": "space:living",
        "window_interface_id": "window:living-south-opportunity",
        "host_exterior_boundary_ref": "R1-WPAIR-SOUTH",
        "boundary_segment": [[0.2, 0.2], [5.8, 0.2]],
        "width_m": 1.2,
        "height_m": 1.4,
        "dimensions_source": "explicit_project_requirement:window-01h",
        "position_distance_m": 2.0,
        "position_source": "explicit_project_requirement:distance_from_boundary_start",
        "daylight_goal": {"goal": "create_exterior_window_opportunity", "requires_orientation": False},
        "privacy_constraints": (),
        "reason": "explicit_selected_strategy_daylight_opportunity",
    }
    value.update(changes)
    return value


def _strategy(strategy_type="DAYLIGHT_EXPOSURE_RELATIONSHIP", evidence=None):
    return bind_explicitly_selected_daylight_strategy(
        _selected_strategy(strategy_type),
        _readiness(),
        application_id=f"application:{strategy_type.lower()}",
        execution_evidence=evidence or _evidence(),
        lineage={"selection": "caller_explicit", "ranking_performed": False},
    )


def _window(window_id="window:existing", start=1.5, end=2.5, height=1.2):
    return {
        "opening_id": window_id,
        "floor": "R1",
        "kind": "WINDOW",
        "host_wall_pair_id": "R1-WPAIR-SOUTH",
        "host_face_a": "R1-FACE-SOUTH-INNER",
        "host_face_b": "R1-FACE-SOUTH-OUTER",
        "centerline": [[start, 0.2], [end, 0.2]],
        "clear_width_m": end - start,
        "height_m": height,
        "side_a": "space:living",
        "side_b": "EXTERIOR:R1",
        "exposure": "EXTERIOR_UNORIENTED",
        "status": "RESOLVED_WINDOW_OPPORTUNITY",
        "geometric_evidence": {"source": "existing_candidate_geometry"},
    }


def _candidate(openings=None):
    value = {
        "candidate_id": "candidate-01h",
        "candidate_version": "12",
        "space_boundary_graphs": {
            "R1": {
                "floor": "R1",
                "spaces": [{
                    "space_id": "space:living",
                    "floor": "R1",
                    "polygon": [[0.2, 0.2], [5.8, 0.2], [5.8, 4.8], [0.2, 4.8], [0.2, 0.2]],
                    "area_m2": 25.76,
                    "boundary_ids": ["R1-FACE-SOUTH-INNER"],
                    "semantic_class": "LIVING",
                    "required": True,
                }],
                "virtual_closures": [],
                "unresolved": [],
            }
        },
        "wall_face_graphs": {
            "R1": {
                "floor": "R1",
                "faces": [
                    {"face_id": "R1-FACE-SOUTH-INNER", "start": [0.2, 0.2], "end": [5.8, 0.2], "source_handles": ["W-IN"]},
                    {"face_id": "R1-FACE-SOUTH-OUTER", "start": [0.0, 0.0], "end": [6.0, 0.0], "source_handles": ["W-OUT"]},
                ],
                "pairs": [{
                    "wall_pair_id": "R1-WPAIR-SOUTH",
                    "face_a": "R1-FACE-SOUTH-INNER",
                    "face_b": "R1-FACE-SOUTH-OUTER",
                    "thickness_m": 0.2,
                    "source_handles": ["W-IN", "W-OUT"],
                }],
                "junctions": [],
                "thickness_clusters_m": [],
            }
        },
        "wall_solid_graphs": {
            "R1": {
                "floor": "R1",
                "solids": [{
                    "wall_solid_id": "R1-WSOLID-SOUTH",
                    "polygon": [[0, 0], [6, 0], [5.8, 0.2], [0.2, 0.2], [0, 0]],
                    "source_pair_ids": ["R1-WPAIR-SOUTH"],
                    "source_face_ids": ["R1-FACE-SOUTH-INNER", "R1-FACE-SOUTH-OUTER"],
                }],
                "floor_envelopes": [{
                    "envelope_id": "R1-ENVELOPE-001",
                    "polygon": [[0, 0], [6, 0], [6, 5], [0, 5], [0, 0]],
                    "source": "CLOSED_SOURCE_PERIMETER_GEOMETRY",
                }],
            }
        },
        "opening_host_graphs": {
            "R1": {"floor": "R1", "openings": deepcopy(openings or []), "unresolved": []}
        },
        "access_graph": {
            "status": "RESOLVED",
            "nodes": [{"id": "space:living", "floor": "R1", "semantic_class": "LIVING"}],
            "edges": [],
            "connected_components": [["space:living"]],
        },
        "protected_entities": [],
        "protected_constraints": [],
        "hard_constraints": [],
        "privacy_constraints": [],
    }
    return value


def _run(candidate=None, strategy=None, **expected):
    candidate = candidate or _candidate()
    return realize_selected_window_daylight_strategy(
        strategy or _strategy(), _readiness(), candidate,
        expected_parent_id=expected.get("expected_parent_id", candidate["candidate_id"]),
        expected_parent_version=expected.get("expected_parent_version", candidate["candidate_version"]),
        expected_parent_hash=expected.get("expected_parent_hash", candidate_semantic_hash(candidate)),
    )


def _opening(candidate, window_id):
    return next(item for item in candidate["opening_host_graphs"]["R1"]["openings"] if item["opening_id"] == window_id)


def test_create_window_opportunity_on_verified_exterior_boundary_commits_derived_candidate():
    parent = _candidate()
    derived, result = _run(parent)
    assert result.status == WINDOW_DAYLIGHT_STATUS_REALIZED_WITH_WARNINGS
    assert derived is not None and derived is not parent
    window = _opening(derived, "window:living-south-opportunity")
    assert window["kind"] == "WINDOW" and window["side_b"] == "EXTERIOR:R1"
    assert window["physical_object_scope"] == "ARCHITECTURAL_OPENING_INTERFACE_ONLY"
    assert result.window_daylight_changes[0].facade_exterior_relation["orientation_claimed"] is False
    assert {"site_orientation", "daylight_simulation"} <= set(result.required_downstream_rechecks)


def test_enlarge_existing_window_stays_on_same_host_and_preserves_corner_and_overlap_gates():
    parent = _candidate([_window()])
    evidence = _evidence(
        "ENLARGE_EXISTING_WINDOW",
        window_interface_id="window:existing",
        width_m=1.6,
        height_m=1.2,
        dimensions_source="explicit_project_requirement:enlarged_width+existing_height",
        position_distance_m=None,
        position_fraction=None,
        position_source="existing_window.centerline",
    )
    derived, result = _run(parent, _strategy("ENLARGE_EXISTING_WINDOW", evidence))
    assert derived is not None and result.status == WINDOW_DAYLIGHT_STATUS_REALIZED_WITH_WARNINGS
    enlarged = _opening(derived, "window:existing")
    assert enlarged["host_wall_pair_id"] == "R1-WPAIR-SOUTH"
    assert enlarged["clear_width_m"] == pytest.approx(1.6)
    assert len(derived["opening_host_graphs"]["R1"]["openings"]) == 1


def test_private_protected_edge_rejects_without_mutation():
    parent = _candidate()
    parent["privacy_constraints"] = [{
        "constraint_id": "privacy-private-edge",
        "space_id": "space:living",
        "kind": "privacy_exposure",
        "protected": True,
    }]
    before = deepcopy(parent)
    derived, result = _run(parent)
    assert derived is None and result.status == WINDOW_DAYLIGHT_STATUS_REJECTED_PRIVACY
    assert parent == before


def test_orientation_dependent_daylight_strategy_without_verified_orientation_rejects():
    evidence = _evidence(
        orientation_required=True,
        daylight_goal={"goal": "improve_solar_daylight_performance", "requires_orientation": True},
    )
    derived, result = _run(strategy=_strategy(evidence=evidence))
    assert derived is None and result.status == WINDOW_DAYLIGHT_STATUS_REJECTED_DAYLIGHT_EVIDENCE
    assert result.failures == ("site_orientation_evidence_required_but_missing",)
    assert result.provenance["orientation_inferred"] is False


def test_non_exterior_host_attempt_rejects():
    parent = _candidate()
    parent["wall_face_graphs"]["R1"]["faces"][1].update({"start": [0, 2], "end": [6, 2]})
    derived, result = _run(parent)
    assert derived is None and result.status == WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY
    assert "host_not_proved_exterior_facade_boundary" in result.failures


def test_overlap_with_existing_door_rejects_and_rolls_back():
    door = {
        "opening_id": "door:exterior-existing",
        "floor": "R1",
        "kind": "DOOR",
        "host_wall_pair_id": "R1-WPAIR-SOUTH",
        "centerline": [[1.5, 0.2], [2.5, 0.2]],
        "side_a": "space:living",
        "side_b": "EXTERIOR:R1",
    }
    parent = _candidate([door])
    before = deepcopy(parent)
    derived, result = _run(parent)
    assert derived is None and result.status == WINDOW_DAYLIGHT_STATUS_REJECTED_WINDOW_GEOMETRY
    assert result.failures == ("opening_overlap:door:exterior-existing",)
    assert parent == before


def test_stale_parent_hash_rejects():
    parent = _candidate()
    derived, result = _run(parent, expected_parent_hash="0" * 64)
    assert derived is None and result.status == WINDOW_DAYLIGHT_STATUS_STALE_PARENT


@pytest.mark.parametrize("strategy_type", [
    "ADJACENT_AREA_TRANSFER",
    "DIRECT_PRIVATE_RELATIONSHIP",
    "CREATE_DIRECT_ACCESS_INTERFACE",
    "SITE_FIT_REALIZATION",
])
def test_non_window_strategy_families_are_unsupported(strategy_type):
    derived, result = _run(strategy=_strategy(strategy_type))
    assert derived is None and result.status == WINDOW_DAYLIGHT_STATUS_UNSUPPORTED_STRATEGY


def test_same_input_is_deterministic_for_candidate_delta_and_result_hashes():
    parent = _candidate()
    first_candidate, first_result = _run(parent, _strategy())
    second_candidate, second_result = _run(parent, _strategy())
    assert first_candidate == second_candidate
    assert first_result == second_result
    assert first_result.derived_hash == second_result.derived_hash
    assert first_result.window_daylight_changes == second_result.window_daylight_changes


def test_contract_and_result_serialization_round_trip_stably():
    _, result = _run()
    result_document = dumps_contract(result)
    delta_document = dumps_contract(result.window_daylight_changes[0])
    assert loads_contract(result_document) == result
    assert dumps_contract(loads_contract(result_document)) == result_document
    assert loads_contract(delta_document) == result.window_daylight_changes[0]
    assert dumps_contract(loads_contract(delta_document)) == delta_document


def test_parent_is_byte_and_semantically_unchanged_on_success_and_rejection():
    success_parent = _candidate()
    success_document = json.dumps(success_parent, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    success_hash = candidate_semantic_hash(success_parent)
    derived, success_result = _run(success_parent)
    assert derived is not None
    assert json.dumps(success_parent, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == success_document
    assert candidate_semantic_hash(success_parent) == success_hash == success_result.parent_hash

    rejected_parent = _candidate()
    rejected_document = json.dumps(rejected_parent, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    rejected_hash = candidate_semantic_hash(rejected_parent)
    bad = _evidence(width_m=None)
    rejected, rejected_result = _run(rejected_parent, _strategy(evidence=bad))
    assert rejected is None
    assert json.dumps(rejected_parent, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == rejected_document
    assert candidate_semantic_hash(rejected_parent) == rejected_hash == rejected_result.parent_hash


def test_no_bim_or_ifc_window_object_is_created():
    derived, result = _run()
    assert derived is not None
    window = _opening(derived, "window:living-south-opportunity")
    document = json.dumps(window, sort_keys=True).lower()
    assert "ifcwindow" not in document and "bim_object" not in document
    assert result.provenance["physical_bim_or_ifc_object_created"] is False
    assert result.constraint_checks[-1] == {"check": "no_bim_ifc_window_object_created", "passed": True}


def test_verified_orientation_is_consumed_only_when_authoritative_and_never_inferred():
    parent = _candidate()
    parent["site_orientation_evidence"] = {
        "status": "VERIFIED",
        "source": "survey_coordinate_frame",
        "north_vector": [0, 1],
    }
    evidence = _evidence(
        orientation_required=True,
        daylight_goal={"goal": "orientation_evidence_bound_opportunity", "requires_orientation": True},
    )
    derived, result = _run(parent, _strategy(evidence=evidence))
    assert derived is not None and result.status == WINDOW_DAYLIGHT_STATUS_REALIZED
    assert result.provenance["orientation_inferred"] is False


def test_adapter_does_not_select_rank_or_derive_execution_evidence():
    evidence = _evidence()
    selected = _selected_strategy()
    application = bind_explicitly_selected_daylight_strategy(
        selected, _readiness(), application_id="application:explicit", execution_evidence=evidence,
    )
    assert application.strategy_id == "application:explicit"
    assert application.strategy_type == selected.strategy_type
    assert application.strategy_rank_hint is None
    assert application.provenance["execution_evidence_derived"] is False
    assert application.provenance["window_daylight_realization"] == evidence
