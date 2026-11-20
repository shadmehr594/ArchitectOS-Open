from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(r"<repo-root>")
sys.path.insert(0, str(ROOT/"core/architecture/reasoning"))
from parcel2_floor_level_residential_synthesis_v6 import FloorLevelResidentialSynthesisV6, LEDGER_KEYS, verify_authority

V4 = ROOT/"exports/DEFAULT/parcel2_residential_room_planning_daylight_v4_20260913_131505/PARCEL2_RESIDENTIAL_ROOM_PLANNING_DAYLIGHT_V4.json"
EV = ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"
HISTORICAL = [
    ROOT/"core/architecture/reasoning/parcel2_residential_room_planning_daylight_v3.py",
    ROOT/"core/architecture/reasoning/parcel2_residential_room_planning_daylight_v4.py",
    ROOT/"core/architecture/reasoning/parcel2_controlled_geometric_repair_search_v5.py",
    ROOT/"tools/run_parcel2_residential_room_planning_daylight_v3.py",
    ROOT/"tools/run_parcel2_residential_room_planning_daylight_v4.py",
    ROOT/"tools/run_parcel2_controlled_geometric_repair_search_v5.py",
    ROOT/"tests/test_parcel2_residential_room_planning_daylight_v3.py",
    ROOT/"tests/test_parcel2_residential_room_planning_daylight_v4.py",
    ROOT/"tests/test_parcel2_controlled_geometric_repair_search_v5.py", EV, V4,
]


def source(): return json.loads(V4.read_text(encoding="utf-8"))
def engine(): return FloorLevelResidentialSynthesisV6(json.loads(EV.read_text(encoding="utf-8")))
def floors(): return [engine().synthesize(plans) for _, plans in engine().group(source())]


def test_pipeline_authority_and_facade_budget_precedes_rooms():
    assert verify_authority(json.loads(EV.read_text(encoding="utf-8")))["status"] == "PASS"
    pipeline = engine().pipeline
    assert pipeline.index("facade_daylight_budget") < pipeline.index("unit_partitioning") < pipeline.index("room_blocks")
    assert pipeline[-1] == "full_floor_re_evaluation"


def test_determinism_no_input_mutation_and_floor_grouping():
    data = source(); frozen = deepcopy(data)
    groups = engine().group(data)
    assert len(groups) == 12
    for _, plans in groups:
        result = engine().synthesize(plans)
        assert result == engine().synthesize(plans)
        source_polygons = {json.dumps(room["polygon"], sort_keys=True) for item in plans for room in item["rooms"]}
        output_polygons = {json.dumps(room["polygon"], sort_keys=True) for unit in result["units"] for room in unit["rooms"]}
        assert source_polygons.isdisjoint(output_polygons)
    assert data == frozen


def test_full_floor_contains_all_units_and_rf2_is_one_model():
    for plan in floors():
        expected = 2 if plan["identity"]["floor_id"] == "RESIDENTIAL_FLOOR_2" else 1
        assert len(plan["units"]) == expected
        assert plan["checks"]["full_floor_contains_all_units"]
        if expected == 2:
            assert plan["checks"]["rf2_single_floor_model"]
            assert plan["unit_partitioning"]["simultaneous"]
            assert {u["unit_id"] for u in plan["units"]} == {"UNIT-1", "UNIT-2"}


def test_floor_acceptance_is_fail_closed_and_all_checks_are_explicit():
    for plan in floors():
        assert plan["resolved_floor_level"] == (not plan["spatial_problems"])
        assert plan["REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN"] == plan["resolved_floor_level"]
        assert plan["winner"] is None and not plan["authoritative_ranking"]
        assert plan["checks"]["facade_budget_before_rooms"]
        assert plan["checks"]["no_arbitrary_oblique_geometry"]
        assert all(key in plan["allocation"] for key in LEDGER_KEYS)
        assert len(plan["core_common_access"]["stair_polygon"]) >= 3
        assert len(plan["core_common_access"]["elevator_polygon"]) >= 3
        assert plan["precedent"]["invoked"] and not plan["precedent"]["geometry_copied"]
        assert plan["precedent"]["authority_class"] == "PRECEDENT_NON_REGULATORY"
        assert plan["precedent"]["residential_feature_contract"] == "ResidentialFloorPrecedentPatternsV1"
        assert len(plan["precedent"]["source_case_ids"]) == 5
        assert "COMPACT_ENTRY_DISTRIBUTION" in plan["precedent"]["applied_abstract_pattern_ids"]
        assert not plan["agi"]["invoked"]
        for unit in plan["units"]:
            checks = unit["checks"]
            assert {"threshold_on_common_access", "independent_threshold", "short_non_longitudinal_private_circulation", "door_graph",
                    "verified_room_source_window_chain", "wet_service_cluster", "privacy", "furniture_usability", "containment_non_overlap"} <= set(checks)
            assert checks["private_circulation_area_ratio"] <= .10
            assert unit["space_organization"]["longitudinal_spine_created"] is False
            assert unit["space_organization"]["v4_room_geometry_reused"] is False
            assert unit["space_organization"]["precedent_geometry_copied"] is False
            assert {node["role"] for node in unit["private_circulation"]} == {"COMPACT_ENTRY_DISTRIBUTION_NODE", "SHORT_PRIVATE_BRANCH_NODE"}
            assert all(room["geometry_provenance"].startswith("V6_PRECEDENT_GUIDED_PARAMETRIC_CELL") for room in unit["rooms"])
            for door in unit["doors"]:
                assert "host_wall" in door and "opening" in door and "valid" in door
            source_ids = {item["source_id"] for item in unit["daylight_sources"]}
            for window in unit["windows"]:
                assert window["source_id"] in source_ids
                assert window["host_wall"]["verified_room_source_boundary"]
            lightwell = unit["lightwell"]
            assert lightwell["created"] or (lightwell["polygon"] is None and lightwell["area_m2"] == 0)


def test_historical_v3_v4_v5_byte_equal():
    before = {str(path): (sha256(path.read_bytes()).hexdigest(), path.stat().st_size) for path in HISTORICAL}
    floors()
    after = {str(path): (sha256(path.read_bytes()).hexdigest(), path.stat().st_size) for path in HISTORICAL}
    assert before == after
