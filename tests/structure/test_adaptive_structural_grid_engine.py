"""
ArchitectOS Adaptive Structural Grid Engine Test v1.0

Validates:
- architectural driven grid
- corner based coordinates
- structural exclusion zones
- adaptive spacing
- variable floor heights
- vertical core protection
"""


from core.structure.structural_grid_engine import (
    StructuralGridEngine
)



def test_adaptive_structural_grid_generation():


    engine = StructuralGridEngine()



    architectural_model = {


        "building": {

            "width": 12,

            "depth": 16

        },


        "spaces": [

            {

                "name": "Living",

                "type": "room",

                "bounds": [
                    0,
                    0,
                    5,
                    6
                ]

            },


            {

                "name": "Stair_Core",

                "type": "stairs",

                "bounds": [
                    5,
                    5,
                    3,
                    4
                ]

            },


            {

                "name": "Elevator",

                "type": "elevator",

                "bounds": [
                    8,
                    5,
                    2,
                    2
                ]

            },


            {

                "name": "Duct",

                "type": "duct",

                "bounds": [
                    8,
                    8,
                    1,
                    1
                ]

            }

        ],


        "external_walls": [

            {

                "side":
                    "north"

            },

            {

                "side":
                    "south"

            }

        ]

    }



    vertical_section = {


        "levels": [

            {

                "name":
                    "F1",

                "height":
                    5.0

            },


            {

                "name":
                    "F2",

                "height":
                    3.2

            },


            {

                "name":
                    "F3",

                "height":
                    3.2

            }

        ],


        "vertical_extensions": [

            {

                "type":
                    "elevator_machine_room",

                "height":
                    1.0

            }

        ]

    }



    result = engine.build(

        architectural_model,

        vertical_section

    )



    assert "columns" in result

    assert "beams" in result


    assert len(
        result["columns"]
    ) > 0



    # -----------------------------
    # COLUMN MUST NOT ENTER CORE
    # -----------------------------

    for column in result["columns"]:


        assert column.get(
            "zone"
        ) not in [

            "stairs",

            "elevator",

            "duct"

        ]



    # -----------------------------
    # CORNER BASED PLACEMENT
    # -----------------------------

    assert result["columns"][0]["reference"] == "corner"



    # -----------------------------
    # VARIABLE GRID
    # -----------------------------

    assert result["grid_type"] == "adaptive"



    print(
        "ADAPTIVE STRUCTURAL GRID ENGINE TEST PASSED"
    )