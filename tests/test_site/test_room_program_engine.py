"""
ArchitectOS Room Program Engine Test v1.0
"""


from core.space.room_program_engine import (
    RoomProgramEngine
)



def has_room(
    rooms,
    room_type
):


    for room in rooms:

        if room.get(
            "type"
        ) == room_type:

            return True


    return False



def test_room_program_engine():


    engine = RoomProgramEngine()



    # ==================================================
    # RESIDENTIAL TEST
    # ==================================================

    residential = engine.generate(

        {

            "type":
                "residential",

            "bedrooms":
                2

        }

    )



    print(
        "\n========== RESIDENTIAL =========="
    )


    print(
        residential
    )



    rooms = residential.get(
        "rooms",
        []
    )



    assert has_room(
        rooms,
        "living"
    )


    assert has_room(
        rooms,
        "master_bedroom"
    )


    assert has_room(
        rooms,
        "bedroom"
    )


    assert has_room(
        rooms,
        "kitchen_clean"
    )


    assert has_room(
        rooms,
        "kitchen_dirty"
    )


    assert has_room(
        rooms,
        "laundry"
    )


    assert has_room(
        rooms,
        "bathroom"
    )


    assert has_room(
        rooms,
        "wc"
    )


    assert has_room(
        rooms,
        "storage"
    )


    assert has_room(
        rooms,
        "closet"
    )



    # ==================================================
    # PENTHOUSE TEST
    # ==================================================

    penthouse = engine.generate(

        {

            "type":
                "penthouse"

        }

    )



    print(
        "\n========== PENTHOUSE =========="
    )


    print(
        penthouse
    )



    penthouse_rooms = penthouse.get(
        "rooms",
        []
    )



    assert has_room(
        penthouse_rooms,
        "large_living"
    )


    assert has_room(
        penthouse_rooms,
        "master_bedroom"
    )


    assert has_room(
        penthouse_rooms,
        "master_bathroom"
    )


    assert has_room(
        penthouse_rooms,
        "walk_in_closet"
    )


    assert has_room(
        penthouse_rooms,
        "terrace"
    )


    assert has_room(
        penthouse_rooms,
        "roof_garden"
    )


    assert has_room(
        penthouse_rooms,
        "private_elevator_lobby"
    )



    print(
        "\n✅ ROOM PROGRAM ENGINE TEST PASSED"
    )



if __name__ == "__main__":

    test_room_program_engine()