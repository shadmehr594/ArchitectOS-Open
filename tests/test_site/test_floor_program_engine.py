"""
ArchitectOS Floor Program Engine Test v1.0
"""


from core.building.floor_program_engine import (
    FloorProgramEngine
)



def find_space(
    spaces,
    space_type
):


    for space in spaces:

        if space.get(
            "type"
        ) == space_type:

            return True


    return False



def test_floor_program_engine():


    engine = FloorProgramEngine()



    # ==================================================
    # PARKING TEST
    # ==================================================

    parking = engine.generate(

        {

            "level":
                "B1",

            "type":
                "parking"

        }

    )


    print(
        "\n========== PARKING =========="
    )


    print(
        parking
    )


    parking_spaces = parking.get(
        "spaces",
        []
    )


    assert find_space(
        parking_spaces,
        "parking_area"
    )


    assert find_space(
        parking_spaces,
        "ramp"
    )


    assert find_space(
        parking_spaces,
        "caretaker"
    )



    # ==================================================
    # COMMERCIAL TEST
    # ==================================================

    commercial = engine.generate(

        {

            "level":
                "G",

            "type":
                "commercial"

        }

    )


    print(
        "\n========== COMMERCIAL =========="
    )


    print(
        commercial
    )


    commercial_spaces = commercial.get(
        "spaces",
        []
    )


    assert find_space(
        commercial_spaces,
        "shop"
    )


    assert find_space(
        commercial_spaces,
        "mezzanine"
    )



    # ==================================================
    # RESIDENTIAL TEST
    # ==================================================

    residential = engine.generate(

        {

            "level":
                "F1",

            "type":
                "residential",

            "units":
                4

        }

    )


    print(
        "\n========== RESIDENTIAL =========="
    )


    print(
        residential
    )


    residential_spaces = residential.get(
        "spaces",
        []
    )


    assert find_space(
        residential_spaces,
        "corridor"
    )


    assert find_space(
        residential_spaces,
        "lightwell"
    )


    assert find_space(
        residential_spaces,
        "ducts"
    )


    unit_cluster = None


    for space in residential_spaces:


        if space.get(
            "type"
        ) == "unit_cluster":

            unit_cluster = space



    assert unit_cluster is not None


    assert unit_cluster.get(
        "count"
    ) == 4



    # ==================================================
    # DUPLEX TEST
    # ==================================================

    duplex = engine.generate(

        {

            "level":
                "F3",

            "type":
                "duplex",

            "units":
                2

        }

    )


    print(
        "\n========== DUPLEX =========="
    )


    print(
        duplex
    )


    assert find_space(

        duplex.get(
            "spaces",
            []
        ),

        "internal_stair"

    )



    print(
        "\n✅ FLOOR PROGRAM ENGINE TEST PASSED"
    )



if __name__ == "__main__":

    test_floor_program_engine()