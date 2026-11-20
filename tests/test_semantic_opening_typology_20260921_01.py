import json
from pathlib import Path

from core.architecture.drawing import ArchitecturalPlanRealizer
from core.architecture.drawing.semantic_opening_typology_v1 import (
    DOOR_TYPOLOGY_LIBRARY, WINDOW_TYPOLOGY_LIBRARY, SemanticOpeningEngine,
    TOPIC4_GLAZING_DEFAULT, door_type_for_connection, window_type_for_room)
from core.architecture.drawing.pdf_architectural_renderer_v1 import PdfArchitecturalRenderer
from core.architecture.drawing.svg_architectural_renderer_v1 import SvgArchitecturalRenderer
from core.architecture.reasoning_engine import ArchitecturalDesignReasoningEngine

ROOT=Path(__file__).resolve().parents[1]
BRIEF={"site_width_m":10,"site_depth_m":20,"north":"TOP","street":"SOUTH","storeys":1,"target_area_m2":120,"ffl_m":.38,"jurisdiction":"MINAB"}

def test_01_entrance_exists_and_not_wc_fallback():
    assert "MAIN_ENTRANCE_DOOR" in DOOR_TYPOLOGY_LIBRARY and DOOR_TYPOLOGY_LIBRARY["MAIN_ENTRANCE_DOOR"]["nominal_width_m"] != DOOR_TYPOLOGY_LIBRARY["WC_DOOR"]["nominal_width_m"]

def test_02_project_hierarchy_bedroom_gt_wc():
    assert DOOR_TYPOLOGY_LIBRARY["MAIN_ENTRANCE_DOOR"]["nominal_width_m"] > DOOR_TYPOLOGY_LIBRARY["BEDROOM_DOOR"]["nominal_width_m"] > DOOR_TYPOLOGY_LIBRARY["WC_DOOR"]["nominal_width_m"]

def test_03_door_leaf_and_arc_match_clear_width():
    e=SemanticOpeningEngine(); d={"id":"D1","type":"BEDROOM_DOOR","clear_width_m":.9,"graphic_leaf_length_m":.9,"graphic_arc_radius_m":.9}
    assert e.validate([d],[])["status"]=="PASS"
    d["graphic_arc_radius_m"]=.8
    assert e.validate([d],[])["findings"][0]["code"]=="DOOR_GRAPHICS_NOT_MATCHING_CLEAR_WIDTH"

def test_04_living_window_larger_than_bedroom_comparable_host():
    assert WINDOW_TYPOLOGY_LIBRARY["LIVING_RECEPTION_WINDOW"]["preferred_relative_aperture"]=="XL"
    assert WINDOW_TYPOLOGY_LIBRARY["BEDROOM_WINDOW"]["preferred_relative_aperture"]=="M"

def test_05_bedroom_aperture_meets_verified_rule():
    out=SemanticOpeningEngine().size_windows("bedroom",12,[3.2],TOPIC4_GLAZING_DEFAULT)
    assert out["status"]=="PASS" and out["achieved_glazing_area_m2"]>=out["target_glazing_area_m2"]
    assert out["daylight_rule"]["classification"]=="VERIFIED_REGULATION"

def test_06_kitchen_window_avoids_cabinet_conflict():
    out=SemanticOpeningEngine().size_windows("kitchen",10,[3.0],TOPIC4_GLAZING_DEFAULT,conflicts_m=[.7])
    assert out["status"]=="PASS" and out["sill_m"]>=1.1

def test_07_service_window_is_high_level_private():
    for t in ("BATHROOM_WINDOW","WC_WINDOW"):
        assert WINDOW_TYPOLOGY_LIBRARY[t]["preferred_configuration"]=="HIGH_LEVEL_SERVICE_WINDOW"
        assert "PRIVACY" in WINDOW_TYPOLOGY_LIBRARY[t]["glazing_privacy_behavior"]

def test_08_identical_windows_across_roles_fail():
    ws=[{"id":"W1","type":"LIVING_RECEPTION_WINDOW","width_m":1.2},{"id":"W2","type":"BEDROOM_WINDOW","width_m":1.2}]
    assert SemanticOpeningEngine().validate([],ws)["findings"][0]["code"]=="WINDOW_SIZE_IGNORES_ROOM_FUNCTION"

def test_09_window_constrained_by_host():
    out=SemanticOpeningEngine().validate([],[{"id":"W","type":"LIVING_RECEPTION_WINDOW","width_m":2.4,"host_available_m":1.8}])
    assert any(x["code"]=="WINDOW_SIZE_NOT_SUPPORTED_BY_HOST_WALL" for x in out["findings"])

def test_10_schedule_matches_realized_geometry():
    engine=ArchitecturalDesignReasoningEngine(); state=engine.synthesize(BRIEF,1)[0]
    scene=ArchitecturalPlanRealizer().realize(engine.to_candidate_contract(state))
    schedule=scene.metadata["opening_schedule"]
    leaves={p.metadata["door_id"]:p.metadata["clear_width_m"] for p in scene.primitives if p.layer=="DOORS" and p.metadata.get("component")=="leaf"}
    assert all(abs(leaves[d["id"]]-d["clear_width_m"])<1e-6 for d in schedule["doors"])

def test_11_prior_cumulative_learning_registry_preserved():
    p=ROOT/'outputs'/'RESIDENTIAL_PATTERN_LIBRARY_20260920_01'/'UPDATED_CUMULATIVE_HUMAN_LEARNING_REGISTRY.json'
    assert p.exists() and p.stat().st_size>0

def test_12_semantic_geometry_consistency_regression():
    engine=ArchitecturalDesignReasoningEngine()
    for state in engine.synthesize(BRIEF,4):
        scene=ArchitecturalPlanRealizer().realize(engine.to_candidate_contract(state))
        assert scene.metadata["opening_graphics_audit"]["status"]=="PASS"

def test_13_pdf_svg_preserve_type_and_size_differences(tmp_path):
    engine=ArchitecturalDesignReasoningEngine(); state=engine.synthesize(BRIEF,1)[0]
    scene=ArchitecturalPlanRealizer().realize(engine.to_candidate_contract(state))
    pdf=tmp_path/'opening.pdf'; svg=tmp_path/'opening.svg'; PdfArchitecturalRenderer().render(scene,pdf); SvgArchitecturalRenderer().render(scene,svg)
    assert pdf.stat().st_size>1000 and svg.stat().st_size>1000
    types={x["type"] for x in scene.metadata["opening_schedule"]["windows"]}
    configs={x["configuration"] for x in scene.metadata["opening_schedule"]["windows"]}
    assert len(types)>1 and len(configs)>1

def test_semantic_selectors_and_provenance():
    assert door_type_for_connection("hall","guest_wc")=="WC_DOOR"
    assert window_type_for_room("living")=="LIVING_RECEPTION_WINDOW"
    assert all(x["provenance"]["nominal_dimensions"]=="DESIGN_HEURISTIC" for x in DOOR_TYPOLOGY_LIBRARY.values())
