# ==========================================================
# ARCHITECTURAL INTELLIGENCE END TO END TEST V1
# USER TO ARCHITECTURAL RESPONSE VALIDATION
# ==========================================================


from core.intent.architectural_intelligence_router_bridge_v1 import (
    IntentArchitecturalIntelligenceRouterBridgeV1
)

from core.chat_architect.architectural_intelligence_runtime_v1 import (
    ArchitecturalIntelligenceRuntimeV1
)



def test_architectural_intelligence_end_to_end_v1():


    print(
        "\n====== ARCHITECTURAL INTELLIGENCE END TO END V1 ======"
    )



    # ------------------------------------------------------
    # USER INPUT
    # ------------------------------------------------------


    user_message = (
        "این ساختمان موجود را بررسی کن"
    )



    # ------------------------------------------------------
    # INTENT ENGINE RESULT
    # ------------------------------------------------------


    detected_intent = (
        "existing_building_analysis"
    )



    # ------------------------------------------------------
    # RUNTIME
    # ------------------------------------------------------


    runtime = (
        ArchitecturalIntelligenceRuntimeV1()
    )



    router = (
        IntentArchitecturalIntelligenceRouterBridgeV1(
            architectural_runtime=runtime
        )
    )



    result = router.route(

        detected_intent,

        user_message,

        {

            "building_state":

            {

                "floors":
                    3,

                "walls":
                    38,

                "doors":
                    17,

                "windows":
                    20,

                "openings":
                    37

            }

        }

    )



    print(
        "\n====== END TO END RESULT ======"
    )


    print(
        result
    )



    # ------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------


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



    runtime_result = (
        result["result"]
    )



    assert (
        runtime_result["ready"]
        ==
        True
    )



    flow = (
        runtime_result["result"]
        ["architectural_flow"]
    )



    assert (
        flow["decision"]["action"]
        ==
        "preserve_existing_shell"
    )



    assert (
        flow["memory"]["stored"]
        ==
        True
    )



    assert (
        flow["response"]["direction"]
        ==
        "preserve_existing_shell"
    )



    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_intelligence_end_to_end_v1()