from core.bim.ifc_architectural_intelligence_report_v1 import (
    IFCArchitecturalIntelligenceReportV1
)



def test_ifc_architectural_intelligence_report_v1():


    print(
        "\n====== IFC ARCHITECTURAL INTELLIGENCE REPORT V1 ======"
    )


    engine = IFCArchitecturalIntelligenceReportV1()


    result = engine.generate(
        "exports/ArchitectOS_Project.ifc"
    )


    print(
        "\n====== INTELLIGENCE REPORT RESULT ======"
    )


    print(result)



    assert (
        result["architectural_quality"]["score"]
        ==
        100
    )


    assert (
        result["planner_ready"]
        ==
        True
    )


    assert (
        result["building_summary"]["walls"]
        >
        0
    )


    assert (
        result["building_summary"]["floors"]
        >
        0
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_architectural_intelligence_report_v1()