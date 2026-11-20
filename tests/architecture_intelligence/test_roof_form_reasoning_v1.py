from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_roof_form_reasoning_v1():


    print(
        "\n====== ROOF FORM REASONING V1 ======"
    )


    brain = ArchitecturalBrain()


    intent = {

        "building_type":
        "villa",


        "style":
        "roman_classic",


        "site":
        {

            "climate":
            {
                "type":
                "hot_dry"
            }

        }

    }


    model = brain.design(
        intent
    )


    print(
        "\n====== ROOF RESULT ======"
    )


    print(
        model.roof_strategy
    )


    roof = model.roof_strategy[
        "roof_strategy"
    ]


    assert (
        roof["roof_type"]
        ==
        "classical_dome"
    )


    assert (
        "central_dome"
        in
        roof["elements"]
    )


    print(
        "\n====== TEST PASSED ======"
    )