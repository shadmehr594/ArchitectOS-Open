from copy import deepcopy

from core.structure.architecture_structure_handoff_v1 import (
    ArchitectureStructureContractError,
    ArchitectureStructureHandoffV1,
)
from core.structure.structural_grid_engine import StructuralGridEngine
from core.structure.structural_element_engine import StructuralElementEngine


def _architecture_sources():
    levels = [
        {"name": "F1", "bottom": -1.5, "top": 2.25, "height": 3.75},
        {"name": "F2", "bottom": 2.25, "top": 7.0, "height": 4.75},
    ]
    geometry = {
        "spaces": [
            {"floor": "F1", "bottom": -1.5, "top": 2.25, "height": 3.75},
            {"floor": "F2", "bottom": 2.25, "top": 7.0, "height": 4.75},
        ],
        "boundaries": [],
        "boundary_segments": [],
        "physical_walls": [],
        "floor_geometry": [
            {"floor": "F1", "bottom": -1.5, "top": 2.25, "height": 3.75},
            {"floor": "F2", "bottom": 2.25, "top": 7.0, "height": 4.75},
        ],
        "slabs": [
            {"floor": "F1", "bottom": -1.5, "top": 2.25},
            {"floor": "F2", "bottom": 2.25, "top": 7.0},
        ],
    }
    model = {
        "architecture_first": True,
        "architectural_geometry": geometry,
        "coordinate_frame": {"source": "architecture"},
        "parcel_placement": {"translation_applied": False},
    }
    return model, {"levels": levels, "roof_level": 7.0}


def test_architecture_structure_handoff_is_validated_and_read_only():
    model, vertical_section = _architecture_sources()
    original_model = deepcopy(model)
    original_section = deepcopy(vertical_section)

    handoff = ArchitectureStructureHandoffV1().create(
        model,
        vertical_section,
    )

    assert handoff["status"] == "ready"
    assert handoff["errors"] == []
    assert handoff["ownership"] == (
        "architecture_authoritative_structure_read_only"
    )
    assert model == original_model
    assert vertical_section == original_section

    handoff["levels"][0]["bottom"] = 999.0
    handoff["architectural_geometry"]["spaces"][0]["bottom"] = 999.0
    assert model == original_model
    assert vertical_section == original_section


def test_architecture_structure_handoff_rejects_z_mismatch_without_fixing_it():
    model, vertical_section = _architecture_sources()
    model["architectural_geometry"]["spaces"][0]["top"] = 999.0
    original_model = deepcopy(model)

    handoff = ArchitectureStructureHandoffV1().create(
        model,
        vertical_section,
    )

    assert handoff["status"] == "rejected"
    assert "architectural_span_mismatch:spaces:F1:top" in handoff["errors"]
    assert handoff["architectural_geometry"]["spaces"][0]["top"] == 999.0
    assert model == original_model


def test_structural_grid_consumes_handoff_without_mutating_architecture():
    model, vertical_section = _architecture_sources()
    model["building"] = {"width": 4.0, "depth": 3.0}
    model["architectural_spaces"] = []
    original_model = deepcopy(model)
    original_section = deepcopy(vertical_section)

    result = StructuralGridEngine().build(
        model,
        vertical_section,
    )

    assert result["architecture_handoff"]["status"] == "ready"
    assert result["architecture_handoff"]["errors"] == []
    assert result["levels"] == vertical_section["levels"]
    assert model == original_model
    assert vertical_section == original_section

    element_engine = StructuralElementEngine(
        result,
        {
            "F1": {
                "base_z": 100.0,
                "top_z": 200.0,
                "column_height": 100.0,
            }
        },
    )
    columns = element_engine._generate_columns("F1")

    assert columns
    assert element_engine.level_config_source == (
        "architecture_handoff_levels_by_name"
    )
    assert all(column["base_z"] == -1.5 for column in columns)
    assert all(column["top_z"] == 2.25 for column in columns)
    assert all(column["height"] == 3.75 for column in columns)


def test_structural_grid_fails_closed_on_rejected_architecture_handoff():
    model, vertical_section = _architecture_sources()
    model["building"] = {"width": 4.0, "depth": 3.0}
    model["architectural_spaces"] = []
    model["architectural_geometry"]["spaces"][0]["top"] = 999.0

    try:
        StructuralGridEngine().build(model, vertical_section)
    except ArchitectureStructureContractError as error:
        message = str(error)
    else:
        raise AssertionError("Rejected architecture handoff generated a grid")

    assert "structural_grid" in message
    assert "architectural_span_mismatch:spaces:F1:top" in message
