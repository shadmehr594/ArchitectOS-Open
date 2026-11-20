from core.structure.structural_grid_engine import (
    StructuralGridEngine
)


def test_irregular_structural_grid_integration():


    engine = StructuralGridEngine()


    architectural_model = {

        "building": {
            "width": 12,
            "depth": 10
        },

        "spaces": [

            {
                "name": "Living",
                "type": "room",
                "bounds": [0, 0, 6, 5]
            },

            {
                "name": "Dining",
                "type": "room",
                "bounds": [6, 0, 6, 5]
            },

            {
                "name": "Stair",
                "type": "stairs",
                "bounds": [5, 4, 2, 2]
            },

            {
                "name": "Bedroom",
                "type": "room",
                "bounds": [0, 5, 12, 5]
            }

        ]

    }


    vertical_section = {

        "levels": [

            {
                "name": "F1",
                "height": 3.2
            }

        ]

    }


    result = engine.build(
        architectural_model,
        vertical_section
    )


    grid = result[
        "grid"
    ]


    assert len(
        grid
    ) > 0


    assert not any(

        point["x"] == 6
        and
        point["y"] == 5

        for point in grid

    )


    assert all(

        point.get(
            "reference"
        ) == "corner"

        for point in grid

    )


    coordinates = {

        (
            round(
                point["x"],
                3
            ),
            round(
                point["y"],
                3
            )
        )

        for point in grid

    }


    assert len(
        coordinates
    ) == len(
        grid
    )


    print(
        "IRREGULAR STRUCTURAL GRID INTEGRATION PASSED"
    )