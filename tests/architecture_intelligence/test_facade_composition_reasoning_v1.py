from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_facade_composition_reasoning_v1():


    print(
        "\n====== FACADE COMPOSITION REASONING V1 ======"
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
        "\n====== FACADE COMPOSITION RESULT ======"
    )


    print(
        model.facade_composition
    )


    composition = model.facade_composition[
        "facade_composition"
    ]


    assert (
        composition["organization"]
        ==
        "symmetrical"
    )


    assert (
        composition["entrance"]["importance"]
        ==
        "main_visual_focus"
    )


    print(
        "\n====== TEST PASSED ======"
    )