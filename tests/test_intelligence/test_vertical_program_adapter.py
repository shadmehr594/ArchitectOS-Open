from core.intelligence.vertical_program_adapter import (
    VerticalProgramAdapter
)



def test_vertical_program_adapter():


    adapter = VerticalProgramAdapter()



    commercial_program = {


        "level":
            "G",


        "type":
            "commercial",


        "spaces":

        [

            {
                "type":
                    "shop"
            }

        ]

    }



    result = adapter.adapt(

        commercial_program,

        {

            "vertical_systems":

            [

                {
                    "type":
                        "escalator"
                },

                {
                    "type":
                        "elevator"
                }

            ]

        }

    )



    print(result)



    spaces = [

        x["type"]

        for x in result["spaces"]

    ]


    assert "escalator_zone" in spaces

    assert "elevator_core" in spaces



    parking_program = {


        "level":
            "B1",

        "type":
            "parking",

        "spaces":[]

    }



    parking_result = adapter.adapt(

        parking_program,

        {

            "vertical_systems":

            [

                {
                    "type":
                        "car_lift"
                }

            ]

        }

    )


    print(parking_result)



    assert (

        "car_lift_zone"

        in

        [

            x["type"]

            for x in parking_result["spaces"]

        ]

    )


    print(
        "✅ VERTICAL PROGRAM ADAPTER TEST PASSED"
    )



if __name__ == "__main__":

    test_vertical_program_adapter()