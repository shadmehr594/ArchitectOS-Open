from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_spatial_layout_reasoning_v1():


    print(
        "\n====== SPATIAL LAYOUT REASONING V1 ======"
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

            "orientation":

            {

                "south":
                "street"

            },


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
        "\n====== LAYOUT RESULT ======"
    )


    print(
        model.layout
    )



    assert (
        "zones"
        in model.layout
    )


    print(
        "\n====== TEST PASSED ======"
    )