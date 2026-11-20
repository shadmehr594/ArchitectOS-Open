from core.architecture_intelligence.architectural_decision_engine_program_aware_v1 import (
    ArchitecturalDecisionEngineProgramAwareV1
)



def test_architectural_decision_engine_program_aware_v1():


    print(
        "\n====== ARCHITECTURAL DECISION ENGINE PROGRAM AWARE V1 ======"
    )



    engine = (
        ArchitecturalDecisionEngineProgramAwareV1()
    )



    context = {


        "building_type":

            "existing_building",


        "target_program":

            "gym",


        "program_category":

            "commercial",


        "requirements":

        [

            "open_space",

            "equipment_area",

            "changing_room"

        ]

    }



    result = engine.decide(

        context

    )



    print(
        "\n====== PROGRAM DECISION RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "ARCHITECTURAL_DECISION_ENGINE_PROGRAM_AWARE_V1"
    )


    assert (
        result["decision_ready"]
        ==
        True
    )


    assert (
        result["decision"]["target_program"]
        ==
        "gym"
    )


    assert (
        "adapt_existing_layout"
        in
        result["decision"]["decisions"]
    )


    assert (
        "validate_gym_requirements"
        in
        result["decision"]["decisions"]
    )


    assert (
        result["decision"]["program_category"]
        ==
        "commercial"
    )


    assert (
        "open_space"
        in
        result["decision"]["requirements"]
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_decision_engine_program_aware_v1()