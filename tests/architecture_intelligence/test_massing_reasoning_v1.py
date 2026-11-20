from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_massing_reasoning_v1():


    print(
        "\n====== MASSING REASONING V1 ======"
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

        ]

    }



    model = brain.design(
        intent
    )



    print(
        "\n====== MASSING RESULT ======"
    )


    print(
        model.massing_analysis
    )



    assert (
        model.massing_analysis
        is not None
    )


    assert (
        len(
            model.massing_analysis["massing_options"]
        )
        >
        0
    )


    print(
        "\n====== TEST PASSED ======"
    )