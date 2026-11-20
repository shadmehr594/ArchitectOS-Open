from core.brain_planner_context_bridge_v1 import (
    BrainPlannerContextBridgeV1
)



def test_brain_planner_context_bridge_v1():


    print(
        "\n====== BRAIN PLANNER CONTEXT BRIDGE V1 ======"
    )



    bridge = (
        BrainPlannerContextBridgeV1()
    )



    planner_context = {


        "planner_context":

        {

            "building_type":
                "existing_building",


            "intent":
                "existing_building_preservation",


            "goal":
                "preserve_existing_shell",


            "target":
                "architectural_shell",


            "confidence":
                0.95

        }

    }



    result = bridge.bridge(
        planner_context
    )



    print(
        "\n====== BRAIN CONTEXT RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "BRAIN_PLANNER_CONTEXT_BRIDGE_V1"
    )


    assert (
        result["ready"]
        ==
        True
    )


    assert (
        result["brain_context"]["building_type"]
        ==
        "existing_building"
    )


    assert (
        result["brain_context"]["architectural_intent"]
        ==
        "existing_building_preservation"
    )


    assert (
        result["brain_context"]["confidence"]
        ==
        0.95
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_brain_planner_context_bridge_v1()