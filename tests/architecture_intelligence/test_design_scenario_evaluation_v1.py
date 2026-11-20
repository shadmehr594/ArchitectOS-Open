from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_design_scenario_evaluation_v1():


    print(
        "\n====== DESIGN SCENARIO EVALUATION V1 ======"
    )


    brain = ArchitecturalBrain()



    intent = {


        "building_type":
        "villa",


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
        "\n====== SCENARIO EVALUATION ======"
    )


    print(
        model.design_scenario_evaluation
    )



    assert (
        len(
            model.design_scenario_evaluation[
                "evaluated_scenarios"
            ]
        )
        > 0
    )


    print(
        "\n====== TEST PASSED ======"
    )