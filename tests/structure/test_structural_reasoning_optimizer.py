"""
ArchitectOS Structural Reasoning Optimizer Test v1.0

Validates:

- architectural driven columns
- column reduction
- stair protection
- elevator protection
- corner based placement
- adaptive structural reasoning
"""


from core.structure.structural_column_optimizer import (
    StructuralColumnOptimizer
)



def test_structural_reasoning_optimizer():


    optimizer = StructuralColumnOptimizer()



    architectural_model = {


        "building": {

            "width": 12,

            "depth": 16

        },


        "spaces": [

            {

                "name":
                    "Living",

                "type":
                    "room",

                "bounds":
                    [
                        0,
                        0,
                        6,
                        8
                    ]

            },


            {

                "name":
                    "Stair_Core",

                "type":
                    "stairs",

                "bounds":
                    [
                        6,
                        4,
                        3,
                        4
                    ]

            },


            {

                "name":
                    "Elevator",

                "type":
                    "elevator",

                "bounds":
                    [
                        9,
                        4,
                        2,
                        2
                    ]

            }

        ]

    }



    raw_columns = [


        {
            "id":
                "C1",

            "x":
                0,

            "y":
                0,

            "reference":
                "corner"

        },


        {
            "id":
                "C2",

            "x":
                6,

            "y":
                4,

            "reference":
                "corner"

        },


        {
            "id":
                "C3",

            "x":
                9,

            "y":
                4,

            "reference":
                "corner"

        },


        {
            "id":
                "C4",

            "x":
                12,

            "y":
                0,

            "reference":
                "corner"

        }

    ]



    result = optimizer.optimize(

        raw_columns,

        architectural_model

    )



    assert len(result) < len(raw_columns)



    for column in result:


        assert not (

            column["x"] >= 6

            and

            column["x"] <= 11

            and

            column["y"] >= 4

            and

            column["y"] <= 8

        )



    for column in result:

        assert column["reference"] == "corner"



    print(
        "STRUCTURAL REASONING OPTIMIZER TEST PASSED"
    )