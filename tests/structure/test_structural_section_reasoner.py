from core.structure.structural_section_reasoner import (
    StructuralSectionReasoner
)


def test_structural_section_reasoner():

    engine = StructuralSectionReasoner()


    column = engine.solve(

        member_type="column",

        level_height=5.0,

        building_type="commercial",

        floor_count=4

    )


    beam_short = engine.solve(

        member_type="beam",

        span=4.0,

        building_type="residential"

    )


    beam_long = engine.solve(

        member_type="beam",

        span=7.5,

        building_type="commercial"

    )


    assert column[
        "member_type"
    ] == "column"


    assert column[
        "width"
    ] > 0


    assert column[
        "depth"
    ] > 0


    assert column[
        "reference"
    ] == "corner"


    assert beam_short[
        "member_type"
    ] == "beam"


    assert beam_long[
        "depth"
    ] >= beam_short[
        "depth"
    ]


    assert beam_long[
        "span"
    ] == 7.5


    assert beam_long[
        "reason"
    ] == "context_driven_beam_section"


    print(
        "STRUCTURAL SECTION REASONER TEST PASSED"
    )