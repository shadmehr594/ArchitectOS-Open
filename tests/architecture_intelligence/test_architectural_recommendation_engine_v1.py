from core.bim.architectural_recommendation_engine_v1 import (
    ArchitecturalRecommendationEngineV1
)



def test_architectural_recommendation_engine_v1():


    print(
        "\n====== ARCHITECTURAL RECOMMENDATION ENGINE V1 ======"
    )


    engine = ArchitecturalRecommendationEngineV1()



    decision_context = {


        "engine":
            "ARCHITECTURAL_DECISION_ENGINE_V1",


        "decisions":
            [

                "existing_multistory_building",

                "architectural_shell_detected",

                "opening_pattern_available"

            ],


        "source_context":
            {

                "building_analysis":
                    {

                        "floors": 3,

                        "walls": 38,

                        "doors": 17,

                        "windows": 20,

                        "openings": 37

                    }

            }

    }



    result = engine.generate(
        decision_context
    )



    print(
        "\n====== RECOMMENDATION RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "ARCHITECTURAL_RECOMMENDATION_ENGINE_V1"
    )


    assert (
        len(
            result["recommendations"]
        )
        ==
        3
    )


    assert (
        "preserve_existing_architectural_shell"
        in
        result["recommendations"]
    )


    assert (
        "evaluate_existing_space_modification"
        in
        result["recommendations"]
    )


    assert (
        "analyze_opening_optimization_options"
        in
        result["recommendations"]
    )


    assert (
        result["planner_ready"]
        ==
        True
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_recommendation_engine_v1()