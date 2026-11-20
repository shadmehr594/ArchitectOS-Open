import hashlib
import json
from copy import deepcopy
from pathlib import Path

from core.architecture.reasoning.pilot_parking_feasibility_study_v1 import (
    PilotParkingFeasibilityStudyV1,
)

ROOT = Path(__file__).resolve().parents[2]


def _inputs():
    path = sorted((ROOT / "exports" / "DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))[-1]
    base = json.loads(path.read_text(encoding="utf-8"))
    recommendation = sorted((ROOT / "exports" / "DEFAULT").glob("parcel2_basement_v2_*/program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json"))[-1]
    rec = json.loads(recommendation.read_text(encoding="utf-8"))
    return base, rec["baseline_scenario_a"]


def _result():
    base, scenario_a = _inputs()
    return PilotParkingFeasibilityStudyV1().resolve(base["site"], base["requirements"], scenario_a)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def test_real_parcel2_and_all_search_families_are_used():
    r = _result()
    assert r["site_geometry_source"] == "authoritative_normalized_real_parcel_2"
    assert r["source_parcel"][0] == [9.495348, 22.127313]
    assert r["source_road_width"] == 10.0
    assert r["candidate_families_explored"] == ["PILOT-P01", "PILOT-P02", "PILOT-P03", "PILOT-P04"]
    assert r["candidate_count"] > len(r["candidate_families_explored"])


def test_scenario_a_is_not_modified_or_regenerated():
    base, scenario_a = _inputs()
    site_before, baseline_before = _digest(base["site"]), _digest(scenario_a)
    r = PilotParkingFeasibilityStudyV1().resolve(base["site"], base["requirements"], scenario_a)
    assert _digest(base["site"]) == site_before and _digest(scenario_a) == baseline_before
    assert r["baseline_geometry_preserved"] and not r["existing_ramp_core_geometry_regenerated"]


def test_capacity_is_generated_stalls_and_independent_use_is_path_validated():
    r = _result()
    for c in r["candidates"]:
        assert c["pilot_parking_capacity"] == len(c["parking_stalls"])
        assert c["independently_usable_parking_count"] == sum(
            p["entry_status"] == "hard_valid" and p["exit_status"] == "hard_valid"
            for p in c["vehicle_movement_path"]["stall_paths"]
        )
        assert all(p["other_stalls_treated_as_occupied"] for p in c["vehicle_movement_path"]["stall_paths"])


def test_rectangle_fit_is_insufficient_and_blocked_paths_reject():
    r = _result()
    blocked = [c for c in r["candidates"] if c["vehicle_movement_path"]["geometry_status"] != "hard_valid"]
    assert blocked
    assert all("maneuvering_unproven" in c["rejection_reasons"] for c in blocked)
    assert all(c["hard_geometry_status"] == "not_feasible" for c in blocked)


def test_core_is_independently_repositioned_and_pedestrian_access_is_evaluated():
    r = _result()
    assert r["core_repositioning_permitted"] and not r["existing_core_reuse_required"]
    assert len({json.dumps(c["core"]["polygon"]) for c in r["candidates"]}) > 1
    assert all(c["pedestrian_access_status"] in ("resolved", "not_feasible") for c in r["candidates"])
    assert all(c["core"]["source"] == "independent_scenario_b_core_generation" for c in r["candidates"])


def test_commercial_metrics_and_quality_gate_are_present():
    r = _result()
    evaluated = [c for c in r["candidates"] if c["commercial_quality"]]
    required = {"commercial_total_area", "commercial_frontage_width", "largest_contiguous_commercial_area",
                "usable_rectangular_field_area", "average_commercial_depth", "maximum_commercial_depth",
                "commercial_space_compactness", "commercial_convexity_ratio", "minimum_local_width",
                "rear_area_reachable_only_through_narrow_neck", "core_induced_commercial_fragmentation"}
    assert evaluated and all(required <= set(c["commercial_quality"]) for c in evaluated)
    if r["best_pilot_candidate"]:
        assert r["best_pilot_candidate"]["commercial_quality_status"] == "quality_valid"


def test_rules_and_protected_state_remain_unresolved_and_unchanged():
    r = _result()
    assert r["regulatory_approval_status"] == "pending_rule_resolution"
    assert all(c["regulatory_status"] == "pending_rule_resolution" for c in r["candidates"])
    assert not r["program_changed"] and not r["basement_deleted"] and not r["basement_removal_approved"]
    assert not r["structure_executed"] and not r["bim_executed"] and not r["ifc_executed"]
    assert r["scenario_b_worthy_of_final_comparison"] in (True, False, "unresolved")
