from core.intelligence.scenario_program_adapter import (
    ScenarioProgramAdapter
)



def test_scenario_program_adapter():


    engine = ScenarioProgramAdapter()



    parking_program = {


        "level":
            "B1",


        "type":
            "parking",


        "spaces":

        [

            {
                "type":
                    "parking_area"
            }

        ]

    }



    scenario = {


        "scenario":
            "parking",


        "requirements":

        [

            "car_lift",

            "ramp",

            "ventilation"

        ]

    }



    result = engine.apply(

        parking_program,

        scenario

    )



    print(
        "\n========== SCENARIO PROGRAM RESULT =========="
    )

    print(result)



    spaces = [

        x["type"]

        for x in result["spaces"]

    ]



    assert "car_lift_zone" in spaces

    assert "vehicle_ramp" in spaces

    assert "ventilation_room" in spaces



    print(
        "✅ SCENARIO PROGRAM ADAPTER TEST PASSED"
    )



if __name__ == "__main__":

    test_scenario_program_adapter()