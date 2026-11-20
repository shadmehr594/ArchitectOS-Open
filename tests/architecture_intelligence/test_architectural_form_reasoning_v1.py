from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_architectural_form_reasoning_v1():


    print(
        "\n====== ARCHITECTURAL FORM REASONING V1 ======"
    )


    brain = ArchitecturalBrain()



    intent = {


        "site":
        {

            "neighbors":
            {
                "east": True,
                "west": True
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
        "\n====== FORM ANALYSIS ======"
    )


    print(
        model.form_analysis
    )



    assert (
        model.form_analysis
        is not None
    )


    assert (
        len(
            model.form_analysis["form_options"]
        )
        >
        0
    )


    print(
        "\n====== TEST PASSED ======"
    )