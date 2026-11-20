from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_space_generation_v1():


    print(
        "\n====== SPACE GENERATION V1 ======"
    )


    brain = ArchitecturalBrain()



    intent = {


        "site": {


            "boundary":

            [

                (0,0),

                (20,0),

                (20,30),

                (0,30)

            ],


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


        },


        "building_type":
        "villa",


        "floors":
        2,


        "requirements":

        [

            "pool",

            "garden",

            "parking"

        ]

    }



    model = brain.design(
        intent
    )



    print(
        "\n====== SPACE GENERATION RESULT ======"
    )


    print(
        model.space_generation
    )



    print(
        "\n====== TEST PASSED ======"
    )