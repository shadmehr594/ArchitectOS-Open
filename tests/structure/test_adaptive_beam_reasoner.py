from core.structure.adaptive_beam_reasoner import (
    AdaptiveBeamReasoner
)


def test_adaptive_beam_reasoner():

    engine = AdaptiveBeamReasoner()


    columns = [

        {
            "id": "C1",
            "x": 0,
            "y": 0,
            "reference": "corner"
        },

        {
            "id": "C2",
            "x": 6,
            "y": 0,
            "reference": "corner"
        },

        {
            "id": "C3",
            "x": 0,
            "y": 6,
            "reference": "corner"
        },

        {
            "id": "C4",
            "x": 6,
            "y": 6,
            "reference": "corner"
        },

        {
            "id": "C5",
            "x": 9,
            "y": 9,
            "reference": "corner"
        }

    ]


    protected_zones = [

        {
            "type": "stairs",

            "bounds": [
                2.5,
                2.5,
                1,
                1
            ],

            "allow_beam": False
        }

    ]


    result = engine.generate(
        columns,
        protected_zones=protected_zones
    )


    beams = result[
        "beams"
    ]


    assert len(
        beams
    ) > 0


    assert len(
        beams
    ) <= len(
        columns
    ) - 1


    assert all(

        beam[
            "reference"
        ] == "corner"

        for beam in beams

    )


    assert all(

        beam[
            "length"
        ] > 0

        for beam in beams

    )


    assert not any(

        beam[
            "start"
        ] == [0.0, 0.0]

        and

        beam[
            "end"
        ] == [6.0, 6.0]

        for beam in beams

    )


    assert any(

        beam[
            "orientation"
        ] == "diagonal"

        for beam in beams

    )


    print(
        "ADAPTIVE BEAM REASONER TEST PASSED"
    )