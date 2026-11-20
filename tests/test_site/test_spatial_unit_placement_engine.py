"""
ArchitectOS Spatial Unit Placement Engine Test v1.0
"""


from core.spatial.spatial_unit_placement_engine import (
    SpatialUnitPlacementEngine
)



def test_spatial_unit_placement_engine():


    engine = SpatialUnitPlacementEngine()



    floor = {


        "level":
            "F1",


        "type":
            "residential"

    }



    result = engine.generate(

        floor,

        4

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    assert result.get(
        "level"
    ) == "F1"



    units = result.get(
        "units",
        []
    )



    assert len(
        units
    ) == 4



    # -----------------------------
    # UNIT 1 CHECK
    # -----------------------------

    unit_1 = units[0]



    assert unit_1.get(
        "id"
    ) == "unit_1"



    assert unit_1.get(
        "area"
    ) == 80



    assert unit_1.get(
        "polygon"
    ) == [

        [0,0],

        [8,0],

        [8,10],

        [0,10]

    ]



    assert "corridor" in unit_1.get(
        "adjacent"
    )


    assert "lightwell" in unit_1.get(
        "adjacent"
    )



    rooms = unit_1.get(
        "rooms",
        []
    )



    room_types = [

        room.get(
            "type"
        )

        for room in rooms

    ]



    assert "living" in room_types


    assert "bedroom" in room_types


    assert "kitchen" in room_types


    assert "bathroom" in room_types



    # -----------------------------
    # UNIT 4 CHECK
    # -----------------------------

    unit_4 = units[3]



    assert unit_4.get(
        "polygon"
    ) == [

        [24,0],

        [32,0],

        [32,10],

        [24,10]

    ]



    print(
        "\n✅ SPATIAL UNIT PLACEMENT ENGINE TEST PASSED"
    )



if __name__ == "__main__":

    test_spatial_unit_placement_engine()