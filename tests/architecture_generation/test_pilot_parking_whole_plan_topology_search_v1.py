import hashlib
import json
from pathlib import Path

from core.architecture.reasoning.pilot_parking_whole_plan_topology_search_v1 import (
    PilotParkingWholePlanTopologySearchV1,
)

ROOT = Path(__file__).resolve().parents[2]


def _inputs():
    base_path = sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))[-1]
    rec_path = sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json"))[-1]
    return json.loads(base_path.read_text()), json.loads(rec_path.read_text())["baseline_scenario_a"]


def _result():
    base, scenario_a = _inputs()
    return PilotParkingWholePlanTopologySearchV1().resolve(base["site"], base["requirements"], scenario_a)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def test_real_parcel_and_human_guided_families_are_explored():
    r = _result()
    assert r["site_geometry_source"] == "authoritative_normalized_real_parcel_2"
    assert r["source_parcel"][0] == [9.495348, 22.127313]
    assert r["source_road_width"] == 10.0
    assert r["topology_families_explored"] == [f"PILOT-H{i:02d}" for i in range(1, 7)]
    assert r["candidate_count"] == 72


def test_frontage_functions_are_explicit_and_vehicle_width_is_not_regulation():
    r = _result()
    assert r["vehicle_entrance_width_search"]["classification"] == "engineering_design_search_range"
    assert not r["vehicle_entrance_width_search"]["regulatory_requirement"]
    for candidate in r["candidates"]:
        allocation = candidate["frontage_allocation"]
        assert allocation["three_functions_explicitly_separated"]
        assert candidate["vehicle_entrance"] and candidate["pedestrian_entrance"] and candidate["commercial_entrance"]


def test_capacity_comes_from_generated_stalls_and_searches_two_and_three():
    r = _result()
    assert {c["parking_count"] for c in r["candidates"]} == {2, 3}
    assert all(c["parking_count"] == len(c["parking_stalls"]) for c in r["candidates"])
    assert all(c["independently_usable_parking_count"] == 0 for c in r["candidates"])


def test_topology_validation_rejects_actual_overlap_but_not_missing_vehicle_model():
    r = _result()
    valid = [c for c in r["candidates"] if c["hard_geometry_status"] == "hard_valid"]
    rejected = [c for c in r["candidates"] if c["hard_geometry_status"] == "not_feasible"]
    assert valid and rejected
    assert all(c["vehicle_maneuvering_status"] == "pending_vehicle_model_validation" for c in valid)
    assert all(not c["vehicle_swept_path_generated"] for c in valid)
    assert any("core_stall_overlap" in c["hard_rejection_reasons"] for c in rejected)


def test_promising_candidates_have_coherent_commercial_metrics_and_core_access():
    r = _result()
    assert 3 <= len(r["promising_candidates"]) <= 5
    required = {"commercial_area", "commercial_frontage", "largest_contiguous_usable_field",
                "largest_usable_rectangle", "average_depth", "maximum_depth", "compactness",
                "convexity", "narrow_neck", "rear_tail", "core_induced_fragmentation"}
    for candidate in r["promising_candidates"]:
        assert required <= set(candidate["commercial_quality"])
        assert candidate["commercial_quality_status"] == "quality_valid_for_human_review"
        assert candidate["pedestrian_access_status"] == "resolved"
        assert candidate["core"]["source"] == "scenario_b_joint_parking_core_topology_search"


def test_no_final_selection_and_scenario_a_state_is_preserved():
    base, scenario_a = _inputs()
    before = _digest(base), _digest(scenario_a)
    r = PilotParkingWholePlanTopologySearchV1().resolve(base["site"], base["requirements"], scenario_a)
    assert (_digest(base), _digest(scenario_a)) == before
    assert r["final_scenario_b_candidate"] is None and not r["final_selection_performed"]
    assert r["scenario_b_worthy_of_final_comparison"] == "pending_human_architect_review"
    assert not r["program_changed"] and not r["basement_deleted"] and not r["basement_removal_approved"]
    assert not r["structure_executed"] and not r["bim_executed"] and not r["ifc_executed"]
