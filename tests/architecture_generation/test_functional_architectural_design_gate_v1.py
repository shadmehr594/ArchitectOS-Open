import json
from pathlib import Path

from core.architecture.reasoning.architectural_topology_grammar_v1 import AccessEdge, EdgeType, detect_mechanical_grid, furniture_proxy, validate_access_graph, validate_composition
from core.architecture.reasoning.functional_architectural_design_gate_v1 import FunctionalArchitecturalDesignGateV1, room


def candidate():
    return FunctionalArchitecturalDesignGateV1().build()


def test_01_bedroom_cannot_be_transit_node():
    spaces=[room("H","R1","PRIVATE_HALL_CORRIDOR","U",[0,0,1.1,3]),room("B","R1","BEDROOM","U",[1.1,0,4.1,3.4]),room("X","R1","STORAGE_LINEN","U",[4.1,0,5.1,2])]
    edges=[AccessEdge("H","B",EdgeType.DOOR_CONNECTION),AccessEdge("B","X",EdgeType.DOOR_CONNECTION,True)]
    assert any("FORBIDDEN_TRANSIT_NODE:B" in x for x in validate_access_graph(spaces,edges).failures)


def test_02_bath_wc_cannot_be_transit_node():
    spaces=[room("H","R1","PRIVATE_HALL_CORRIDOR","U",[0,0,1.1,3]),room("W","R1","GUEST_WC","U",[1.1,0,2.3,2]),room("B","R1","BEDROOM","U",[2.3,0,5.3,3.4])]
    edges=[AccessEdge("H","W",EdgeType.DOOR_CONNECTION),AccessEdge("W","B",EdgeType.DOOR_CONNECTION,True)]
    assert any("FORBIDDEN_TRANSIT_NODE:W" in x for x in validate_access_graph(spaces,edges).failures)


def test_03_corridor_serves_multiple_rooms():
    c=candidate(); deg=c["proofs"]["composition"]["access_graph"]["metrics"]["degrees"]
    assert deg["R1_PRIVATE_HALL"] >= 5


def test_04_living_can_distribute_when_intentional():
    edges={x["a"]+":"+x["b"]:x for x in candidate()["access_edges"]}
    assert edges["R1_LIVING:R1_PRIVATE_HALL"]["intentional_transit"]


def test_05_open_kitchen_has_no_door_default():
    c=candidate(); pairs={frozenset((d["from_space"],d["to_space"])) for d in c["door_intents"]}
    assert frozenset(("R1_DINING","R1_KITCHEN")) not in pairs


def test_06_closed_kitchen_may_require_door():
    from core.architecture.contracts.functional_space_ontology_v1 import resolve_space_type
    assert resolve_space_type("CLOSED_KITCHEN").requires_door == "YES"


def test_07_lightwell_shared_by_two_units():
    proof=candidate()["proofs"]["daylight"]
    assert set(proof["shared_lightwell_units"]) == {"R2_U1","R2_U2"}


def test_08_common_core_not_private():
    for s in candidate()["spaces"]:
        if s["semantic"] in {"STAIR","ELEVATOR_LOBBY","COMMON_CORRIDOR_LANDING"}: assert s["owner"] == "COMMON"


def test_09_unit_entries_originate_at_common_landing():
    assert candidate()["proofs"]["landing"]["passed"]


def test_10_unsafe_stair_door_fails():
    spaces=[room("L","R1","COMMON_CORRIDOR_LANDING","COMMON",[0,0,2,2]),room("E","R1","ENTRANCE_SHOE_OFF","U",[2,0,3.5,2],unsafe_fall_zone=True)]
    result=validate_access_graph(spaces,[AccessEdge("L","E",EdgeType.COMMON_TO_PRIVATE_ENTRY,door_required=True)])
    assert any("UNSAFE_STAIR_DOOR_FALL_ZONE" in x for x in result.failures)


def test_11_parking_routes_from_south_are_obstacle_free():
    p=candidate()["proofs"]["parking"]; assert p["passed"] and len(p["routes"]) == 3 and p["obstacle_free"]


def test_12_maneuver_zone_exists():
    assert any(s["semantic"]=="VEHICLE_MANEUVER_ZONE" for s in candidate()["spaces"])


def test_13_repetitive_equal_grid_fails():
    semantics=["BEDROOM","GUEST_WC","OPEN_KITCHEN","LIVING_RECEPTION","DINING","STORAGE_LINEN"]
    spaces=[room(str(i),"R1",semantics[i%len(semantics)],"U",[(i%4)*2,(i//4)*2,(i%4)*2+2,(i//4)*2+2]) for i in range(20)]
    assert "MECHANICAL_GRID_PACKING_DETECTED" in detect_mechanical_grid(spaces).failures


def test_14_identical_area_spam_fails():
    semantics=["BEDROOM","GUEST_WC","OPEN_KITCHEN","LIVING_RECEPTION","DINING"]
    spaces=[room(str(i),"R1",semantics[i%5],"U",[i*3,0,i*3+2,2]) for i in range(10)]
    assert "IDENTICAL_AREA_SPAM_ACROSS_UNRELATED_SPACE_TYPES" in detect_mechanical_grid(spaces).failures


def test_15_ground_and_roof_mandatory():
    c=candidate(); spaces=[s for s in c["spaces"] if s["level"] not in {"G","ROOF"}]
    result=validate_composition(spaces,[])
    assert "MANDATORY_LEVEL_MISSING:G" in result["failures"] and "MANDATORY_LEVEL_MISSING:ROOF" in result["failures"]


def test_16_separation_joint_concept_present_ne_w():
    c=candidate()
    for level in ("R1","R2"):
        assert any(s["level"]==level and set(s.get("separation_joint_edges",[])) >= {"N","E","W"} for s in c["spaces"])
    assert FunctionalArchitecturalDesignGateV1.SEPARATION_NOTE.endswith("NOT DEDUCTED")


def test_17_dimensions_differ_by_function():
    c=candidate(); dims={s["semantic"]:tuple(round(s["rect"][i+2]-s["rect"][i],2) for i in range(2)) for s in c["spaces"] if s["level"]=="R1"}
    assert len(set(dims.values())) >= 8


def test_18_furniture_proxy_rejects_undersized_bedroom():
    assert not furniture_proxy(room("B","R1","BEDROOM","U",[0,0,1.8,2.2]))["passed"]


def test_19_no_automatic_door_on_every_space():
    c=candidate(); assert len(c["door_intents"]) < len(c["spaces"])-2 and all(not d["automatic_default"] for d in c["door_intents"])


def test_20_r2_units_independent_but_share_common_environment():
    c=candidate(); private=[e for e in c["access_edges"] if e["a"].startswith("R2_U1") and e["b"].startswith("R2_U2") or e["a"].startswith("R2_U2") and e["b"].startswith("R2_U1")]
    assert not private
    assert sum(1 for e in c["access_edges"] if "R2_LIGHTWELL" in {e["a"],e["b"]}) == 4


def test_21_full_candidate_passes_readiness_but_human_stays_pending():
    c=candidate(); assert c["proofs"]["composition"]["passed"], c["proofs"]["composition"]["failures"]
    assert c["acceptance"] == {"software_architectural_readiness":"PASS","human_architectural_acceptance":"PENDING","human_approval_is_user_decision":True}


def test_22_previous_grid_is_machine_readable_negative_precedent():
    path=Path(__file__).parents[2]/"core/architecture/contracts/parcel2_human_rejection_20260920_v1.json"
    data=json.loads(path.read_text(encoding="utf-8")); assert data["human_architectural_acceptance"]=="REJECTED"
    assert data["source_code_signature"]["hard_failure_code"]=="MECHANICAL_GRID_PACKING_DETECTED"


def test_23_all_four_levels_and_three_parking_bays_are_designed():
    c=candidate(); assert {s["level"] for s in c["spaces"]}=={"G","R1","R2","ROOF"}
    assert len([s for s in c["spaces"] if s["semantic"]=="PARKING_BAY"])==3


def test_24_historical_rejection_is_not_rewritten_as_pending():
    c=candidate(); old=c["human_verdict_on_previous_candidate"]
    assert old["human_architectural_acceptance"]=="REJECTED" and old["software_acceptance"]=="PASS"
