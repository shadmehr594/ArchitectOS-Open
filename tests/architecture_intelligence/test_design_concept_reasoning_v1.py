from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_design_concept_reasoning_v1():


    print(
        "\n====== DESIGN CONCEPT REASONING V1 ======"
    )


    brain = ArchitecturalBrain()



    intent = {


        "building_type":
        "villa",


        "style":
        "modern",


        "site":
        {


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
        "\n====== DESIGN CONCEPT ======"
    )


    print(
        model.design_concept
    )


    assert (
        "design_principles"
        in model.design_concept
    )


    print(
        "\n====== TEST PASSED ======"
    )