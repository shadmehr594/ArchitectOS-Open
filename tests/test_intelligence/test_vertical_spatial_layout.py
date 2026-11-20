from core.spatial.vertical_spatial_layout_engine import (
    VerticalSpatialLayoutEngine
)



def test_vertical_spatial_layout():


    engine = VerticalSpatialLayoutEngine()



    program = {


        "level":
            "G",


        "spaces":
            [

                {
                    "type":
                        "escalator_zone"
                },

                {
                    "type":
                        "moving_ramp_zone"
                },

                {
                    "type":
                        "elevator_core"
                },

                {
                    "type":
                        "stair_core"
                }

            ]

    }



    result = engine.generate(

        program

    )


    print(

        "\n===== VERTICAL SPATIAL LAYOUT ====="

    )


    print(result)



    assert len(

        result["vertical_layout"]

    ) == 4



    print(

        "\n✅ VERTICAL SPATIAL LAYOUT TEST PASSED"

    )



if __name__=="__main__":

    test_vertical_spatial_layout()