from core.structure.structural_grid_engine import (
    StructuralGridEngine
)


def test_adaptive_beam_grid_integration():

    engine = StructuralGridEngine()


    architectural_model = {

        "building": {
            "width": 12,
            "depth": 12
        },

        "spaces": [

            {
                "name": "Living",
                "type": "room",
                "bounds": [0, 0, 6, 6]
            },

            {
                "name": "Dining",
                "type": "room",
                "bounds": [6, 0, 6, 6]
            },

            {
                "name": "Stair",
                "type": "stairs",
                "bounds": [5, 5, 2, 2]
            },

            {
                "name": "Bedroom",
                "type": "room",
                "bounds": [0, 6, 12, 6]
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


    columns = result[
        "columns"
    ]

    beams = result[
        "beams"
    ]


    assert len(
        columns
    ) > 0


    assert len(
        beams
    ) > 0


    column_ids = {

        column.get(
            "id"
        )

        for column in columns

        if column.get(
            "id"
        ) is not None

    }


    for beam in beams:

        assert beam[
            "start_column"
        ] in column_ids

        assert beam[
            "end_column"
        ] in column_ids


    assert all(

        beam.get(
            "reference"
        ) == "corner"

        for beam in beams

    )


    stair_bounds = [
        5,
        5,
        2,
        2
    ]


    def point_inside_stair(
        point
    ):

        x, y = point

        sx, sy, sw, sh = stair_bounds

        return (

            sx < x < sx + sw

            and

            sy < y < sy + sh

        )


    assert not any(

        point_inside_stair(
            beam["start"]
        )

        or

        point_inside_stair(
            beam["end"]
        )

        for beam in beams

    )


    assert all(

        beam[
            "length"
        ] > 0

        for beam in beams

    )


    print(
        "ADAPTIVE BEAM GRID INTEGRATION PASSED"
    )