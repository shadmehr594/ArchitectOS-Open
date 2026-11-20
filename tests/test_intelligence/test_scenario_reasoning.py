from core.intelligence.architectural_scenario_reasoning_engine import (
    ArchitecturalScenarioReasoningEngine
)



def test_scenario_reasoning():


    engine = ArchitecturalScenarioReasoningEngine()



    parking = engine.analyze(

        {
            "type":
                "parking"
        }

    )


    duplex = engine.analyze(

        {
            "type":
                "duplex"
        }

    )


    penthouse = engine.analyze(

        {
            "type":
                "penthouse"
        }

    )



    print(
        parking
    )

    print(
        duplex
    )

    print(
        penthouse
    )



    assert "car_lift" in parking["requirements"]

    assert "internal_stair" in duplex["requirements"]

    assert "private_terrace" in penthouse["requirements"]



    print(
        "✅ SCENARIO REASONING TEST PASSED"
    )



if __name__ == "__main__":

    test_scenario_reasoning()