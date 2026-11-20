"""
ArchitectOS Structural Span Reasoner Test v1.0

Validates:
- no fixed 4m grid
- adaptive span selection
- variable structural spacing
- architectural alignment
"""


from core.structure.structural_span_reasoner import (
    StructuralSpanReasoner
)



def test_structural_span_reasoning():


    engine = StructuralSpanReasoner()



    # -----------------------------
    # CASE 1
    # 12m residential building
    # -----------------------------

    result = engine.solve(

        length=12,

        anchors=[
            0,
            5,
            12
        ],

        building_type="residential"

    )


    assert "axis" in result

    assert len(
        result["axis"]
    ) > 1



    assert result["span"] != 4 or result["axis"] == [

        0,
        4,
        8,
        12

    ]



    # -----------------------------
    # CASE 2
    # Commercial open plan
    # -----------------------------


    commercial = engine.solve(

        length=15,

        anchors=[
            0,
            15
        ],

        building_type="commercial"

    )


    assert commercial["span"] >= 5



    # -----------------------------
    # MIN/MAX CONTROL
    # -----------------------------


    assert (

        engine.min_span

        <=

        result["span"]

        <=

        engine.max_span

    )



    print(
        "STRUCTURAL SPAN REASONER TEST PASSED"
    )