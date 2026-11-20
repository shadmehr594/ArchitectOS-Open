from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_massing_selection_reasoning_v1():


    print(
        "\n====== MASSING SELECTION REASONING V1 ======"
    )



    brain = ArchitecturalBrain()



    intent = {


        "building_type":
        "villa",


        "style":
        "modern",


        "requirements":
        [
            "garden",
            "pool"
        ],


        "site":
        {

            "neighbors":
            {

                "east": True,

                "west": True

            }

        }

    }



    model = brain.design(
        intent
    )



    print(
        "\n====== MASSING SELECTION ======"
    )


    print(
        model.massing_selection
    )



    assert (
        model.massing_selection[
            "selected_massing"
        ]
        is not None
    )



    print(
        "\n====== TEST PASSED ======"
    )