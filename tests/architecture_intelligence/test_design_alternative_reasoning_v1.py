from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_design_alternative_reasoning_v1():


    print(
        "\n====== DESIGN ALTERNATIVE REASONING V1 ======"
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
                "north":"top",
                "south":"street"
            },


            "neighbors":
            {
                "east":True,
                "west":True
            },


            "climate":
            {
                "type":"hot_dry"
            },


            "access":
            {
                "main_access":"south"
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
        "\n====== DESIGN ALTERNATIVES ======"
    )


    print(
        model.design_alternatives
    )



    assert (
        model.design_alternatives
        is not None
    )


    assert (
        len(
            model.design_alternatives["alternatives"]
        ) > 0
    )


    print(
        "\n====== TEST PASSED ======"
    )