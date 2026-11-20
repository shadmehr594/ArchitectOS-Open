from core.architecture.planner.ifc_architectural_context_adapter_v1 import (
    IFCArchitecturalContextAdapterV1
)



def test_ifc_architectural_context_adapter_v1():


    print(
        "\n====== IFC ARCHITECTURAL CONTEXT ADAPTER V1 ======"
    )


    adapter = IFCArchitecturalContextAdapterV1()



    report = {


        "engine":
            "IFC_ARCHITECTURAL_INTELLIGENCE_REPORT_V1",


        "building_summary":
        {

            "floors":3,

            "walls":38,

            "doors":17,

            "windows":20,

            "openings":37

        },


        "architectural_quality":
        {

            "score":100,

            "status":"healthy"

        },


        "observations":
        [

            "3 storeys detected",

            "38 architectural walls detected"

        ]

    }



    result = adapter.adapt(
        report
    )



    print(
        "\n====== PLANNER CONTEXT RESULT ======"
    )


    print(
        result
    )



    assert (
        result["source"]
        ==
        "IFC"
    )


    assert (
        result["building_state"]["floors"]
        ==
        3
    )


    assert (
        result["building_state"]["walls"]
        ==
        38
    )


    assert (
        result["planner_ready"]
        ==
        True
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_architectural_context_adapter_v1()