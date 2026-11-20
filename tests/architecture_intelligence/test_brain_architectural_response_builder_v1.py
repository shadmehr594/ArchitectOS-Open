from core.brain_architectural_response_builder_v1 import (
    BrainArchitecturalResponseBuilderV1
)



def test_brain_architectural_response_builder_v1():


    print(
        "\n====== BRAIN ARCHITECTURAL RESPONSE BUILDER V1 ======"
    )



    builder = (
        BrainArchitecturalResponseBuilderV1()
    )



    brain_context = {


        "brain_context":

        {

            "decision_type":
                "existing_building_architectural_plan",


            "architectural_intent":
                "existing_building_preservation",


            "architectural_action":
                "preserve_existing_shell",


            "target":
                "architectural_shell",


            "confidence":
                0.95

        }

    }



    result = builder.build(
        brain_context
    )



    print(
        "\n====== RESPONSE RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "BRAIN_ARCHITECTURAL_RESPONSE_BUILDER_V1"
    )


    assert (
        result["ready"]
        ==
        True
    )


    assert (
        result["response"]["architectural_direction"]
        ==
        "preserve_existing_shell"
    )


    assert (
        result["response"]["confidence"]
        ==
        0.95
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_brain_architectural_response_builder_v1()