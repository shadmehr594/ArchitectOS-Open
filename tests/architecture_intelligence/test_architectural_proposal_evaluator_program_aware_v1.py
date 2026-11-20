from core.architecture_intelligence.architectural_proposal_evaluator_program_aware_v1 import (
    ArchitecturalProposalEvaluatorProgramAwareV1
)



def test_architectural_proposal_evaluator_program_aware_v1():


    print(
        "\n====== ARCHITECTURAL PROPOSAL EVALUATOR PROGRAM AWARE V1 ======"
    )



    evaluator = (
        ArchitecturalProposalEvaluatorProgramAwareV1()
    )



    proposal_context = {


        "proposal":

        {


            "proposal_type":

                "existing_building_program_transformation",


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


            "proposals":

            [

                {

                    "type":

                        "architectural_shell_preservation",


                    "action":

                        "retain_existing_structure"

                },


                {

                    "type":

                        "space_reconfiguration",


                    "action":

                        "create_gym_layout"

                },


                {

                    "type":

                        "program_validation",


                    "action":

                        "validate_gym_requirements"

                }

            ]

        }

    }



    result = evaluator.evaluate(

        proposal_context

    )



    print(
        "\n====== EVALUATION RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "ARCHITECTURAL_PROPOSAL_EVALUATOR_PROGRAM_AWARE_V1"
    )


    assert (
        result["evaluation_ready"]
        ==
        True
    )


    assert (
        result["evaluation"]["target_program"]
        ==
        "gym"
    )


    assert (
        len(
            result["evaluation"]["evaluations"]
        )
        ==
        3
    )


    assert (
        result["evaluation"]["program_category"]
        ==
        "commercial"
    )


    assert (
        "open_space"
        in
        result["evaluation"]["requirements"]
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_proposal_evaluator_program_aware_v1()