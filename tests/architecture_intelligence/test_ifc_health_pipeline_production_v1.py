import os


from core.bim.ifc_health_pipeline import (
    IFCHealthPipelineV1
)



def test_ifc_health_pipeline_production_v1():


    print(
        "\n====== IFC HEALTH PIPELINE PRODUCTION V1 ======"
    )


    ifc_path = (
        "exports/"
        "ArchitectOS_Project.ifc"
    )



    assert os.path.exists(
        ifc_path
    ), (
        "ArchitectOS_Project.ifc not found"
    )



    pipeline = IFCHealthPipelineV1()



    result = pipeline.run(
        ifc_path
    )



    print(
        "\n====== PRODUCTION HEALTH RESULT ======"
    )


    print(
        result
    )



    assert (
        result["quality"]["status"]
        ==
        "passed"
    )


    assert (
        result["spatial"]["status"]
        ==
        "passed"
    )



    assert (
        result["overall"]["score"]
        >=
        90
    )



    print(
        "\n====== PRODUCTION TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_health_pipeline_production_v1()