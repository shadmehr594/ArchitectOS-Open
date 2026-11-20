"""
ArchitectOS Building Stack Generator Test v1.0
"""


from core.building.building_stack_generator import (
    BuildingStackGenerator
)



def test_building_stack_generator():


    engine = BuildingStackGenerator()



    building = {


        "site":{


            "width":
                20,


            "depth":
                30

        },


        "floors":[



            {


                "level":
                    "B1",


                "type":
                    "parking",


                "features":[

                    "ramp",

                    "caretaker"

                ]

            },



            {


                "level":
                    "G",


                "type":
                    "commercial",


                "features":[

                    "mezzanine"

                ]

            },



            {


                "level":
                    "F1",


                "type":
                    "residential",


                "units":
                    3

            },



            {


                "level":
                    "F2",


                "type":
                    "residential",


                "units":
                    4,


                "projection":{


                    "side":
                        "south",


                    "width":
                        8,


                    "depth":
                        1.5

                }

            },



            {


                "level":
                    "F3",


                "type":
                    "duplex",


                "units":
                    2

            }


        ]

    }



    result = engine.generate(

        building

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    assert result.get(
        "floor_count"
    ) == 5



    floors = result.get(
        "floors",
        []
    )



    assert floors[0]["level"] == "B1"


    assert floors[0]["type"] == "parking"



    assert floors[1]["type"] == "commercial"



    assert floors[2]["units"] == 3



    assert floors[3]["units"] == 4



    assert floors[3]["projection"]["side"] == "south"


    assert floors[3]["projection"]["width"] == 8


    assert floors[3]["projection"]["depth"] == 1.5



    assert floors[4]["type"] == "duplex"



    assert floors[4]["units"] == 2



    print(
        "\n✅ BUILDING STACK GENERATOR TEST PASSED"
    )



if __name__ == "__main__":

    test_building_stack_generator()