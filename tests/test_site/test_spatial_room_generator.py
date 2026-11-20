"""
ArchitectOS Spatial Room Generator Test v1.1
"""


from core.spatial.spatial_room_generator import SpatialRoomGenerator



def test_spatial_room_generator():


    engine = SpatialRoomGenerator()



    result = engine.generate(

        units=4,

        bedrooms=2,

        lightwell=True,

        separate_duct=True

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    units = result.get(
        "units",
        []
    )


    assert len(
        units
    ) == 4



    for unit in units:


        rooms = unit.get(
            "rooms",
            []
        )


        assert len(
            rooms
        ) == 5



        bedroom_count = 0


        for room in rooms:


            if room["type"] == "bedroom":


                bedroom_count += 1


                assert room.get(
                    "light_source"
                ) == "lightwell"



            if room["type"] == "bathroom":


                assert room.get(
                    "ventilation"
                ) == "duct_bathroom"



            if room["type"] == "kitchen":


                assert room.get(
                    "ventilation"
                ) == "duct_kitchen"



        assert bedroom_count == 2



    assert result["rules"]["window_facing"] is False



    print(
        "\n✅ SPATIAL ROOM GENERATOR TEST PASSED"
    )



if __name__ == "__main__":

    test_spatial_room_generator()