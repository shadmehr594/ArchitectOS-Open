from core.architecture_intelligence.architectural_flow_orchestrator_v1 import (
    ArchitecturalFlowOrchestratorV1
)



def test_architectural_flow_orchestrator_v1():


    print(
        "\n====== ARCHITECTURAL FLOW ORCHESTRATOR V1 ======"
    )



    orchestrator = (
        ArchitecturalFlowOrchestratorV1()
    )



    source = {


        "building_state":

        {

            "floors":
                3,

            "walls":
                38,

            "doors":
                17,

            "windows":
                20

        }

    }



    result = orchestrator.run(
        source
    )



    print(
        "\n====== FLOW RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "ARCHITECTURAL_FLOW_ORCHESTRATOR_V1"
    )


    assert (
        result["ready"]
        ==
        True
    )


    assert (
        result["decision"]["action"]
        ==
        "preserve_existing_shell"
    )


    assert (
        result["planner_context"]["building_type"]
        ==
        "existing_building"
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_flow_orchestrator_v1()