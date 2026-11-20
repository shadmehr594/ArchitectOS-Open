import os


from core.bim.ifc_bim_consistency_validator_v1 import (
    IFCBIMConsistencyValidatorV1
)



def test_ifc_bim_consistency_validator_v1():


    print(
        "\n====== IFC BIM CONSISTENCY VALIDATOR V1 ======"
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



    validator = IFCBIMConsistencyValidatorV1()



    result = validator.validate(
        ifc_path
    )



    print(
        "\n====== BIM CONSISTENCY RESULT ======"
    )


    print(
        result
    )



    assert (
        result["checks"]["geometry"]
        ==
        True
    )


    assert (
        result["checks"]["placement"]
        ==
        True
    )


    assert (
        result["inventory"]["walls"]
        >
        0
    )


    assert (
        result["inventory"]["windows"]
        >
        0
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_bim_consistency_validator_v1()