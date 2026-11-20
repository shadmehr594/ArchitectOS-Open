from core.structure.structural_element_engine import StructuralElementEngine
from core.structure.architecture_structure_handoff_v1 import (
    ArchitectureStructureContractError,
)


def test_structural_elements_consume_architectural_level_bounds_directly():
    grid = {
        "columns": [
            {
                "id": "C1",
                "x": 0.0,
                "y": 0.0,
                "width": 0.4,
                "depth": 0.4,
            }
        ],
        "beams": [
            {
                "id": "B1",
                "start": [0.0, 0.0],
                "end": [4.0, 0.0],
                "width": 0.3,
                "depth": 0.65,
            }
        ],
    }
    # Height is deliberately inconsistent with top-bottom. Structural Z
    # must preserve all architectural evidence and must not reconstruct top.
    level_config = {
        "F1": {
            "bottom": -2.75,
            "top": 8.125,
            "height": 99.0,
        }
    }
    engine = StructuralElementEngine(grid, level_config)

    columns = engine._generate_columns("F1")
    beams = engine._generate_beams({}, "F1")
    walls = engine._generate_walls(
        {
            "room": {
                "x": 0.0,
                "y": 0.0,
                "w": 4.0,
                "h": 3.0,
            }
        },
        "F1",
    )

    assert columns[0]["base_z"] == -2.75
    assert columns[0]["top_z"] == 8.125
    assert columns[0]["height"] == 99.0

    assert beams[0]["top_z"] == 8.125
    assert beams[0]["z"] == 7.475
    assert beams[0]["elevation"] == 7.475

    structural_wall = next(
        wall
        for wall in walls
        if wall.get("id") == "W-room"
    )
    assert structural_wall["z"] == -2.75
    assert structural_wall["top_z"] == 8.125
    assert structural_wall["height"] == 99.0


def test_missing_level_z_stays_unresolved_without_defaults():
    engine = StructuralElementEngine(
        {
            "columns": [
                {
                    "id": "C1",
                    "x": 0.0,
                    "y": 0.0,
                    "width": 0.4,
                    "depth": 0.4,
                }
            ],
            "beams": [],
        },
        {"F1": {}},
    )

    columns = engine._generate_columns("F1")

    assert columns[0]["base_z"] is None
    assert columns[0]["top_z"] is None
    assert columns[0]["height"] is None


def test_ready_architecture_handoff_overrides_legacy_level_z_in_production_grid():
    architectural_level = {
        "name": "F1",
        "bottom": -4.25,
        "top": 6.75,
        "height": 11.0,
    }
    grid = {
        "architecture_handoff": {
            "status": "ready",
            "levels_by_name": {
                "F1": architectural_level,
            },
        },
        "columns": [
            {
                "id": "C1",
                "x": 0.0,
                "y": 0.0,
                "width": 0.4,
                "depth": 0.4,
            }
        ],
        "beams": [],
    }
    contradictory_legacy_config = {
        "F1": {
            "base_z": 100.0,
            "top_z": 200.0,
            "column_height": 100.0,
        }
    }

    engine = StructuralElementEngine(
        grid,
        contradictory_legacy_config,
    )
    columns = engine._generate_columns("F1")

    assert engine.level_config_source == (
        "architecture_handoff_levels_by_name"
    )
    assert columns[0]["base_z"] == -4.25
    assert columns[0]["top_z"] == 6.75
    assert columns[0]["height"] == 11.0

    # Neither source contract is mutated by normalization or generation.
    assert architectural_level == {
        "name": "F1",
        "bottom": -4.25,
        "top": 6.75,
        "height": 11.0,
    }
    assert contradictory_legacy_config["F1"]["base_z"] == 100.0


def test_rejected_handoff_cannot_fall_back_to_legacy_level_config():
    rejected_grid = {
        "architecture_handoff": {
            "status": "rejected",
            "architecture_first": True,
            "errors": ["architectural_span_mismatch:spaces:F1:top"],
            "levels_by_name": {},
        },
        "columns": [],
        "beams": [],
    }

    try:
        StructuralElementEngine(
            rejected_grid,
            {"F1": {"base_z": 0.0, "top_z": 3.0}},
        )
    except ArchitectureStructureContractError as error:
        message = str(error)
    else:
        raise AssertionError("Rejected handoff fell back to legacy Z")

    assert "structural_elements" in message
    assert "architectural_span_mismatch:spaces:F1:top" in message
