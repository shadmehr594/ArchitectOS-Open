# ==========================================================
# TEST ARCHITECTURAL DECISION ENGINE V1
# ==========================================================


from core.bim.architectural_decision_engine_v1 import (
    ArchitecturalDecisionEngineV1
)



def test_architectural_decision_engine_v1():


    print(
        "\n====== ARCHITECTURAL DECISION ENGINE V1 ======"
    )


    context = {


        "building_analysis": {

            "floors": 3,

            "walls": 38,

            "doors": 17,

            "windows": 20,

            "openings": 37

        }

    }



    engine = ArchitecturalDecisionEngineV1()



    result = engine.decide(
        context
    )



    print(
        "\n====== DECISION RESULT ======"
    )


    print(
        result
    )



    assert (
        result["planner_ready"]
        ==
        True
    )


    assert (
        "existing_multistory_building"
        in
        result["decisions"]
    )


    assert (
        "architectural_shell_detected"
        in
        result["decisions"]
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_decision_engine_v1()