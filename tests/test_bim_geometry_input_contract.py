"""
ArchitectOS BIM Geometry Input Contract Test

Validates:

Design Geometry Input
        |
        v
FullBIMPipeline

and preserves fallback behavior.
"""


from core.bim.full_bim_pipeline import (
    FullBIMPipeline
)



def test_bim_geometry_input_contract():


    print(
        "\n🏗️ BIM GEOMETRY INPUT CONTRACT TEST START"
    )


    pipeline = FullBIMPipeline()



    # ======================================
    # TEST 1
    # EXTERNAL DESIGN GEOMETRY
    # ======================================

    geometry_input = {

        "rooms":[

            {

                "id":
                "Living",

                "type":
                "space",

                "geometry":

                {

                    "x":0,

                    "y":0,

                    "width":5,

                    "height":5

                }

            }

        ],

        "floors":[

            "F1"

        ]

    }



    result = pipeline.run(

        {

            "geometry":
            geometry_input

        }

    )



    assert result is not None


    assert (
        result.get("status")
        ==
        "completed"
    )


    print(
        "✅ External geometry accepted"
    )



    # ======================================
    # TEST 2
    # FALLBACK
    # ======================================

    fallback_result = pipeline.run(
        {}
    )


    assert fallback_result is not None


    assert (
        fallback_result.get("status")
        ==
        "completed"
    )


    print(
        "✅ Fallback behavior preserved"
    )



    print(
        "\n🎯 BIM GEOMETRY INPUT CONTRACT PASSED"
    )