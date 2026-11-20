from core.conversation.existing_model_context_v1 import (
    ExistingModelConversationContextV1
)



def test_existing_model_context_v1():


    print(
        "\n====== EXISTING MODEL CONVERSATION CONTEXT V1 ======"
    )



    builder = (
        ExistingModelConversationContextV1()
    )



    architectural_context = {


        "building_type":

            "existing_building",


        "architectural_intent":

            "existing_building_preservation",


        "architectural_goal":

            "preserve_existing_shell",


        "target":

            "architectural_shell",


        "confidence":

            0.95

    }



    result = builder.build(
        architectural_context
    )



    print(
        "\n====== CONVERSATION CONTEXT RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "EXISTING_MODEL_CONVERSATION_CONTEXT_V1"
    )


    assert (
        result["ready"]
        ==
        True
    )


    assert (
        result["conversation_context"]["existing_model"]
        ==
        True
    )


    assert (
        result["conversation_context"]["building_type"]
        ==
        "existing_building"
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_existing_model_context_v1()