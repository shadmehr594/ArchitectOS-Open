from core.architecture.geometry.architectural_geometry_engine_v2 import ArchitecturalGeometryEngineV2
from core.architecture.geometry.architectural_geometry_intent_generator_v1 import ArchitecturalGeometryIntentGeneratorV1
from core.bim.bim_geometry_contract_normalizer import BIMGeometryContractNormalizer
from core.bim.design_geometry_adapter import DesignGeometryAdapter
from core.geometry.geometry_adapter import GeometryAdapter
from core.integration.design_bim_bridge import DesignBIMBridge
import os


def _authoritative_contract():
    placement = {
        "floors": {
            "ground": {
                "spaces": [{"name": "shop", "x": 0, "y": 0, "width": 8, "depth": 10}],
            },
            "mezzanine": {
                "spaces": [{"name": "office", "x": 0, "y": 0, "width": 8, "depth": 5}],
            },
            "upper": {
                "spaces": [{"name": "living", "x": 0, "y": 0, "width": 8, "depth": 7}],
            },
        },
        "vertical_core": [
            {"name": "stairs", "type": "stairs", "connects": ["ground", "mezzanine", "upper"], "continuous": True},
            {"name": "elevator", "type": "elevator", "connects": ["ground", "upper"], "continuous": True},
        ],
    }
    vertical_section = {
        "levels": [
            {"name": "ground", "bottom": 0.0, "top": 3.64, "height": 3.64},
            {"name": "mezzanine", "bottom": 0.60, "top": 2.69, "height": 2.09, "is_mezzanine": True},
            {"name": "upper", "bottom": 3.64, "top": 6.60, "height": 2.96},
        ],
        "roof_level": 6.60,
    }
    site = {"separation": {"east": {"neighbor": True, "joint": 0.30}}}
    intent = ArchitecturalGeometryIntentGeneratorV1().generate(
        placement, site_analysis=site, vertical_section=vertical_section
    )
    geometry = ArchitecturalGeometryEngineV2().generate(intent)
    geometry["vertical_section"] = vertical_section
    return intent, geometry, vertical_section


def test_authoritative_geometry_survives_adapters_bim_state_and_element_mapping():
    intent, source, vertical_section = _authoritative_contract()

    adapted = DesignGeometryAdapter().convert({"architectural_geometry": source})
    assert adapted["authoritative_passthrough"] is True
    assert adapted["geometry"]["physical_walls"] == source["physical_walls"]

    project = DesignBIMBridge().prepare_bim_project({
        "architectural_geometry": adapted["geometry"],
        "geometry_intent": intent,
        "vertical_section": vertical_section,
        "generate_structure": False,
    })
    geometry = project["geometry"]
    normalized = BIMGeometryContractNormalizer().normalize(geometry)

    for key in (
        "physical_walls", "openings", "slabs", "floor_geometry",
        "vertical_geometry", "roof_geometry", "site_geometry",
    ):
        assert normalized[key] == geometry[key]

    assert project["architectural_geometry"] is geometry
    assert project["vertical_section"] == vertical_section
    assert project["geometry_intent"] == intent
    assert project["generate_structure"] is False
    assert geometry["architectural_authority"] is True
    assert geometry["walls"]
    assert geometry["slabs"]
    assert geometry["stairs"]
    assert geometry["elevators"]
    assert geometry["roofs"]

    by_floor = {item["floor"]: item for item in geometry["slabs"]}
    assert (by_floor["mezzanine"]["bottom"], by_floor["mezzanine"]["top"]) == (0.60, 2.69)

    elements = GeometryAdapter().build({}, geometry)
    types = {item["ifc_type"] for item in elements}
    assert {"IfcWall", "IfcSlab", "IfcStair", "IfcTransportElement", "IfcRoof"} <= types
    wall_data = next(item["data"] for item in elements if item["ifc_type"] == "IfcWall")
    assert "wall_type" in wall_data
    assert "thickness" in wall_data


def test_authoritative_geometry_reaches_real_unique_exports():
    intent, source, vertical_section = _authoritative_contract()
    result = DesignBIMBridge().run_bim({
        "architectural_geometry": source,
        "geometry": source,
        "geometry_intent": intent,
        "vertical_section": vertical_section,
        "generate_structure": False,
        "run_id": "authoritative_acceptance",
        "export_session": "DEFAULT",
    })["bim_result"]

    exports = result["exports"]
    assert exports["status"] == "completed"
    assert "authoritative_acceptance_" in exports["run_id"]
    assert os.path.isdir(exports["output_dir"])
    assert result["geometry"]["architectural_authority"] is True
    assert result["geometry"]["physical_walls"] == source["physical_walls"]

    paths = {
        "ifc": exports["ifc"]["path"],
        "dxf": exports["cad"]["file"]["file"],
        "dwg": exports["dwg"]["file"],
    }
    assert all(os.path.isfile(path) for path in paths.values())
    assert os.path.commonpath(paths.values()) == exports["output_dir"]
