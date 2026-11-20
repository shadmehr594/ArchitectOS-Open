from copy import deepcopy

import ifcopenshell
from ifcopenshell.util.placement import get_local_placement

from core.export.ifc_export_engine import IFCExportEngine
from core.integration.design_bim_bridge import DesignBIMBridge
from core.structure.architecture_structure_handoff_v1 import (
    ArchitectureStructureContractError,
)


def _design_result_with_handoff(status="ready"):
    levels = [
        {"name": "F1", "bottom": -2.5, "top": 1.75, "height": 4.25},
        {"name": "F2", "bottom": 1.75, "top": 7.5, "height": 5.75},
    ]
    return {
        "type": "design",
        "site": {},
        "spatial": {},
        "geometry": {
            # Deliberately contradictory: ready handoff must win.
            "floor_geometry": [
                {"floor": "F1", "bottom": 100.0, "top": 103.0, "height": 3.0},
            ],
        },
        "structural_grid": {
            "architecture_handoff": {
                "status": status,
                "architecture_first": True,
                "errors": [] if status == "ready" else ["z_contract_invalid"],
                "levels": levels,
                "levels_by_name": {level["name"]: level for level in levels},
            },
        },
    }


def test_bridge_copies_vertical_section_bounds_without_recalculation():
    design_result = _design_result_with_handoff()
    original = deepcopy(design_result)

    project = DesignBIMBridge().prepare_bim_project(design_result)
    levels = project["level_config"]

    assert levels["F1"]["bottom"] == -2.5
    assert levels["F1"]["top"] == 1.75
    assert levels["F1"]["height"] == 4.25
    assert levels["F1"]["base_z"] == -2.5
    assert levels["F2"]["bottom"] == 1.75
    assert levels["F2"]["top"] == 7.5
    assert levels["F2"]["height"] == 5.75
    assert levels["F2"]["height_source"] == "vertical_section.levels"
    assert design_result == original


def test_ifc_storey_elevation_prefers_canonical_bottom():
    config = {
        "level_config": {
            "F1": {
                "bottom": -3.125,
                "base_z": 999.0,
                "top": 4.0,
                "height": 7.125,
            },
        },
        "levels": [
            {"name": "F1", "bottom": 50.0, "elevation": 60.0},
        ],
    }

    assert IFCExportEngine().resolve_storey_elevation("F1", config) == -3.125


def test_ifc_level_list_prefers_bottom_over_elevation_alias():
    config = {
        "levels": [
            {"name": "F2", "bottom": 2.75, "elevation": 200.0},
        ],
    }

    assert IFCExportEngine().resolve_storey_elevation("F2", config) == 2.75


def test_bridge_fails_closed_on_rejected_architecture_handoff():
    design_result = _design_result_with_handoff(status="rejected")

    try:
        DesignBIMBridge().prepare_bim_project(design_result)
    except ArchitectureStructureContractError as error:
        message = str(error)
    else:
        raise AssertionError("BIM bridge accepted a rejected architecture handoff")

    assert "design_bim_bridge" in message
    assert "z_contract_invalid" in message


def test_exported_ifc_storeys_preserve_architectural_bottoms(tmp_path):
    output_path = tmp_path / "architectural_z_contract.ifc"
    building_config = {
        "floors": 2,
        "architectural_authority": True,
        "level_config": {
            "F1": {
                "bottom": -1.625,
                "top": 2.875,
                "height": 4.5,
                "base_z": 999.0,
            },
            "F2": {
                "bottom": 2.875,
                "top": 8.125,
                "height": 5.25,
                "base_z": 1999.0,
            },
        },
        "levels": [
            {"name": "F1", "bottom": -1.625, "top": 2.875, "height": 4.5},
            {"name": "F2", "bottom": 2.875, "top": 8.125, "height": 5.25},
        ],
    }
    bim_model = {
        "levels": ["F1", "F2"],
        "building_config": building_config,
        "bim_elements": [],
    }

    result = IFCExportEngine().export(
        bim_model,
        output_path=str(output_path),
    )

    assert result["status"] == "exported"
    assert output_path.exists()

    model = ifcopenshell.open(str(output_path))
    elevations = {
        storey.Name: storey.Elevation
        for storey in model.by_type("IfcBuildingStorey")
    }
    assert elevations["Level F1"] == -1.625
    assert elevations["Level F2"] == 2.875


def test_ifc_products_apply_architectural_z_exactly_once(tmp_path):
    output_path = tmp_path / "element_placement_z_contract.ifc"
    level_bottom = 4.75
    beam_world_z = 8.4
    building_config = {
        "floors": 1,
        "architectural_authority": True,
        "level_config": {
            "F2": {"bottom": level_bottom, "top": 8.75, "height": 4.0},
        },
        "levels": [
            {"name": "F2", "bottom": level_bottom, "top": 8.75, "height": 4.0},
        ],
    }
    elements = [
        {
            "id": "placement-wall", "ifc_type": "IfcWall",
            "level": "F2", "z": level_bottom,
            "start": [0.0, 0.0], "end": [4.0, 0.0],
            "data": {
                "id": "placement-wall", "level": "F2", "z": level_bottom,
                "start": [0.0, 0.0], "end": [4.0, 0.0],
                "height": 4.0, "thickness": 0.2,
            },
        },
        {
            "id": "placement-column", "ifc_type": "IfcColumn",
            "data": {
                "id": "placement-column", "level": "F2", "z": level_bottom,
                "x": 1.0, "y": 1.0, "width": 0.4, "depth": 0.4,
                "height": 4.0,
            },
        },
        {
            "id": "placement-beam", "ifc_type": "IfcBeam",
            "data": {
                "id": "placement-beam", "level": "F2", "z": beam_world_z,
                "start": [0.0, 0.0], "end": [4.0, 0.0],
                "width": 0.3, "depth": 0.35, "height": 0.35,
            },
        },
        {
            "id": "placement-slab", "ifc_type": "IfcSlab",
            "data": {
                "id": "placement-slab", "level": "F2", "z": level_bottom,
                "x": 0.0, "y": 0.0, "width": 4.0, "depth": 4.0,
                "thickness": 0.2,
            },
        },
    ]

    IFCExportEngine().export(
        {
            "levels": ["F2"],
            "building_config": building_config,
            "bim_elements": elements,
        },
        output_path=str(output_path),
    )

    model = ifcopenshell.open(str(output_path))
    expected_world_z = {
        "placement-wall": level_bottom,
        "placement-column": level_bottom,
        "placement-beam": beam_world_z,
        "placement-slab": level_bottom,
    }
    for ifc_type in ("IfcWall", "IfcColumn", "IfcBeam", "IfcSlab"):
        product = next(
            item for item in model.by_type(ifc_type)
            if item.Name in expected_world_z
        )
        world_z = float(get_local_placement(product.ObjectPlacement)[2, 3])
        assert world_z == expected_world_z[product.Name]
