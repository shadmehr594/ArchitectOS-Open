from core.intelligence.vertical_circulation_reasoning import (
    VerticalCirculationReasoning
)



def test_vertical_circulation_reasoning():


    engine = VerticalCirculationReasoning()



    result = engine.analyze(

        {

            "function":
                "commercial",

            "floors":
            [
                "G",
                "L1"
            ],

            "public_flow":
                True

        }

    )


    print(result)



    systems = [

        item["type"]

        for item in result["vertical_systems"]

    ]


    assert "escalator" in systems

    assert "elevator" in systems



    parking_result = engine.analyze(

        {

            "function":
                "parking",

            "floors":
            [
                "B1",
                "B2"
            ],

            "parking":
                True,

            "limited_space":
                True

        }

    )


    print(parking_result)



    assert (

        "car_lift"

        in

        [

            item["type"]

            for item in parking_result["vertical_systems"]

        ]

    )


    print(
        "✅ VERTICAL CIRCULATION REASONING TEST PASSED"
    )


def test_confirmed_multilevel_mixed_use_chain_infers_elevator_without_hint():
    floors = ["basement", "ground", "residential_floor_1", "residential_floor_2", "roof"]
    context = {"building_type": "mixed_use", "floors": floors, "requirements": []}
    result = VerticalCirculationReasoning().analyze(context)
    elevators = [item for item in result["vertical_systems"] if item["type"] == "elevator"]
    assert len(elevators) == 1
    assert "elevator" not in result["decision_context"]["requirements"]
    assert result["decision_context"]["multi_level"] is True
    assert result["decision_context"]["commercial"] is True



if __name__ == "__main__":

    test_vertical_circulation_reasoning()
