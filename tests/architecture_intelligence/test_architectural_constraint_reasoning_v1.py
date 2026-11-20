from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_architectural_constraint_reasoning_v1():


    print(
        "\n====== ARCHITECTURAL CONSTRAINT REASONING V1 ======"
    )


    brain = ArchitecturalBrain()



    intent = {


        "site":
        {

            "neighbors":
            {
                "east": True,
                "west": True
            },


            "climate":
            {
                "type":
                "hot_dry"
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
        "\n====== CONSTRAINT MODEL ======"
    )


    print(
        model.architectural_constraints
    )



    assert (
        model.architectural_constraints
        is not None
    )


    assert (
        len(
            model.architectural_constraints["constraints"]
        )
        >
        0
    )


    assert (
        len(
            model.architectural_constraints["design_freedom"]
        )
        >
        0
    )


    print(
        "\n====== TEST PASSED ======"
    )