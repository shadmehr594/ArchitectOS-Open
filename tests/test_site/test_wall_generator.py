"""
ArchitectOS Wall Generator Test v1.0
"""


from core.geometry.wall_generator import (
    WallGenerator
)



def test_wall_generator():


    engine = WallGenerator()



    geometry = {


        "rooms":[


            {


                "type":
                    "living",


                "polygon":[

                    [0,0],

                    [4,0],

                    [4,5],

                    [0,5]

                ]

            },


            {


                "type":
                    "bedroom",


                "polygon":[

                    [4,0],

                    [8,0],

                    [8,5],

                    [4,5]

                ]

            }

        ]

    }



    result = engine.generate(

        geometry

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    walls = result.get(
        "walls",
        []
    )



    assert len(
        walls
    ) == 7



    interior_found = False

    exterior_found = False



    for wall in walls:


        if wall.get(
            "type"
        ) == "interior":


            interior_found = True



            assert wall.get(
                "adjacent_rooms"
            ) == [

                "living",

                "bedroom"

            ]



        if wall.get(
            "type"
        ) == "exterior":


            exterior_found = True



        assert wall.get(
            "thickness"
        ) == 0.2



    assert interior_found

    assert exterior_found



    print(
        "\n✅ WALL GENERATOR TEST PASSED"
    )



if __name__ == "__main__":

    test_wall_generator()