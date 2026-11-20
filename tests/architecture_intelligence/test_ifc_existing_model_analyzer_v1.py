from core.bim.architectural_existing_model_analyzer_v1 import (
    ArchitecturalExistingModelAnalyzerV1
)



def test_ifc_existing_model_analyzer_v1():


    print(
        "\n====== IFC EXISTING MODEL ANALYZER V1 ======"
    )


    context = {


        "context_type":
            "architectural_existing_model",


        "building_state":
            {

                "floors": 3,

                "walls": 38,

                "doors": 17,

                "windows": 20

            }


    }



    analyzer = ArchitecturalExistingModelAnalyzerV1()



    result = analyzer.analyze(
        context
    )



    print(
        "\n====== ANALYSIS RESULT ======"
    )


    print(
        result
    )



    assert (
        result["planner_ready"]
        ==
        True
    )


    assert (
        result["building_analysis"]["floors"]
        ==
        3
    )


    assert (
        result["building_analysis"]["walls"]
        ==
        38
    )


    assert (
        result["building_analysis"]["openings"]
        ==
        37
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_existing_model_analyzer_v1()