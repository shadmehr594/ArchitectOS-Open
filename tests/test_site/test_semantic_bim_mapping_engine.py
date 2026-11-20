"""
ArchitectOS Semantic BIM Mapping Engine Test v1.0
"""


from core.bim.semantic_bim_mapping_engine import (
    SemanticBIMMappingEngine
)



def test_semantic_bim_mapping_engine():


    engine = SemanticBIMMappingEngine()



    spaces = [

        {

            "type":
                "living",

            "zone":
                "public",

            "polygon":[

                [0,0],

                [4,0],

                [4,5],

                [0,5]

            ]

        }

    ]



    walls = [

        {

            "type":
                "interior",

            "edge":[

                [4,0],

                [4,5]

            ],

            "thickness":
                0.2

        }

    ]



    openings = [

        {

            "type":
                "door",

            "room":
                "living",

            "source":
                "entrance"

        },


        {

            "type":
                "window",

            "room":
                "living",

            "source":
                "facade"

        }

    ]



    result = engine.generate(

        spaces,

        walls,

        openings

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    elements = result.get(
        "elements",
        []
    )



    assert len(
        elements
    ) == 4



    ifc_types = [

        element.get(
            "ifc_type"
        )

        for element in elements

    ]



    assert "IfcSpace" in ifc_types

    assert "IfcWall" in ifc_types

    assert "IfcDoor" in ifc_types

    assert "IfcWindow" in ifc_types



    print(
        "\n✅ SEMANTIC BIM MAPPING ENGINE TEST PASSED"
    )



if __name__ == "__main__":

    test_semantic_bim_mapping_engine()