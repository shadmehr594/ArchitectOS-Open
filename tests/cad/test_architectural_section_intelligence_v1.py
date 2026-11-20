import ezdxf
from core.architecture.geometry.architectural_section_intelligence_v1 import ArchitecturalSectionIntelligenceV1
from tests.architecture_generation.test_complete_architecture_vehicle_access_acceptance import _generate_and_export


def test_south_functional_section_contains_ramp_headroom_stair_and_voids():
    _,result,exports=_generate_and_export("south_road","south","vehicle_ramp",0.0,16.0,"architectural_section_south")
    section=result["architectural_geometry"]["architectural_section"]
    assert section["geometry_status"]=="resolved"
    assert section["ramp_profile"] and section["headroom_profile"] and section["stair_profile"]
    assert {o["type"] for o in section["slab_openings"]}>={"stairwell_slab_opening","vehicle_ramp_clearance_slab_opening"}
    doc=ezdxf.readfile(exports["exports"]["cad"]["file"]["file"])
    layers={e.dxf.layer for e in doc.modelspace()}
    assert {"ARCH_SECTION","SECTION_RAMP","SECTION_HEADROOM","SECTION_STAIR","SECTION_SLAB_OPENING"}<=layers


def test_north_section_has_stair_and_levels_without_fake_ramp():
    _,result,exports=_generate_and_export("north_road","north","direct_at_grade",-2.4,0.0,"architectural_section_north")
    section=result["architectural_geometry"]["architectural_section"]
    assert section["geometry_status"]=="resolved" and section["ramp_profile"] is None
    doc=ezdxf.readfile(exports["exports"]["cad"]["file"]["file"])
    assert len(doc.modelspace().query('*[layer=="SECTION_RAMP"]'))==0
