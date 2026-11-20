from core.brain_response_adapter_bridge_v1 import (
    BrainResponseAdapterBridgeV1
)



def test_brain_response_adapter_bridge_v1():


    print(
        "\n====== BRAIN RESPONSE ADAPTER BRIDGE V1 ======"
    )



    adapter = (
        BrainResponseAdapterBridgeV1()
    )



    brain_response = {


        "engine":

            "BRAIN_ARCHITECTURAL_RESPONSE_BUILDER_V1",



        "response":

        {

            "summary":

                "Existing building architectural evaluation completed",


            "architectural_direction":

                "preserve_existing_shell",


            "target":

                "architectural_shell",


            "confidence":

                0.95

        }

    }



    result = adapter.adapt(
        brain_response
    )



    print(
        "\n====== ADAPTER RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "BRAIN_RESPONSE_ADAPTER_BRIDGE_V1"
    )


    assert (
        result["chat_ready"]
        ==
        True
    )


    assert (
        result["response"]["architectural"]["direction"]
        ==
        "preserve_existing_shell"
    )


    assert (
        result["response"]["architectural"]["confidence"]
        ==
        0.95
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_brain_response_adapter_bridge_v1()