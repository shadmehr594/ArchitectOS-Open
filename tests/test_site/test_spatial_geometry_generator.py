"""
ArchitectOS Spatial Geometry Generator Test v1.0
"""


from core.geometry.spatial_geometry_generator import (
    SpatialGeometryGenerator
)



def test_spatial_geometry_generator():


    engine = SpatialGeometryGenerator()



    room_layout = {


        "type":
            "residential",


        "rooms":[


            {

                "type":
                    "living"

            },


            {

                "type":
                    "bedroom"

            },


            {

                "type":
                    "bathroom"

            }

        ]

    }



    result = engine.generate(

        room_layout,

        {

            "id":
                "unit_1"

        }

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    assert result.get(
        "unit"
    ) == "unit_1"



    rooms = result.get(
        "rooms",
        []
    )



    assert len(
        rooms
    ) == 3



    # ------------------------------
    # LIVING
    # ------------------------------

    living = rooms[0]


    assert living.get(
        "type"
    ) == "living"



    assert living.get(
        "polygon"
    ) == [

        [0,0],

        [4,0],

        [4,5],

        [0,5]

    ]



    assert living.get(
        "area"
    ) == 20



    # ------------------------------
    # BEDROOM
    # ------------------------------

    bedroom = rooms[1]


    assert bedroom.get(
        "type"
    ) == "bedroom"



    assert bedroom.get(
        "polygon"
    ) == [

        [4,0],

        [8,0],

        [8,5],

        [4,5]

    ]



    # ------------------------------
    # BATHROOM
    # ------------------------------

    bathroom = rooms[2]


    assert bathroom.get(
        "type"
    ) == "bathroom"



    assert bathroom.get(
        "polygon"
    ) == [

        [8,0],

        [12,0],

        [12,5],

        [8,5]

    ]



    print(
        "\n✅ SPATIAL GEOMETRY GENERATOR TEST PASSED"
    )



if __name__ == "__main__":

    test_spatial_geometry_generator()