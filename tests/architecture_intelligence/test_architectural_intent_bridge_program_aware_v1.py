from core.architecture_intelligence.architectural_intent_bridge_program_aware_v1 import (
    ArchitecturalIntentBridgeProgramAwareV1
)



def test_architectural_intent_bridge_program_aware_v1():


    print(
        "\n====== ARCHITECTURAL INTENT BRIDGE PROGRAM AWARE V1 ======"
    )



    bridge = (
        ArchitecturalIntentBridgeProgramAwareV1()
    )



    decision_context = {


        "decision":

        {


            "proposal":

                "architectural_shell_preservation",


            "action":

                "retain_existing_structure",


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


            "score":

                95,


            "confidence":

                0.95

        }

    }



    result = bridge.build_intent(

        decision_context

    )



    print(
        "\n====== INTENT RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "ARCHITECTURAL_INTENT_BRIDGE_PROGRAM_AWARE_V1"
    )


    assert (
        result["intent_ready"]
        ==
        True
    )


    assert (
        result["intent"]["target_program"]
        ==
        "gym"
    )


    assert (
        result["intent"]["architectural_action"]
        ==
        "adaptive_reuse"
    )


    assert (
        result["intent"]["program_category"]
        ==
        "commercial"
    )


    assert (
        "open_space"
        in
        result["intent"]["requirements"]
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_intent_bridge_program_aware_v1()