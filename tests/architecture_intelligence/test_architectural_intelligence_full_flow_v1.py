from core.architecture_intelligence.architectural_flow_orchestrator_v1 import (
    ArchitecturalFlowOrchestratorV1
)

from core.memory.architectural_decision_memory_writer_v1 import (
    ArchitecturalDecisionMemoryWriterV1
)



def test_architectural_intelligence_full_flow_v1():


    print(
        "\n====== ARCHITECTURAL INTELLIGENCE FULL FLOW V1 ======"
    )



    memory_writer = (
        ArchitecturalDecisionMemoryWriterV1()
    )



    orchestrator = (
        ArchitecturalFlowOrchestratorV1(
            memory_writer=memory_writer
        )
    )



    ifc_context = {


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



    result = orchestrator.run(
        ifc_context
    )



    print(
        "\n====== FULL FLOW RESULT ======"
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


    # IFC ANALYSIS

    assert (
        result["analysis"]["source"]
        ==
        "IFC"
    )


    # DECISION

    assert (
        result["decision"]["action"]
        ==
        "preserve_existing_shell"
    )



    # PLANNER

    assert (
        result["planner_context"]["building_type"]
        ==
        "existing_building"
    )



    # MEMORY

    assert (
        result["memory"]["stored"]
        ==
        True
    )



    assert (
        result["memory"]["memory"]["target"]
        ==
        "architectural_shell"
    )



    # RESPONSE

    assert (
        result["response"]["direction"]
        ==
        "preserve_existing_shell"
    )



    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_intelligence_full_flow_v1()