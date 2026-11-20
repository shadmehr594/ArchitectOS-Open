from core.bim.ifc_architectural_consistency_validator_v1 import (
    IFCArchitecturalConsistencyValidatorV1
)



def test_ifc_architectural_consistency_validator_v1():


    print(
        "\n====== IFC ARCHITECTURAL CONSISTENCY VALIDATOR V1 ======"
    )


    validator = IFCArchitecturalConsistencyValidatorV1()



    result = validator.validate(

        "exports/ArchitectOS_Project.ifc"

    )



    print(

        "\n====== ARCHITECTURAL CONSISTENCY RESULT ======"

    )


    print(result)



    assert (

        result["status"]

        ==

        "passed"

    )



    assert (

        result["architectural_health"]["score"]

        ==

        100

    )



    inventory = result["inventory"]



    assert (

        inventory["walls"]

        >

        0

    )



    assert (

        inventory["doors"]

        >

        0

    )



    assert (

        inventory["windows"]

        >

        0

    )



    assert (

        inventory["storeys"]

        >

        0

    )



    print(

        "\n====== TEST PASSED ======"

    )




if __name__ == "__main__":

    test_ifc_architectural_consistency_validator_v1()