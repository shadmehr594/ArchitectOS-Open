from core.brain_architectural_decision_consumer_v1 import (
    BrainArchitecturalDecisionConsumerV1
)



def test_brain_architectural_decision_consumer_v1():


    print(
        "\n====== BRAIN ARCHITECTURAL DECISION CONSUMER V1 ======"
    )


    consumer = (
        BrainArchitecturalDecisionConsumerV1()
    )



    adapter_result = {


        "decision":

        {

            "type":
                "existing_building_architectural_plan",


            "intent":
                "existing_building_preservation",


            "action":
                "preserve_existing_shell",


            "target":
                "architectural_shell",


            "confidence":
                0.95

        }

    }



    result = consumer.consume(
        adapter_result
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
        "BRAIN_ARCHITECTURAL_DECISION_CONSUMER_V1"
    )


    assert (
        result["response_ready"]
        ==
        True
    )


    assert (
        result["brain_context"]["architectural_action"]
        ==
        "preserve_existing_shell"
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

    test_brain_architectural_decision_consumer_v1()