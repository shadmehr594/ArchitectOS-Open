from core.intelligence.vertical_program_integration_engine import (
    VerticalProgramIntegrationEngine
)



def test_vertical_program_integration():


    engine = VerticalProgramIntegrationEngine()



    program = {

        "level":
            "G",

        "type":
            "commercial",

        "spaces":
            [

                {
                    "type":
                        "shop"
                }

            ]

    }



    network = {


        "systems":

            [

                {
                    "type":
                        "escalator"
                },

                {
                    "type":
                        "moving_ramp"
                },

                {
                    "type":
                        "elevator"
                },

                {
                    "type":
                        "stair"
                }

            ]

    }



    result = engine.apply(

        program,

        network

    )


    print(
        "\n===== VERTICAL PROGRAM RESULT ====="
    )


    print(result)



    types = [

        x["type"]

        for x in result["spaces"]

    ]



    assert "escalator_zone" in types

    assert "moving_ramp_zone" in types

    assert "elevator_core" in types

    assert "stair_core" in types



    print(
        "\n✅ VERTICAL PROGRAM INTEGRATION TEST PASSED"
    )



if __name__=="__main__":

    test_vertical_program_integration()