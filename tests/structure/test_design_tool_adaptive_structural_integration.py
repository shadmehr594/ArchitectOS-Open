from core.tools.design_tool import DesignTool


def test_design_tool_uses_adaptive_structural_grid():

    tool = DesignTool()

    spatial_output = {
        "F1": {
            "width": 12,
            "height": 10,
            "nodes": {
                "F1-Living": {
                    "x": 0,
                    "y": 0,
                    "w": 6,
                    "h": 5
                },
                "F1-Circulation": {
                    "x": 6,
                    "y": 0,
                    "w": 2,
                    "h": 10
                },
                "F1-Bedroom-1": {
                    "x": 8,
                    "y": 0,
                    "w": 4,
                    "h": 5
                }
            }
        }
    }

    floors = [
        {
            "name": "F1",
            "type": "single_unit"
        }
    ]

    result = tool.build_structural_grid(
        spatial_output,
        floors,
        12,
        10
    )

    assert result["grid_type"] == "adaptive"

    assert isinstance(
        result["columns"],
        list
    )

    assert isinstance(
        result["beams"],
        list
    )

    assert result[
        "origin"
    ] == "architectural_corner_origin"

    assert all(
        column.get(
            "reference"
        ) == "corner"
        for column in result[
            "columns"
        ]
    )

    protected_types = {
        zone.get(
            "type"
        )
        for zone in result.get(
            "protected_zones",
            []
        )
    }

    assert "corridor" in protected_types