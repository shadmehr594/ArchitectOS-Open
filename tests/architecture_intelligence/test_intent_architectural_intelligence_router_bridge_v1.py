from core.intent.architectural_intelligence_router_bridge_v1 import (
    IntentArchitecturalIntelligenceRouterBridgeV1
)

from core.chat_architect.architectural_intelligence_runtime_v1 import (
    ArchitecturalIntelligenceRuntimeV1
)



def test_intent_architectural_intelligence_router_bridge_v1():


    print(
        "\n====== INTENT ARCHITECTURAL INTELLIGENCE ROUTER BRIDGE V1 ======"
    )



    runtime = (
        ArchitecturalIntelligenceRuntimeV1()
    )



    router_bridge = (
        IntentArchitecturalIntelligenceRouterBridgeV1(
            architectural_runtime=runtime
        )
    )



    result = router_bridge.route(

        "existing_building_analysis",

        "این ساختمان موجود را بررسی کن",

        {

            "building_state":

            {

                "floors":3,

                "walls":38,

                "doors":17,

                "windows":20,

                "openings":37

            }

        }

    )



    print(
        "\n====== ROUTE RESULT ======"
    )


    print(
        result
    )



    assert (
        result["route"]
        ==
        "architectural_intelligence"
    )


    assert (
        result["ready"]
        ==
        True
    )


    assert (
        result["result"]["ready"]
        ==
        True
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_intent_architectural_intelligence_router_bridge_v1()