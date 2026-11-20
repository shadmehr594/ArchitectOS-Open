from core.structure.structural_grid_engine import (
    StructuralGridEngine
)


def test_structural_section_grid_integration():

    engine = StructuralGridEngine()


    architectural_model = {

        "building": {
            "width": 15,
            "depth": 10
        },

        "spaces": [

            {
                "name": "Living",
                "type": "room",
                "bounds": [0, 0, 7.5, 5]
            },

            {
                "name": "Dining",
                "type": "room",
                "bounds": [7.5, 0, 7.5, 5]
            },

            {
                "name": "Bedroom",
                "type": "room",
                "bounds": [0, 5, 15, 5]
            }

        ]

    }


    vertical_section = {

        "levels": [

            {
                "name": "F1",
                "height": 3.2
            },

            {
                "name": "F2",
                "height": 3.2
            },

            {
                "name": "F3",
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


    for column in columns:

        assert column.get(
            "width"
        ) is not None

        assert column.get(
            "depth"
        ) is not None

        assert column.get(
            "width"
        ) > 0

        assert column.get(
            "depth"
        ) > 0

        assert column.get(
            "section_reason"
        ) == "context_driven_column_section"

        assert column.get(
            "reference"
        ) == "corner"


    for beam in beams:

        assert beam.get(
            "width"
        ) is not None

        assert beam.get(
            "depth"
        ) is not None

        assert beam.get(
            "width"
        ) > 0

        assert beam.get(
            "depth"
        ) > 0

        assert beam.get(
            "section_reason"
        ) == "context_driven_beam_section"

        assert beam.get(
            "reference"
        ) == "corner"


    beam_sections = [

        (
            beam.get(
                "length"
            ),
            beam.get(
                "depth"
            )
        )

        for beam in beams

        if beam.get(
            "length"
        ) is not None

    ]


    if len(
        beam_sections
    ) >= 2:

        beam_sections = sorted(
            beam_sections,
            key=lambda item: item[0]
        )


        shortest_span = beam_sections[0]

        longest_span = beam_sections[-1]


        assert longest_span[
            1
        ] >= shortest_span[
            1
        ]


    print(
        "STRUCTURAL SECTION GRID INTEGRATION PASSED"
    )