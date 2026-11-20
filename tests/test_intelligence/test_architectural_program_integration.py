from core.intelligence.architectural_program_integration import (
    ArchitecturalProgramIntegration
)



def test_architectural_program_integration():


    engine = ArchitecturalProgramIntegration()



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



    intelligence = {


        "program_requirements":

        [

            {

                "target":
                    "G",

                "additions":

                [

                    "street_frontage",

                    "mezzanine"

                ]

            }

        ],


        "vertical_systems":

        [

            {
                "type":
                    "escalator"
            },

            {
                "type":
                    "elevator"
            }

        ]

    }



    result = engine.integrate(

        program,

        intelligence

    )



    print(
        "\n========== PROGRAM RESULT =========="
    )

    print(result)



    spaces = [

        item["type"]

        for item in result["spaces"]

    ]



    assert "mezzanine" in spaces

    assert "street_frontage" in spaces

    assert "escalator_zone" in spaces

    assert "elevator_core" in spaces



    print(
        "✅ ARCHITECTURAL PROGRAM INTEGRATION TEST PASSED"
    )



if __name__ == "__main__":

    test_architectural_program_integration()