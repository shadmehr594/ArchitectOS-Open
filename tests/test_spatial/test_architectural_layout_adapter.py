from core.spatial.architectural_layout_adapter import (
    ArchitecturalLayoutAdapter
)



def test_courtyard_layout_strategy():


    engine = ArchitecturalLayoutAdapter()



    spaces = [


        {

            "id":
                "courtyard_001",

            "type":
                "courtyard"

        },


        {

            "id":
                "office_001",

            "type":
                "office",

            "adjacency":

            {

                "preferred":

                [

                    "courtyard"

                ]

            }

        }

    ]



    result = engine.generate_layout(
        spaces
    )


    print(
        result
    )


    assert (
        result["strategy"]
        ==
        "courtyard_centered"
    )


    assert (
        result["spaces"][0]
        ["layout_role"]
        ==
        "central_open_space"
    )


    assert (
        result["spaces"][1]
        ["layout_role"]
        ==
        "courtyard_adjacent"
    )