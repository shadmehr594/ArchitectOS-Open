# ==================================================
# TEST ArchitectOS Architectural Design Action Executor V2
# Adaptive Reuse Program Aware Contract
# ==================================================


from core.intelligence.architectural_design_action_executor_v2 import (
    ArchitecturalDesignActionExecutorV2
)



def test_architectural_design_action_executor_v2():


    print(
        "\n====== ARCHITECTURAL DESIGN ACTION EXECUTOR V2 ======"
    )


    executor = ArchitecturalDesignActionExecutorV2()



    decision = {


        "type":

            "adaptive_reuse_architectural_plan",


        "action":

            "modify_existing_layout_for_program",


        "preserve":

            "existing_shell",


        "target_program":

            "gym",


        "next_stage":

            "bim_modification_planning",


        "confidence":

            0.95

    }



    actions = executor.execute(
        decision
    )



    print(
        "\n====== GENERATED ACTIONS ======"
    )


    print(
        actions
    )



    assert len(actions) == 3



    assert (
        actions[0]["module"]
        ==
        "adaptive_reuse"
    )


    assert (
        actions[0]["action"]
        ==
        "preserve_existing_shell"
    )


    assert (
        actions[1]["action"]
        ==
        "modify_existing_layout"
    )


    assert (
        actions[1]["parameters"]["target_program"]
        ==
        "gym"
    )


    assert (
        actions[2]["module"]
        ==
        "bim"
    )


    assert (
        actions[2]["action"]
        ==
        "create_modification_plan"
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_design_action_executor_v2()