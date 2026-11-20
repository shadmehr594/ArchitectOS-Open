from core.spatial.spatial_layout_intelligence_bridge import (
    SpatialLayoutIntelligenceBridge
)



def test_layout_constraints():


    engine = SpatialLayoutIntelligenceBridge()



    decision = {


        "strategy":

            "courtyard_centered",


        "spaces":

        [

            {

                "id":
                    "courtyard_001",

                "type":
                    "courtyard",

                "layout_role":
                    "central_open_space"

            },


            {

                "id":
                    "office_001",

                "type":
                    "office",

                "layout_role":
                    "courtyard_adjacent"

            }

        ]

    }



    result = engine.generate_constraints(
        decision
    )


    print(
        result
    )


    assert (
        result["strategy"]
        ==
        "courtyard_centered"
    )


    assert (
        result["constraints"][0]["type"]
        ==
        "center"
    )


    assert (
        result["constraints"][1]["type"]
        ==
        "adjacent"
    )