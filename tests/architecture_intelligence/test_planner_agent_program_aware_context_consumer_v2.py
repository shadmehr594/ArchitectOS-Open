from core.architecture_intelligence.planner_agent_program_aware_context_consumer_v2 import (
    PlannerAgentProgramAwareContextConsumerV2
)



def test_planner_agent_program_aware_context_consumer_v2():


    print(
        "\n====== PLANNER AGENT PROGRAM AWARE CONTEXT CONSUMER V2 ======"
    )



    consumer = (
        PlannerAgentProgramAwareContextConsumerV2()
    )



    context = {


        "planner_context":

        {


            "building_type":

                "existing_building",


            "planning_goal":

                "adaptive_reuse_transformation",


            "architectural_strategy":

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



    result = consumer.consume(

        context

    )



    print(
        "\n====== PLANNER INPUT RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "PLANNER_AGENT_PROGRAM_AWARE_CONTEXT_CONSUMER_V2"
    )


    assert (
        result["planner_ready"]
        ==
        True
    )


    assert (
        result["planner_input"]["target_program"]
        ==
        "gym"
    )


    assert (
        result["planner_input"]["task"]
        ==
        "adaptive_reuse_design_planning"
    )


    assert (
        result["planner_input"]["program_category"]
        ==
        "commercial"
    )


    assert (
        "open_space"
        in
        result["planner_input"]["requirements"]
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_planner_agent_program_aware_context_consumer_v2()