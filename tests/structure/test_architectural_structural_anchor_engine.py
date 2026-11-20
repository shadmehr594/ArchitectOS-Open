from core.structure.architectural_structural_anchor_engine import (
    ArchitecturalStructuralAnchorEngine
)



def test_architectural_structural_anchor_engine():


    engine = ArchitecturalStructuralAnchorEngine()



    model = {


        "building": {

            "width":12,

            "depth":16

        },


        "spaces":[


            {

                "name":"Living",

                "type":"room",

                "bounds":[

                    0,
                    0,
                    5,
                    6

                ]

            },


            {

                "name":"Stair",

                "type":"stairs",

                "bounds":[

                    5,
                    5,
                    3,
                    4

                ]

            }

        ]

    }



    result = engine.extract(
        model
    )



    assert 0 in result["x_anchors"]

    assert 12 in result["x_anchors"]


    assert len(
        result["core_zones"]
    ) == 1


    assert "avoid_structure" in [

        x["type"]

        for x in result["structural_hints"]

    ]


    print(
        "ARCHITECTURAL STRUCTURAL ANCHOR ENGINE TEST PASSED"
    )