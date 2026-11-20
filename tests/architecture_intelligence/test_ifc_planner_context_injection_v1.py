from core.architecture.planner.planner_context_injection_v1 import (
    PlannerContextInjectionV1
)



def test_ifc_planner_context_injection_v1():


    print(
        "\n====== IFC PLANNER CONTEXT INJECTION V1 ======"
    )


    injector = PlannerContextInjectionV1()



    bridge_result = {


        "source":
            "IFC",


        "intent":
            "existing_building_analysis",


        "ready":
            True,


        "planner_context":
        {


            "context_type":
                "architectural_existing_model",


            "building_state":
            {

                "floors":3,

                "walls":38,

                "doors":17,

                "windows":20

            },


            "planner_ready":
                True

        }

    }



    result = injector.inject(
        bridge_result
    )



    print(
        "\n====== INJECTION RESULT ======"
    )


    print(
        result
    )



    assert (
        result["context_source"]
        ==
        "IFC"
    )


    assert (
        result["planner_ready"]
        ==
        True
    )


    assert (
        result["context"]["building_state"]["floors"]
        ==
        3
    )


    assert (
        result["context"]["building_state"]["walls"]
        ==
        38
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_planner_context_injection_v1()