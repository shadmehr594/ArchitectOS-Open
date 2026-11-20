from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_design_scenario_generator_v1():


    print(
        "\n====== DESIGN SCENARIO GENERATOR V1 ======"
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
        "\n====== DESIGN SCENARIOS ======"
    )


    print(
        model.design_scenarios
    )



    assert (
        len(
            model.design_scenarios["scenarios"]
        )
        > 0
    )



    print(
        "\n====== TEST PASSED ======"
    )