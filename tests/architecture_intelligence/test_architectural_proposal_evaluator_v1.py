from core.bim.architectural_proposal_evaluator_v1 import (
    ArchitecturalProposalEvaluatorV1
)



def test_architectural_proposal_evaluator_v1():


    print(
        "\n====== ARCHITECTURAL PROPOSAL EVALUATOR V1 ======"
    )


    evaluator = ArchitecturalProposalEvaluatorV1()



    context = {


        "changes":

        [

            {

                "type":
                    "architectural_preservation",

                "target":
                    "architectural_shell"

            },

            {

                "type":
                    "space_modification_proposal",

                "target":
                    "existing_layout"

            },

            {

                "type":
                    "opening_optimization_proposal",

                "target":
                    "existing_openings"

            }

        ]

    }



    result = evaluator.evaluate(
        context
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
        "ARCHITECTURAL_PROPOSAL_EVALUATOR_V1"
    )


    assert (
        result["planner_ready"]
        ==
        True
    )


    assert (
        len(
            result["evaluations"]
        )
        ==
        3
    )


    assert (
        result["evaluations"][0]["score"]
        ==
        95
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_proposal_evaluator_v1()