from core.bim.ifc_quality_validator_v2 import IFCQualityValidatorV2


def test_ifc_quality_validator_geometry_v2_1():

    print(
        "\n====== IFC QUALITY VALIDATOR GEOMETRY V2.1 ======"
    )


    validator = IFCQualityValidatorV2()


    result = validator.validate(
        "exports/test_quality_validator.ifc"
    )


    print(
        "\n====== VALIDATION RESULT ======"
    )


    print(result)


    assert (
        result["status"]
        ==
        "passed"
    )


    statistics = result["statistics"]


    assert (
        statistics["walls"]
        >
        0
    )


    assert (
        statistics["columns"]
        >
        0
    )


    assert (
        statistics["windows"]
        >
        0
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_quality_validator_geometry_v2_1()