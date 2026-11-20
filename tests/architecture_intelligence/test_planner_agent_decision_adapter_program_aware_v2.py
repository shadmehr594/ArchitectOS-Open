from core.architecture_intelligence.planner_agent_decision_adapter_program_aware_v2 import (
    PlannerAgentDecisionAdapterProgramAwareV2
)



def test_planner_agent_decision_adapter_program_aware_v2():


    print(
        "\n====== PLANNER AGENT DECISION ADAPTER PROGRAM AWARE V2 ======"
    )



    adapter = (
        PlannerAgentDecisionAdapterProgramAwareV2()
    )



    planner_context = {


        "planner_input":

        {


            "task":

                "adaptive_reuse_design_planning",


            "building_type":

                "existing_building",


            "planning_goal":

                "adaptive_reuse_transformation",


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


            "architectural_strategy":

                "preserve_and_adapt_existing_shell",


            "architectural_action":

                "adaptive_reuse",


            "confidence":

                0.95

        }

    }



    result = adapter.adapt(

        planner_context

    )



    print(
        "\n====== DECISION RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "PLANNER_AGENT_DECISION_ADAPTER_PROGRAM_AWARE_V2"
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
        result["decision"]["next_stage"]
        ==
        "bim_modification_planning"
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

    test_planner_agent_decision_adapter_program_aware_v2()