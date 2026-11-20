import hashlib
import json
from copy import deepcopy
from pathlib import Path

from core.architecture.reasoning.vehicle_movement_path_diagnostic_v1 import (
    VehicleMovementPathDiagnosticV1,
)

ROOT = Path(__file__).resolve().parents[2]


def _inputs():
    study_path = sorted((ROOT / "exports" / "DEFAULT").glob("parcel2_basement_v2_*/pilot_parking_feasibility_study_v1_*/PARCEL2_PILOT_PARKING_FEASIBILITY_STUDY_V1.json"))[-1]
    study = json.loads(study_path.read_text(encoding="utf-8"))
    candidate = next(c for c in study["candidates"] if c["candidate_id"] == "PILOT-P02-03")
    baseline = json.loads(Path(study["source_baseline_contract_path"]).read_text(encoding="utf-8"))
    return candidate, baseline


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def test_diagnosis_uses_real_geometry_without_mutating_candidate():
    candidate, baseline = _inputs()
    before = _digest(candidate)
    diagnostic = VehicleMovementPathDiagnosticV1().analyze(candidate, baseline)
    assert _digest(candidate) == before and diagnostic["candidate_geometry_unchanged"]
    assert diagnostic["source_site"] == "REAL Parcel 2"
    assert diagnostic["source_parcel"][0] == [9.495348, 22.127313]


def test_existing_failures_are_exposed_with_exact_intersection_geometry():
    candidate, baseline = _inputs()
    diagnostic = VehicleMovementPathDiagnosticV1().analyze(candidate, baseline)
    assert all(a["outside_drivable_field_area"] > 0 for a in diagnostic["attempts"])
    assert all(a["outside_drivable_field_geometry"] for a in diagnostic["attempts"])
    assert all(a["occupied_stall_collisions"] for a in diagnostic["attempts"])
    assert all(a["other_stalls_treated_as_occupied"] for a in diagnostic["attempts"])


def test_diagnostic_does_not_misrepresent_corridor_as_vehicle_swept_path():
    candidate, baseline = _inputs()
    diagnostic = VehicleMovementPathDiagnosticV1().analyze(candidate, baseline)
    assert not diagnostic["vehicle_footprint_collision_check"]
    assert not diagnostic["swept_path_check"]
    assert diagnostic["vehicle_dimensions_source"].startswith("unresolved")
    assert diagnostic["clearance_width"] == 5.0


def test_search_limitations_and_legacy_semantics_are_explicit():
    candidate, baseline = _inputs()
    diagnostic = VehicleMovementPathDiagnosticV1().analyze(candidate, baseline)
    assert diagnostic["number_of_maneuver_attempts"] == 2
    assert not diagnostic["reverse_entry_tested"] and not diagnostic["multi_point_maneuver_tested"]
    assert diagnostic["legacy_semantics"]["compatible_general_name"] == "return_to_public_access_status"
    assert {"vehicle_path_intelligence_limitation", "insufficient_search"} <= set(diagnostic["failure_classification"]["applicable"])


def test_independent_use_requires_entry_and_exit_and_other_stall_occupied():
    candidate, baseline = _inputs()
    diagnostic = VehicleMovementPathDiagnosticV1().analyze(candidate, baseline)
    assert not diagnostic["independently_usable"]
    assert diagnostic["successful_entry_strategy"] is None
    assert diagnostic["successful_exit_strategy"] is None
    assert all(not a["entry_successful"] and not a["exit_successful"] for a in diagnostic["attempts"])


def test_scenario_a_and_protected_execution_state_remain_unchanged():
    candidate, baseline = _inputs()
    protected = deepcopy(baseline)
    diagnostic = VehicleMovementPathDiagnosticV1().analyze(candidate, baseline)
    assert baseline == protected
    assert not diagnostic["program_changed"] and not diagnostic["basement_deleted"]
    assert not diagnostic["structure_executed"] and not diagnostic["bim_executed"] and not diagnostic["ifc_executed"]
    assert diagnostic["regulatory_status"] == "pending_rule_resolution"
