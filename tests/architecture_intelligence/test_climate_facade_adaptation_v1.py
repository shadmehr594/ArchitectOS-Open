from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_climate_facade_adaptation_v1():


    print(
        "\n====== CLIMATE FACADE ADAPTATION V1 ======"
    )


    brain = ArchitecturalBrain()


    intent = {

        "building_type":
        "villa",

        "style":
        "roman_classic",

        "site": {

            "climate": {
                "type":
                "hot_dry"
            },

            "orientation": {

                "south":
                "street",

                "west":
                "neighbor"

            }

        }

    }



    model = brain.design(
        intent
    )


    print(
        "\n====== CLIMATE FACADE RESULT ======"
    )


    print(
        model.climate_facade_strategy
    )


    assert (
        "deep window reveals"
        in
        model.climate_facade_strategy[
            "facade_modifications"
        ]
    )


    assert (
        "control summer solar gain"
        in
        model.climate_facade_strategy[
            "orientation_response"
        ]
    )


    print(
        "\n====== TEST PASSED ======"
    )