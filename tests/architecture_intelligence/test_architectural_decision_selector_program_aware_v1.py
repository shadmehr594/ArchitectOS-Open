from core.architecture_intelligence.architectural_decision_selector_program_aware_v1 import (
    ArchitecturalDecisionSelectorProgramAwareV1
)



def test_architectural_decision_selector_program_aware_v1():


    print(
        "\n====== ARCHITECTURAL DECISION SELECTOR PROGRAM AWARE V1 ======"
    )



    selector = (
        ArchitecturalDecisionSelectorProgramAwareV1()
    )



    evaluation_context = {


        "evaluation":

        {


            "evaluation_type":

                "program_aware_architectural_proposal_evaluation",


            "target_program":

                "gym",

            "program_category":
                "commercial",


            "requirements":
                [
                    "open_space",
                    "equipment_area",
                    "changing_room"
                ],


            "evaluations":

            [

                {

                    "proposal":

                        "architectural_shell_preservation",


                    "action":

                        "retain_existing_structure",


                    "score":

                        95

                },


                {

                    "proposal":

                        "space_reconfiguration",


                    "action":

                        "create_gym_layout",


                    "score":

                        85

                },


                {

                    "proposal":

                        "program_validation",


                    "action":

                        "validate_gym_requirements",


                    "score":

                        90

                }

            ]

        }

    }



    result = selector.select(

        evaluation_context

    )



    print(
        "\n====== SELECTED DECISION RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "ARCHITECTURAL_DECISION_SELECTOR_PROGRAM_AWARE_V1"
    )


    assert (
        result["decision_ready"]
        ==
        True
    )


    assert (
        result["decision"]["proposal"]
        ==
        "architectural_shell_preservation"
    )


    assert (
        result["decision"]["score"]
        ==
        95
    )


    assert (
        result["decision"]["program_category"]
        ==
        "commercial"
    )


    assert (
        "open_space"
        in
        result["decision"]["requirements"]
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_decision_selector_program_aware_v1()