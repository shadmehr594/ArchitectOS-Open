from dataclasses import asdict
from pathlib import Path

from core.architecture.drawing import ArchitecturalPlanRealizer
from core.architecture.drawing.semantic_opening_typology_v1 import (
    DOOR_TYPOLOGY_LIBRARY, WINDOW_TYPOLOGY_LIBRARY, SemanticOpeningEngine,
    TOPIC4_GLAZING_DEFAULT, door_type_for_connection, window_type_for_room)
from core.architecture.drawing.pdf_architectural_renderer_v1 import PdfArchitecturalRenderer
from core.architecture.drawing.svg_architectural_renderer_v1 import SvgArchitecturalRenderer
from core.architecture.learning.cumulative_human_learning_v2 import cumulative_learning_items
from core.architecture.reasoning_engine import ArchitecturalDesignReasoningEngine

BRIEF={"site_width_m":10,"site_depth_m":20,"north":"TOP","street":"SOUTH","storeys":1,"target_area_m2":120,"ffl_m":.38,"jurisdiction":"MINAB"}

def test_01_main_entrance_resolves_wider_than_bedroom():
    e=SemanticOpeningEngine()
    assert e.resolved_door_spec("MAIN_ENTRANCE_DOOR").nominal_width_m > e.resolved_door_spec("BEDROOM_DOOR").nominal_width_m

def test_02_bedroom_wider_than_wc_and_bath_default_heuristic():
    e=SemanticOpeningEngine(); bed=e.resolved_door_spec("BEDROOM_DOOR")
    assert bed.nominal_width_m > e.resolved_door_spec("WC_DOOR").nominal_width_m
    assert bed.nominal_width_m > e.resolved_door_spec("BATHROOM_DOOR").nominal_width_m
    assert bed.min_width_source["regulatory_status"]=="NOT_ASSERTED_AS_LAW"

def test_03_open_kitchen_has_no_fake_door():
    try: door_type_for_connection("living","open_kitchen",closed_kitchen=False)
    except ValueError as exc: assert str(exc)=="OPEN_KITCHEN_MUST_NOT_RECEIVE_DOOR"
    else: raise AssertionError("open kitchen received a door")

def test_04_living_window_larger_when_context_allows():
    e=SemanticOpeningEngine()
    living=e.size_windows("living",24,[5.0],TOPIC4_GLAZING_DEFAULT)
    bed=e.size_windows("bedroom",12,[5.0],TOPIC4_GLAZING_DEFAULT)
    assert living["status"]==bed["status"]=="PASS" and living["width_m"]>bed["width_m"]

def test_05_wc_bath_windows_are_compact_private():
    for kind in ("WC_WINDOW","BATHROOM_WINDOW"):
        spec=SemanticOpeningEngine().resolved_window_spec(kind)
        assert spec.privacy_class in {"HIGH","VERY_HIGH"} and spec.graphical_symbol_class=="WINDOW_PRIVACY_HIGH_LEVEL"

def test_06_kitchen_window_avoids_tall_cabinet_interval():
    out=SemanticOpeningEngine().size_windows("kitchen",10,[3.4],TOPIC4_GLAZING_DEFAULT,conflict_intervals=[(0,1.0)])
    assert out["status"]=="PASS" and out["selected_clear_runs"][0]["start_m"]>=1.1

def test_07_bedroom_window_avoids_wardrobe_bed_conflicts_when_alternative_exists():
    out=SemanticOpeningEngine().size_windows("bedroom",12,[4.2],TOPIC4_GLAZING_DEFAULT,conflict_intervals=[(0,.8),(2.0,2.8)])
    assert out["status"]=="PASS"
    chosen=out["selected_clear_runs"][0]
    assert chosen["start_m"]>=2.9 or chosen["end_m"]<=1.9

def test_08_daylight_uses_area_and_rule_provenance():
    out=SemanticOpeningEngine().size_windows("bedroom",16,[4],TOPIC4_GLAZING_DEFAULT,room_depth_m=4.2)
    assert out["target_glazing_area_m2"]==2.0 and out["daylight_rule"]["classification"]=="VERIFIED_REGULATION" and out["room_depth_m"]==4.2

def test_09_insufficient_host_hard_fails_without_shrinking():
    out=SemanticOpeningEngine().size_windows("living",30,[.7],TOPIC4_GLAZING_DEFAULT)
    assert out["status"]=="FAIL" and out["findings"][0]["code"]=="WINDOW_AREA_REQUIREMENT_NOT_REALIZABLE"

def test_10_graphical_symbol_classes_differ():
    door_symbols={DOOR_TYPOLOGY_LIBRARY[x]["graphical_symbol_class"] for x in ("MAIN_ENTRANCE_DOOR","BEDROOM_DOOR","WC_DOOR","TERRACE_BALCONY_DOOR")}
    window_symbols={WINDOW_TYPOLOGY_LIBRARY[x]["graphical_symbol_class"] for x in ("LIVING_RECEPTION_WINDOW","BEDROOM_WINDOW","WC_WINDOW")}
    assert len(door_symbols)==4 and len(window_symbols)==3

def test_11_pdf_svg_scene_preserves_opening_types(tmp_path):
    engine=ArchitecturalDesignReasoningEngine(); scene=ArchitecturalPlanRealizer().realize(engine.to_candidate_contract(engine.synthesize(BRIEF,1)[0]))
    pdf=tmp_path/"typed.pdf"; svg=tmp_path/"typed.svg"
    PdfArchitecturalRenderer().render(scene,pdf); SvgArchitecturalRenderer().render(scene,svg)
    schedule=scene.metadata["opening_schedule"]
    assert pdf.stat().st_size>1000 and svg.stat().st_size>1000
    assert len({x["graphical_symbol_class"] for x in schedule["doors"]})>1
    assert len({x["graphical_symbol_class"] for x in schedule["windows"]})>1

def test_12_future_dwg_mapping_exists_on_every_type():
    assert all(x["future_dwg_mapping"]["block"] and x["future_dwg_mapping"]["layer"] for x in DOOR_TYPOLOGY_LIBRARY.values())
    assert all(x["future_dwg_mapping"]["block"] and x["future_dwg_mapping"]["layer"] for x in WINDOW_TYPOLOGY_LIBRARY.values())
    assert asdict(SemanticOpeningEngine().resolved_door_spec("BEDROOM_DOOR"))["semantic_type"]=="BEDROOM_DOOR"

def test_13_prior_rules_and_new_learning_remain_active():
    rules={x["generalized_rule"] for x in cumulative_learning_items() if x["active"]}
    assert {"GRAPH_GEOMETRY_OPENING_MATCH","ENTRANCE_ARRIVAL_SEQUENCE","DOOR_SIZE_AND_TYPE_DEPENDS_ON_FUNCTION","OPENING_TYPOLOGY_MUST_BE_GRAPHICALLY_DISTINCT"} <= rules

