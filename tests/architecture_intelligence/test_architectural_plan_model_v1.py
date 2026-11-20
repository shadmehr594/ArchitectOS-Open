from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_architectural_plan_model_v1():


    print(
        "\n====== ARCHITECTURAL PLAN MODEL V1 ======"
    )


    brain = ArchitecturalBrain()



    intent = {


        "building_type":
        "villa",


        "style":
        "modern",


        "spaces":

        [

            "living_room",

            "kitchen",

            "bedroom",

            "pool",

            "terrace"

        ],


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
        "\n====== PLAN MODEL ======"
    )


    print(
        model.plan_model
    )



    assert (
        "spaces"
        in model.plan_model
    )


    print(
        "\n====== TEST PASSED ======"
    )