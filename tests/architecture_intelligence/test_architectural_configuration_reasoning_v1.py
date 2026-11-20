from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_architectural_configuration_reasoning_v1():


    print(
        "\n====== ARCHITECTURAL CONFIGURATION REASONING V1 ======"
    )


    brain = ArchitecturalBrain()



    intent = {


        "building_type":
        "villa",


        "floors":
        2,


        "style":
        "modern",


        "requirements":
        [

            "pool",

            "garden"

        ],


        "site":
        {


            "boundary":

            [

                (0,0),

                (20,0),

                (20,30),

                (0,30)

            ],


            "orientation":

            {

                "north":
                "top",

                "south":
                "street"

            },


            "climate":

            {

                "type":
                "hot_dry"

            },


            "access":

            {

                "main_access":
                "south"

            }

        }

    }



    model = brain.design(
        intent
    )



    print(
        "\n====== CONFIGURATION RESULT ======"
    )


    print(
        model.configuration
    )



    print(
        "\n====== TEST PASSED ======"
    )