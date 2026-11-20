from core.architecture.planner.ifc_planner_bridge_v1 import (
    IFCPlannerBridgeV1
)



def test_ifc_planner_bridge_v1():


    print(
        "\n====== IFC PLANNER BRIDGE V1 ======"
    )


    bridge = IFCPlannerBridgeV1()



    report = {


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

            "Existing IFC architectural model"

        ]

    }



    result = bridge.build_planner_input(
        report
    )



    print(
        "\n====== PLANNER INPUT RESULT ======"
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
        result["ready"]
        ==
        True
    )


    assert (
        result["planner_context"]["building_state"]["floors"]
        ==
        3
    )


    assert (
        result["planner_context"]["building_state"]["walls"]
        ==
        38
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_planner_bridge_v1()