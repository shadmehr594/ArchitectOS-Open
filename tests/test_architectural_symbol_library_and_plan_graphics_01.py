from core.architecture.drawing.architectural_symbol_library_v1 import SYMBOL_LIBRARY,SPACE_FURNITURE_BUNDLES
from core.architecture.drawing.furniture_placement_validator_v1 import FurniturePlacementValidator
from core.architecture.drawing import ArchitecturalPlanRealizer
from core.architecture.reasoning_engine import ArchitecturalDesignReasoningEngine
from core.architecture.drawing.pdf_architectural_renderer_v1 import PdfArchitecturalRenderer
from core.architecture.drawing.svg_architectural_renderer_v1 import SvgArchitecturalRenderer

REQUIRED={"SINGLE_BED","DOUBLE_BED","MASTER_BED","WARDROBE","SOFA_1","SOFA_2","SOFA_3","L_SOFA","ARMCHAIR","COFFEE_TABLE","TV_MEDIA_UNIT","DINING_TABLE_4","DINING_TABLE_6","DINING_TABLE_8","KITCHEN_BASE_CABINET","REFRIGERATOR","SINK","COOKTOP","OVEN","DISHWASHER","PENINSULA","ISLAND","WC_IRANIAN","WC_WESTERN","WASHBASIN","SHOWER","BATHTUB","FLOOR_DRAIN","WASHING_MACHINE","PORCH_PLATFORM","ENTRY_STEPS","CANOPY","RAMP","PARKED_CAR","PARKING_BAY","TREE","SHRUB_PLANTER"}

def states(): return ArchitecturalDesignReasoningEngine().synthesize({"site_width_m":10,"site_depth_m":20,"north":"TOP","street":"SOUTH","storeys":1,"target_area_m2":120,"ffl_m":.38,"canopy_depth_m":1.2,"jurisdiction":"MINAB","minab_overlay":"CONDITIONAL_EVIDENCE_REQUIRED"},4)
def test_required_symbols_have_vectors(): assert REQUIRED<=set(SYMBOL_LIBRARY) and all(SYMBOL_LIBRARY[x]["vector_primitives"] for x in REQUIRED)
def test_distinct_visual_grammars():
    sig=lambda x:[p["kind"]+":"+p.get("role","") for p in SYMBOL_LIBRARY[x]["vector_primitives"]]
    assert sig("SINGLE_BED")!=sig("WARDROBE")!=sig("DINING_TABLE_6") and sig("SOFA_3")!=sig("MASTER_BED")
    assert sig("WC_IRANIAN")!=sig("WASHBASIN")!=sig("SHOWER") and sig("SINK")!=sig("COOKTOP")!=sig("REFRIGERATOR")
def test_major_space_bundles(): assert {"LIVING","DINING","BEDROOM_SINGLE","BEDROOM_DOUBLE","MASTER","OPEN_KITCHEN","BATH","GUEST_WC","LAUNDRY","PARKING"}<=set(SPACE_FURNITURE_BUNDLES)
def test_placement_failures():
    v=FurniturePlacementValidator(); rooms={"r":[0,0,3,3]}
    assert v.validate([{"semantic_id":"SINGLE_BED","room":"r","footprint":[.2,.2,1.1,2.2]}],rooms)["status"]=="PASS"
    assert v.validate([{"semantic_id":"SINGLE_BED","room":"r","footprint":[2.5,.2,3.4,2.2]}],rooms)["findings"][0]["code"]=="FURNITURE_OUTSIDE_ROOM"
    assert v.validate([{"semantic_id":"SOFA_3","room":"r","footprint":[.2,.2,2.3,1.1]}],rooms,door_zones=[[0,0,1,1]])["findings"][0]["code"]=="DOOR_SWING_FURNITURE_CONFLICT"
    assert v.validate([{"semantic_id":"WARDROBE","room":"r","footprint":[.2,.2,2,.8],"wall_aligned":True}],rooms,window_zones=[[0,0,3,.3]])["findings"][0]["code"]=="WINDOW_FURNITURE_CONFLICT"
    assert v.validate([{"semantic_id":"DINING_TABLE_6","room":"r","footprint":[.2,.2,2,1.1]}],rooms,routes=[[1,0,1.3,3]])["findings"][0]["code"]=="FURNITURE_BLOCKS_ROUTE"
def test_scene_site_label_joint_and_same_scene_contract():
    e=ArchitecturalDesignReasoningEngine()
    for st in states():
        sc=ArchitecturalPlanRealizer().realize(e.to_candidate_contract(st))
        assert sc.metadata["entry_site_graphics"]["status"]=="PASS" and sc.metadata["entry_site_graphics"]["canopy_depth_m"]==1.2
        assert sc.metadata["separation_joint_audit"]["source"]=="actual building exterior footprint"
        assert sc.metadata["label_layout_audit"]["critical_geometry_hidden"] is False
        assert sc.sheet["orientation"]=="LANDSCAPE" and sc.metadata["room_function_legibility"]["status"]=="PASS"
    assert "SvgArchitecturalRenderer" not in PdfArchitecturalRenderer.__dict__ and PdfArchitecturalRenderer is not SvgArchitecturalRenderer
