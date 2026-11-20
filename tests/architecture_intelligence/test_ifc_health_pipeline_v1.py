import os


from core.bim.ifc_health_pipeline import (
    IFCHealthPipelineV1
)



def test_ifc_health_pipeline_v1():


    print(
        "\n====== IFC HEALTH PIPELINE V1 ======"
    )



    ifc_path = (
        "exports/"
        "test_spatial_validator.ifc"
    )



    assert (
        os.path.exists(
            ifc_path
        )
    )



    pipeline = IFCHealthPipelineV1()



    result = pipeline.run(
        ifc_path
    )



    print(
        "\n====== BIM HEALTH PIPELINE RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "ARCHITECTOS_BIM_HEALTH_PIPELINE"
    )



    assert (
        result["quality"]["score"]
        ==
        100
    )


    assert (
        result["quality"]["status"]
        ==
        "passed"
    )



    assert (
        result["spatial"]["score"]
        ==
        100
    )


    assert (
        result["spatial"]["status"]
        ==
        "passed"
    )



    assert (
        result["overall"]["score"]
        ==
        100
    )



    assert (
        result["overall"]["status"]
        ==
        "healthy"
    )



    assert (
        result["report"]["health"]["score"]
        ==
        100
    )



    print(
        "\n====== TEST PASSED ======"
    )




if __name__ == "__main__":


    test_ifc_health_pipeline_v1()