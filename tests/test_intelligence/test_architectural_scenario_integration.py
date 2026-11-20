from core.intelligence.architectural_scenario_integration import (
    ArchitecturalScenarioIntegration
)



def test_architectural_scenario_integration():


    engine = ArchitecturalScenarioIntegration()



    program = {


        "level":
            "F3",


        "type":
            "duplex",


        "spaces":

        [

            {
                "type":
                    "unit_cluster"
            }

        ]

    }



    scenario = {


        "scenario":
            "duplex",


        "requirements":

        [

            "internal_stair",

            "double_height",

            "private_zone"

        ]

    }



    result = engine.apply(

        program,

        scenario

    )



    print(
        "\n========== SCENARIO INTEGRATION RESULT =========="
    )

    print(result)



    spaces = [

        x["type"]

        for x in result["spaces"]

    ]



    assert "internal_stair" in spaces

    assert "double_height_space" in spaces

    assert "private_zone" in spaces



    print(
        "✅ ARCHITECTURAL SCENARIO INTEGRATION TEST PASSED"
    )



if __name__ == "__main__":

    test_architectural_scenario_integration()