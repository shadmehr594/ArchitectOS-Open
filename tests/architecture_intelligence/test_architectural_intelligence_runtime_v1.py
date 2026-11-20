from core.chat_architect.architectural_intelligence_runtime_v1 import (
    ArchitecturalIntelligenceRuntimeV1
)



def test_architectural_intelligence_runtime_v1():


    print(
        "\n====== ARCHITECTURAL INTELLIGENCE RUNTIME V1 ======"
    )



    runtime = (
        ArchitecturalIntelligenceRuntimeV1()
    )



    result = runtime.process(

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
        "\n====== RUNTIME RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "ARCHITECTURAL_INTELLIGENCE_RUNTIME_V1"
    )


    assert (
        result["ready"]
        ==
        True
    )


    assert (
        result["result"]
        ["architectural_flow"]
        ["memory"]
        ["stored"]
        ==
        True
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_intelligence_runtime_v1()