import ezdxf

from core.architecture.vertical_building_section_engine import VerticalBuildingSectionEngine
from core.architecture.geometry.architectural_geometry_intent_generator_v1 import ArchitecturalGeometryIntentGeneratorV1
from core.export.dwg.dwg_writer import DWGWriter


def test_explicit_mezzanine_levels_are_preserved():
    section = VerticalBuildingSectionEngine().generate({"floors": [
        {"name": "ground", "type": "commercial", "bottom": 0.0, "top": 3.64, "height": 3.64},
        {"name": "mezzanine", "type": "mezzanine", "bottom": 0.60, "top": 2.69, "height": 2.09},
        {"name": "upper", "type": "residential", "bottom": 3.64, "top": 6.60, "height": 2.96},
    ]})
    by_name = {level["name"]: level for level in section["levels"]}
    assert (by_name["mezzanine"]["bottom"], by_name["mezzanine"]["top"]) == (0.60, 2.69)
    assert by_name["mezzanine"]["is_mezzanine"] is True
    assert section["roof_level"] == 6.60


def test_stair_flights_use_vertical_section_level_elevations():
    vertical = {"levels": [
        {"name": "ground", "bottom": 0.0, "top": 3.64, "height": 3.64},
        {"name": "mezzanine", "bottom": 0.60, "top": 2.69, "height": 2.09},
        {"name": "upper", "bottom": 3.64, "top": 6.60, "height": 2.96},
    ]}
    placement = {"vertical_core": [{"type": "stairs", "connects": ["ground", "mezzanine", "upper"], "parameters": {}}]}
    intent = ArchitecturalGeometryIntentGeneratorV1().generate(placement, vertical_section=vertical)
    flights = intent["vertical_elements"][0]["flights"]
    assert [(f["bottom"], f["top"]) for f in flights] == [(0.0, 0.60), (0.60, 3.64)]
    assert all(f["source"] == "vertical_section.levels" for f in flights)


def test_separation_joint_is_forwarded_and_drawn(tmp_path):
    site = {"building_strategy": {"parcel_boundary": [[0, 0], [10, 0], [10, 20], [0, 20]], "coordinate_system": "local_normalized"},
            "separation": {"east": {"neighbor": True, "joint": 0.30}, "west": {"neighbor": True, "joint": 0.20}}}
    intent = ArchitecturalGeometryIntentGeneratorV1().generate({}, site_analysis=site)
    assert intent["site_geometry_intent"]["separation_joints"]["east"]["joint"] == 0.30
    output = tmp_path / "joint.dxf"
    DWGWriter().export({"site_geometry": intent["site_geometry_intent"]}, {}, output=str(output))
    msp = ezdxf.readfile(output).modelspace()
    assert sum(1 for e in msp if e.dxf.layer == "SITE_SEPARATION_JOINT" and e.dxftype() == "LINE") == 2
