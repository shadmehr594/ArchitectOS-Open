from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_alternative_selection_reasoning_v1():


    print(
        "\n====== ALTERNATIVE SELECTION REASONING V1 ======"
    )


    brain = ArchitecturalBrain()



    intent = {


        "site":
        {

            "neighbors":
            {
                "east": True,
                "west": True
            },


            "access":
            {
                "main_access":
                "south"
            }

        },


        "building_type":
        "villa",


        "requirements":
        [
            "garden",
            "pool"
        ],


        "priorities":
        [
            "privacy"
        ]

    }



    model = brain.design(
        intent
    )



    print(
        "\n====== SELECTED ALTERNATIVE ======"
    )


    print(
        model.selected_alternative
    )



    assert (
        model.selected_alternative
        is not None
    )


    assert (
        model.selected_alternative["selected_alternative"]["name"]
        ==
        "protected_compact_mass_strategy"
    )


    print(
        "\n====== TEST PASSED ======"
    )