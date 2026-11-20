from core.structure.structural_element_engine import (
    StructuralElementEngine
)


def test_structural_element_engine_preserves_adaptive_contract():

    grid = {
        "grid_type": "adaptive",

        "columns": [
            {
                "id": "C-1",
                "x": 0.0,
                "y": 0.0,
                "width": 0.35,
                "depth": 0.40,
                "reference": "corner",
                "section_reason":
                    "context_driven_column_section"
            },
            {
                "id": "C-2",
                "x": 5.5,
                "y": 4.0,
                "width": 0.35,
                "depth": 0.40,
                "reference": "corner",
                "section_reason":
                    "context_driven_column_section"
            }
        ],

        "beams": [
            {
                "id": "B-1",
                "start": [0.0, 0.0],
                "end": [5.5, 4.0],
                "length": 6.8,
                "orientation": "diagonal",
                "width": 0.30,
                "depth": 0.55,
                "reference": "corner",
                "section_reason":
                    "context_driven_beam_section"
            }
        ]
    }

    level_config = {
        "F1": {
            "bottom": -1.25,
            "top": 4.75,
            "height": 6.0
        }
    }

    engine = StructuralElementEngine(
        grid,
        level_config
    )

    columns = engine._generate_columns(
        "F1"
    )

    beams = engine._generate_beams(
        {},
        "F1"
    )

    assert len(columns) == 2

    assert columns[0]["x"] == 0.0
    assert columns[0]["y"] == 0.0

    assert columns[0]["width"] == 0.35
    assert columns[0]["depth"] == 0.40

    assert columns[0]["reference"] == "corner"
    assert columns[0]["base_z"] == -1.25
    assert columns[0]["top_z"] == 4.75
    assert columns[0]["height"] == 6.0

    assert (
        columns[0]["section_reason"]
        ==
        "context_driven_column_section"
    )

    assert len(beams) == 1

    assert beams[0]["start"] == (
        0.0,
        0.0
    )

    assert beams[0]["end"] == (
        5.5,
        4.0
    )

    assert (
        beams[0]["orientation"]
        ==
        "diagonal"
    )

    assert beams[0]["width"] == 0.30
    assert beams[0]["depth"] == 0.55
    assert beams[0]["z"] == 4.20
    assert beams[0]["top_z"] == 4.75

    assert (
        beams[0]["height"]
        ==
        0.55
    )

    assert (
        beams[0]["section_reason"]
        ==
        "context_driven_beam_section"
    )
