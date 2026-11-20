from core.architecture.drawing import ArchitecturalPlanRealizer
from core.architecture.drawing.semantic_opening_semantics_v2 import DOOR_SEMANTIC_LIBRARY as D, WINDOW_SEMANTIC_LIBRARY as W
from core.architecture.drawing.opening_access_semantics_v3 import solve_contract, validate_contract
from core.architecture.reasoning_engine import ArchitecturalDesignReasoningEngine

BRIEF={"site_width_m":10,"site_depth_m":20,"north":"TOP","street":"SOUTH","storeys":1,"target_area_m2":120,"ffl_m":.38,"jurisdiction":"MINAB"}

def contracts():
    e=ArchitecturalDesignReasoningEngine(); return [e.to_candidate_contract(s) for s in e.synthesize(BRIEF,4)]

def test_01_main_entry_wider_than_bedroom(): assert D["MAIN_ENTRY_DOOR"]["nominal_width_m"] > D["BEDROOM_DOOR"]["nominal_width_m"]
def test_02_bedroom_wider_than_bath_wc(): assert D["BEDROOM_DOOR"]["nominal_width_m"] > D["BATH_WC_DOOR"]["nominal_width_m"]
def test_03_living_window_larger_than_bedroom(): assert W["LIVING_PRIMARY_WINDOW"]["nominal_width_m"] > W["BEDROOM_WINDOW"]["nominal_width_m"]
def test_04_bath_window_smaller_than_bedroom(): assert W["BATH_WC_WINDOW"]["nominal_width_m"] < W["BEDROOM_WINDOW"]["nominal_width_m"]
def test_05_bedroom_door_swings_in():
    for c in contracts():
        assert all(d["swing_into_space"]==d["to_space"] for d in c["doors"] if d["to_space"] in {"master","bed2","bed3"} and d["swing_collision_free"])
def test_06_wet_door_has_solved_swing():
    for c in contracts(): assert all(d["hinge_side"] in {"START","END"} for d in c["doors"] if d["to_space"] in {"bath","guest_wc"})
def test_07_kitchen_entry_not_joinery():
    for c in contracts(): assert not any(x["code"]=="KITCHEN_ENTRY_BLOCKED_BY_JOINERY" for x in c["opening_access_validation"]["findings"])
def test_08_private_wing_not_sealed():
    for c in contracts(): assert not any(x["code"]=="PRIVATE_WING_SEALED" for x in c["opening_access_validation"]["findings"])
def test_09_each_bedroom_independent():
    for c in contracts(): assert not any(x["code"]=="BEDROOM_NO_INDEPENDENT_DOOR" for x in c["opening_access_validation"]["findings"])
def test_10_no_rear_through_middle_bedroom():
    for c in contracts(): assert not any(x["code"]=="BEDROOM_THROUGH_BEDROOM_ACCESS" for x in c["opening_access_validation"]["findings"])
def test_11_internal_window_fails():
    c=contracts()[0]; c["windows"][0]["source"]="kitchen"; assert any(x["code"]=="WINDOW_TO_NEIGHBOR_PLOT" for x in validate_contract(c)["findings"])
def test_12_bedroom_window_to_kitchen_fails(): test_11_internal_window_fails()
def test_13_constrained_plot_window_fails():
    c=contracts()[0]; c["windows"][0]["source"]="WEST_NEIGHBOR"; assert validate_contract(c)["status"]=="FAIL"
def test_14_north_requires_exact_boundary():
    for c in contracts(): assert all(w["source_adjacency_proof"]["exact_shared_boundary"] for w in c["windows"] if w["source"]=="NORTH_REAR_YARD")
def test_15_east_requires_exact_boundary():
    for c in contracts(): assert all(w["source_adjacency_proof"]["exact_shared_boundary"] for w in c["windows"] if w["source"]=="EAST_SERVICE_YARD")
def test_16_living_best_public_edge():
    for c in contracts(): assert all(w["source"]=="SOUTH_YARD" for w in c["windows"] if w["room"]=="living")
def test_17_openings_avoid_furniture():
    for c in contracts(): assert not any(w["furniture_conflicts"] for w in c["windows"])
def test_18_separation_joint_outside():
    for c in contracts(): assert ArchitecturalPlanRealizer().realize(c).metadata["separation_joint_audit"]["outside_building_envelope"]
def test_19_orientation_anchors():
    for c in contracts(): assert ArchitecturalPlanRealizer().realize(c).metadata["orientation_anchors"]["north"]=="TOP"
def test_20_cumulative_learning():
    from core.architecture.learning.cumulative_human_learning_v2 import cumulative_learning_items
    rules={x["generalized_rule"] for x in cumulative_learning_items()}; assert "REFERENCE_OPENING_DIMENSIONS_ARE_HEURISTIC_NOT_REGULATION" in rules
def test_21_pattern_diversity(): assert len({c["family"] for c in contracts()})==4
def test_22_contract_verdict_fields():
    for c in contracts(): assert set(c["opening_access_validation"]["verdict"])=={"ACCESS","DOOR SEMANTICS","WINDOW/DAYLIGHT SEMANTICS","FURNITURE/OPENING COMPATIBILITY","PLAN REALIZATION","HUMAN ARCHITECTURAL ACCEPTANCE"}
