from core.architecture.drawing import ArchitecturalPlanRealizer
from core.architecture.drawing.semantic_opening_semantics_v2 import (
    DOOR_SEMANTIC_LIBRARY as D, WINDOW_SEMANTIC_LIBRARY as W,
    ResidentialOpeningSemanticEngine, ResidentialOpeningHeuristicProfileV1,
    door_type_for_connection, window_type_for_room)
from core.architecture.reasoning_engine import ArchitecturalDesignReasoningEngine

BRIEF={"site_width_m":10,"site_depth_m":20,"north":"TOP","street":"SOUTH","storeys":1,"target_area_m2":120,"ffl_m":.38,"jurisdiction":"MINAB"}

def scenes():
    e=ArchitecturalDesignReasoningEngine(); return [ArchitecturalPlanRealizer().realize(e.to_candidate_contract(s)) for s in e.synthesize(BRIEF,4)]

def test_01_required_semantic_classes():
    assert {"MAIN_ENTRY_DOOR","UNIT_ENTRY_DOOR","BEDROOM_DOOR","MASTER_BEDROOM_DOOR","BATHROOM_DOOR","WC_DOOR","KITCHEN_DOOR","COURTYARD_DOOR","TERRACE_DOOR","SERVICE_DOOR","VEHICLE_GATE","PEDESTRIAN_GATE"} <= set(D)
    assert {"LIVING_PRIMARY_WINDOW","LIVING_SECONDARY_WINDOW","BEDROOM_WINDOW","MASTER_BEDROOM_WINDOW","KITCHEN_WINDOW","BATHROOM_WINDOW","WC_WINDOW","COURTYARD_FACING_WINDOW","REAR_YARD_WINDOW","SIDE_YARD_WINDOW","TERRACE_GLAZED_OPENING"} <= set(W)

def test_02_04_relative_hierarchy():
    h=ResidentialOpeningSemanticEngine().validate_hierarchy(); assert h["status"]=="PASS" and all(h["checks"].values())

def test_05_kitchen_differs_from_living(): assert window_type_for_room("kitchen") != window_type_for_room("living")
def test_06_service_natural_windows(): assert window_type_for_room("guest_wc")=="WC_WINDOW" and window_type_for_room("bath")=="BATHROOM_WINDOW"
def test_07_all_dimensions_have_provenance(): assert all(x["provenance"]["selected_dimensions"] for x in list(D.values())+list(W.values()))
def test_08_no_heuristic_labeled_regulation(): assert ResidentialOpeningHeuristicProfileV1["regulatory_status"]=="NOT_A_REGULATION"

def test_09_14_realized_geometry_schedule_and_graphics():
    for scene in scenes():
        a=scene.metadata["opening_graphics_audit"]; s=scene.metadata["opening_schedule"]
        assert a["status"]=="PASS" and a["source_proof_preserved"] and a["required_opening_bijection_preserved"]
        assert any(x["type"]=="MAIN_ENTRY_DOOR" for x in s["doors"])
        assert len({x["graphic_variant"] for x in s["doors"]})>1 and len({x["graphic_variant"] for x in s["windows"]})>1
        assert all(x["width"] and x["height"] and x["provenance"] for x in s["rows"])

def test_15_access_daylight_orientation_regression():
    e=ArchitecturalDesignReasoningEngine()
    for state in e.synthesize(BRIEF,4):
        assert state.daylight_source_graph and state.street_access_edges==["SOUTH"] and not state.unresolved_constraints

def test_16_learning_registry_active():
    from core.architecture.learning.cumulative_human_learning_v2 import cumulative_learning_items
    active={x["generalized_rule"] for x in cumulative_learning_items() if x["active"]}
    assert {"OPENING_TYPE_DEPENDS_ON_SPACE_FUNCTION","MAIN_ENTRY_DOOR_LARGER_THAN_INTERNAL_PRIVATE_DOORS","DOOR_WINDOW_GRAPHICS_MUST_REFLECT_SEMANTIC_TYPE"} <= active
