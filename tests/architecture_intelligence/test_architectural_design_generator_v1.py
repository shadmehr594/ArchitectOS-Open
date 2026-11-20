from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_architectural_design_generator_v1():


    print(
        "\n====== ARCHITECTURAL DESIGN GENERATOR V1 ======"
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
        "\n====== DESIGN INTENT RESULT ======"
    )


    print(
        model.design_intent
    )



    assert (
        model.design_intent
        is not None
    )


    assert (
        len(
            model.design_intent[
                "architectural_strategy"
            ]
        )
        >
        0
    )


    print(
        "\n====== TEST PASSED ======"
    )