from core.spatial.spatial_intent_model_v1 import (
    SpatialIntentModelV1
)



def test_spatial_intent_model_v1():


    print(
        "\n====== SPATIAL INTENT MODEL TEST ======"
    )


    space_program = {


        "spaces":

        [

            "living",
            "bedroom",
            "garden"

        ],


        "zones":

        {

            "public":

            [

                "living"

            ],


            "private":

            [

                "bedroom"

            ],


            "external":

            [

                "garden"

            ]

        },


        "relationships":

        [

            {

                "from":

                    "living",

                "to":

                    "garden",

                "type":

                    "visual_connection"

            }

        ]

    }



    engine = SpatialIntentModelV1()


    result = engine.build(
        space_program
    )



    print(
        result
    )



    assert result["ready"] is True


    assert (

        result["spaces"]["living"]["role"]

        ==

        "public_space"

    )


    assert (

        "garden"

        in

        result["spaces"]["living"]["connects"]

    )


    assert (

        result["spaces"]["bedroom"]["privacy"]

        ==

        "high"

    )


    print(
        "\n====== TEST PASSED ======"
    )