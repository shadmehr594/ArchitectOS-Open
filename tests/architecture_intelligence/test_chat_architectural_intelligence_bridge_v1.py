from core.chat_architect.architectural_intelligence_bridge_v1 import (
    ChatArchitectArchitecturalIntelligenceBridgeV1
)

from core.architecture_intelligence.architectural_flow_orchestrator_v1 import (
    ArchitecturalFlowOrchestratorV1
)



def test_chat_architectural_intelligence_bridge_v1():


    print(
        "\n====== CHATARCHITECT ARCHITECTURAL INTELLIGENCE BRIDGE V1 ======"
    )



    flow = (
        ArchitecturalFlowOrchestratorV1()
    )



    bridge = (
        ChatArchitectArchitecturalIntelligenceBridgeV1(
            architectural_flow=flow
        )
    )



    result = bridge.process(

        "این ساختمان موجود را بررسی کن",

        {

            "building_state":

            {

                "floors":3,

                "walls":38,

                "doors":17,

                "windows":20

            }

        }

    )



    print(
        "\n====== CHAT BRIDGE RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "CHATARCHITECT_ARCHITECTURAL_INTELLIGENCE_BRIDGE_V1"
    )


    assert (
        result["response_ready"]
        ==
        True
    )


    assert (
        result["architectural_flow"]["decision"]["action"]
        ==
        "preserve_existing_shell"
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_chat_architectural_intelligence_bridge_v1()