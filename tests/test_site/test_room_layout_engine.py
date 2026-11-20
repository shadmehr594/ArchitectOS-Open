from core.space.room_layout_engine import (
    RoomLayoutEngine
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



def test_room_layout_engine():


    engine = RoomLayoutEngine()



    # ------------------------------
    # RESIDENTIAL TEST
    # ------------------------------

    room_program = {

        "type":
            "residential",

        "rooms":[

            {
                "type":
                    "living"
            },

            {
                "type":
                    "master_bedroom"
            },

            {
                "type":
                    "kitchen_clean"
            },

            {
                "type":
                    "kitchen_dirty"
            },

            {
                "type":
                    "bathroom"
            }

        ]

    }


    result = engine.generate(

        room_program,

        {
            "id":
                "unit_1"
        }

    )


    print(
        "\n========== RESIDENTIAL =========="
    )

    print(
        result
    )



    assert has_room(
        result["rooms"],
        "living"
    )


    assert has_room(
        result["rooms"],
        "master_bedroom"
    )


    assert has_room(
        result["rooms"],
        "bathroom"
    )



    # ------------------------------
    # ROOF TEST
    # ------------------------------

    roof_program = {


        "type":
            "roof",


        "rooms":[

            {
                "type":
                    "stair_headroom"
            },

            {
                "type":
                    "elevator_room"
            },

            {
                "type":
                    "parapet"
            }

        ]

    }



    roof_result = engine.generate(

        roof_program,

        {
            "id":
                "roof"
        }

    )


    print(
        "\n========== ROOF =========="
    )


    print(
        roof_result
    )


    assert has_room(
        roof_result["rooms"],
        "stair_headroom"
    )


    assert has_room(
        roof_result["rooms"],
        "elevator_room"
    )


    assert has_room(
        roof_result["rooms"],
        "parapet"
    )


    print(
        "\n✅ ROOM LAYOUT ENGINE TEST PASSED"
    )



if __name__ == "__main__":

    test_room_layout_engine()