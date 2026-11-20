from core.bim.architectural_change_planner_v1 import (
    ArchitecturalChangePlannerV1
)



def test_architectural_change_planner_v1():


    print(
        "\n====== ARCHITECTURAL CHANGE PLANNER V1 ======"
    )


    planner = ArchitecturalChangePlannerV1()



    execution_context = {


        "execution_plan":

        [

            {

                "domain":
                    "existing_architecture",

                "operation":
                    "preserve",

                "target":
                    "architectural_shell"

            },

            {

                "domain":
                    "space_planning",

                "operation":
                    "evaluate_modification",

                "target":
                    "existing_layout"

            },

            {

                "domain":
                    "facade_analysis",

                "operation":
                    "analyze_openings",

                "target":
                    "existing_openings"

            }

        ]

    }



    result = planner.plan(
        execution_context
    )



    print(
        "\n====== CHANGE PROPOSAL RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "ARCHITECTURAL_CHANGE_PLANNER_V1"
    )


    assert (
        result["planner_ready"]
        ==
        True
    )


    assert (
        len(
            result["changes"]
        )
        ==
        3
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_change_planner_v1()