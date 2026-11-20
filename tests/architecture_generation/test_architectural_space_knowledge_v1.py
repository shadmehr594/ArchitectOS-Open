import json
from pathlib import Path

import pytest

from core.architecture.knowledge.architectural_space_knowledge_v1 import (
    ArchitecturalKnowledgeResolver as R, EDGE_TYPES, HABITABLE_FLOOR,
    MINAB_OVERLAY, NATIONAL_DAYLIGHT_RULES, Provenance, SPACE_SPECS,
)


def rule(rule_id): return next(x for x in NATIONAL_DAYLIGHT_RULES if x["id"] == rule_id)


def test_01_bedroom_transit_forbidden(): assert "PASS_THROUGH_FORBIDDEN" in SPACE_SPECS["BEDROOM_SINGLE"]["circulation_role"]
def test_02_living_distributor(): assert "DISTRIBUTOR" in SPACE_SPECS["LIVING_RECEPTION"]["circulation_role"]
def test_03_open_kitchen_no_door(): assert SPACE_SPECS["OPEN_KITCHEN"]["requires_door"] == "NOT_REQUIRED"
@pytest.mark.parametrize("s", ["ENSUITE","FAMILY_BATHROOM","GUEST_WC","SEPARATE_WC"])
def test_04_bath_wc_no_transit(s): assert "PASS_THROUGH_FORBIDDEN" in SPACE_SPECS[s]["circulation_role"]
def test_05_corridor_derived(): assert "DERIVED_NOT_TARGET_ROOM" in SPACE_SPECS["PRIVATE_HALL_CORRIDOR"]["special_validation_rules"]
def test_06_lightwell_void_common_capable(): assert SPACE_SPECS["LIGHTWELL"]["circulation_role"] == "ENVIRONMENTAL_VOID" and "COMMON" in SPACE_SPECS["LIGHTWELL"]["common_private_ownership_semantics"]
def test_07_pilotis_not_parking(): assert SPACE_SPECS["PILOTIS"]["semantic_class"] != SPACE_SPECS["PARKING_BAY"]["semantic_class"]
def test_08_parking_access_maneuver(): assert not R.validate_circulation({"p":"PARKING_BAY"},[])["passed"]
def test_09_commercial_frontage(): assert "PUBLIC_FRONTAGE_EXPECTED" in SPACE_SPECS["COMMERCIAL_SHOP"]["special_validation_rules"]
def test_10_unit_hierarchy_valid(): assert R.validate_circulation({"e":"UNIT_ENTRY","l":"LIVING_RECEPTION","h":"PRIVATE_HALL_CORRIDOR","b":"BEDROOM_SINGLE"},[("e","l","OPEN_CONNECTION"),("l","h","PUBLIC_TO_PRIVATE_TRANSITION"),("h","b","DOOR_CONNECTION")])["passed"]
def test_11_bedroom_through_bedroom_invalid(): assert not R.validate_circulation({"a":"BEDROOM_SINGLE","b":"BEDROOM_DOUBLE","h":"PRIVATE_HALL_CORRIDOR"},[("h","a","DOOR_CONNECTION"),("a","b","DOOR_CONNECTION")])["passed"]
def test_12_bath_through_bedroom_invalid(): assert not R.validate_circulation({"h":"PRIVATE_HALL_CORRIDOR","b":"BEDROOM_SINGLE","w":"FAMILY_BATHROOM"},[("h","b","DOOR_CONNECTION"),("b","w","DOOR_CONNECTION")])["passed"]
def test_13_common_landing_before_entry(): assert "SAME_LEVEL_BEFORE_UNIT_ENTRY" in SPACE_SPECS["COMMON_LANDING"]["special_validation_rules"]
def test_14_core_vertical_alignment(): assert "VERTICALLY_ALIGNED_CONTRACT" in SPACE_SPECS["STAIR"]["special_validation_rules"]
def test_15_vehicle_pedestrian_distinct(): assert "VEHICLE_ACCESS" in EDGE_TYPES and "COMMON_TO_PRIVATE_ENTRY" in EDGE_TYPES
def test_16_court_12_3(): r=rule("HABITABLE_COURT_GROUP_1_5"); assert r["claims"]["minimum_area_m2"]["value"]==12 and r["claims"]["minimum_width_m"]["value"]==3
def test_17_kitchen_court_6_2(): r=rule("KITCHEN_STORAGE_COURT_GROUP_1_5"); assert r["claims"]["minimum_area_m2"]["value"]==6 and r["claims"]["minimum_width_m"]["value"]==2
def test_18_glazing_1_8(): assert rule("GLAZING_DEFAULT")["claim"]["value"]=="1/8"
def test_19_glazing_1_7(): assert rule("GLAZING_ONE_WINDOW_DEPTH_GT_4_5")["claim"]["value"]=="1/7"
def test_20_depth_7m(): assert rule("MAX_DAYLIGHT_DEPTH")["claim"]["value"]==7
def test_21_skylight_unresolved_not_invented(): assert rule("SKYLIGHT_MAX_REQUIRED_LIGHT_SHARE")["status"]=="UNRESOLVED_SOURCE_REQUIRED"
def test_22_habitable_floors(): assert [HABITABLE_FLOOR[x]["value"] for x in ("minimum_area_m2","minimum_clear_width_m","minimum_clear_height_m")]==[6.5,2.15,2.4]
def test_23_minab_not_loaded_elsewhere(): assert not any(x.get("provenance")==Provenance.MINAB_LOCAL_VERIFIED_RULE.value for x in R.resolve("BEDROOM_SINGLE","TEHRAN")["applied_rules"])
def test_24_missing_minab_warns_not_number(): assert any("UNRESOLVED_LOCAL_RULE" in x for x in R.resolve("BEDROOM_SINGLE","MINAB")["warnings"])
def test_25_user_rule_activates_and_is_tagged(): assert R.resolve("BEDROOM_SINGLE",user_requirements={"preferred_area_m2":12})["knowledge"]["preferred_area_m2"]["provenance"]==Provenance.USER_REQUESTED_PROJECT_RULE.value
def test_26_living_quality_rank(): assert R.assess_daylight("LIVING_RECEPTION","PUBLIC_STREET")["DAYLIGHT_ARCHITECTURAL_QUALITY"]["score"] > R.assess_daylight("LIVING_RECEPTION","VALID_LIGHTWELL")["DAYLIGHT_ARCHITECTURAL_QUALITY"]["score"]
def test_27_bed_valid_lightwell_when_legal(): assert R.assess_daylight("BEDROOM_SINGLE","VALID_LIGHTWELL",source_legal=True)["DAYLIGHT_LEGALITY"]["passed"]
def test_28_room_window_invalid(): assert not R.assess_daylight("BEDROOM_SINGLE","ROOM_TO_ROOM_WINDOW")["DAYLIGHT_LEGALITY"]["passed"]
def test_29_open_plan_kitchen_shared_light(): assert R.assess_daylight("OPEN_KITCHEN","BORROWED_OPEN_PLAN_DAYLIGHT",source_legal=True,open_plan_same_field=True)["DAYLIGHT_LEGALITY"]["passed"]
def test_30_lightwell_after_deficit_strategy_in_artifact():
    p=Path(__file__).parents[2]/"outputs"/"ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01"/"DAYLIGHT_REASONING_MODEL.json"
    assert json.loads(p.read_text(encoding="utf-8"))["strategy_order"][4]=="SYNTHESIZE_COURTYARD_OR_LIGHTWELL_ONLY_IF_NEEDED"
def test_31_bedroom_variant_numbers_not_regulation():
    for s in ("BEDROOM_SINGLE","BEDROOM_DOUBLE","MASTER_BEDROOM_SLEEPING"):
        assert SPACE_SPECS[s]["clear_dimension_requirements"]["design_heuristic"] == {}
def test_32_furniture_can_fail_quality(): assert not R.furniture_proxy("BEDROOM_SINGLE",["SINGLE_BED_ZONE"])["passed"]
def test_33_numeric_provenance():
    for c in HABITABLE_FLOOR.values(): assert c["provenance"] and c["evidence_id"] and c["source"]
def test_34_heuristic_cannot_undercut_law(): assert any("REJECTED_BELOW_VERIFIED_REGULATION" in w for w in R.resolve("BEDROOM_SINGLE",user_requirements={"minimum_area_m2":5})["warnings"])
def test_35_every_required_space_exists():
    required={"UNIT_ENTRY","FOYER_SHOE_OFF","LIVING_RECEPTION","GENERAL_HALL","DINING","OPEN_KITCHEN","CLOSED_KITCHEN","BEDROOM_SINGLE","BEDROOM_DOUBLE","MASTER_BEDROOM_SLEEPING","DRESSING","ENSUITE","FAMILY_BATHROOM","GUEST_WC","SEPARATE_WC","STORAGE_LINEN","LAUNDRY_UTILITY","PRIVATE_HALL_CORRIDOR","TERRACE_BALCONY","PRIVATE_YARD","COURTYARD","LIGHTWELL","COMMON_ENTRANCE","LOBBY","COMMON_CORRIDOR_GALLERY","COMMON_LANDING","STAIR","ELEVATOR","ELEVATOR_LOBBY","COMMON_ROOF","ROOF_SERVICE_ENCLOSURE","SHARED_LIGHTWELL_COURTYARD","PILOTIS","PARKING_BAY","MANEUVER_ZONE","SHARED_VEHICLE_PEDESTRIAN_ACCESS","PEDESTRIAN_ONLY_ACCESS","COMMERCIAL_SHOP","COMMERCIAL_ENTRANCE_FRONTAGE","SERVICE_LOADING_ZONE"}
    assert required <= SPACE_SPECS.keys()
