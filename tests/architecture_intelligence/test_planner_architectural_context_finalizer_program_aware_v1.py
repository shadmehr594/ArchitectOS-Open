from core.architecture_intelligence.planner_architectural_context_finalizer_program_aware_v1 import (
    PlannerArchitecturalContextFinalizerProgramAwareV1
)



def test_planner_architectural_context_finalizer_program_aware_v1():


    print(
        "\n====== PLANNER ARCHITECTURAL CONTEXT FINALIZER PROGRAM AWARE V1 ======"
    )



    finalizer = (
        PlannerArchitecturalContextFinalizerProgramAwareV1()
    )



    intent_context = {


        "intent":

        {


            "intent_type":

                "existing_building_program_transformation",


            "architectural_goal":

                "preserve_and_adapt_existing_shell",


            "architectural_action":

                "adaptive_reuse",


            "target_program":

                "gym",


            "program_category":
                "commercial",


            "requirements":
                [
                    "open_space",
                    "equipment_area",
                    "changing_room"
                ],


            "confidence":

                0.95

        }

    }



    result = finalizer.finalize(

        intent_context

    )



    print(
        "\n====== FINAL PLANNER CONTEXT RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "PLANNER_ARCHITECTURAL_CONTEXT_FINALIZER_PROGRAM_AWARE_V1"
    )


    assert (
        result["ready"]
        ==
        True
    )


    assert (
        result["planner_context"]["target_program"]
        ==
        "gym"
    )


    assert (
        result["planner_context"]["program_transformation"]
        ==
        True
    )


    assert (
        result["planner_context"]["program_category"]
        ==
        "commercial"
    )


    assert (
        "open_space"
        in
        result["planner_context"]["requirements"]
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_planner_architectural_context_finalizer_program_aware_v1()