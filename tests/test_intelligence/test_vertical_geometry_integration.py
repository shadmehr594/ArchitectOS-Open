from core.geometry.vertical_geometry_integration_engine import (
    VerticalGeometryIntegrationEngine
)



def test_vertical_geometry_integration():


    engine = VerticalGeometryIntegrationEngine()



    layout = {


        "level":
            "G",


        "vertical_layout":

            [

                {

                    "type":
                        "escalator_zone",

                    "polygon":
                        [
                            [5,5],
                            [11,5],
                            [11,6],
                            [5,6]
                        ],

                    "location":
                        "atrium"

                },


                {

                    "type":
                        "elevator_core",

                    "polygon":
                        [
                            [10,10],
                            [14,14]
                        ]

                },


                {

                    "type":
                        "stair_core",

                    "polygon":
                        [
                            [0,10],
                            [4,14]
                        ]

                }

            ]

    }



    result = engine.generate(

        layout

    )


    print(
        "\n===== VERTICAL GEOMETRY RESULT ====="
    )


    print(result)



    assert len(

        result["elements"]

    ) == 3



    print(
        "\n✅ VERTICAL GEOMETRY INTEGRATION TEST PASSED"
    )



if __name__=="__main__":

    test_vertical_geometry_integration()