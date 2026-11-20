"""
ArchitectOS Spatial Floor Layout Engine Test v1.0
"""


from core.spatial.spatial_floor_layout_engine import (
    SpatialFloorLayoutEngine
)



def find_layout_item(
    layout,
    item_type
):


    for item in layout:

        if item.get(
            "type"
        ) == item_type:

            return item


    return None



def test_spatial_floor_layout_engine():


    engine = SpatialFloorLayoutEngine()



    floor = {


        "level":
            "F1",


        "type":
            "residential",


        "units":
            4

    }



    result = engine.generate(

        floor

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



    assert result.get(
        "type"
    ) == "residential"



    layout = result.get(
        "layout",
        []
    )



    assert len(
        layout
    ) == 7



    core = find_layout_item(
        layout,
        "core"
    )


    assert core is not None


    assert core.get(
        "position"
    ) == "center"



    lightwell = find_layout_item(
        layout,
        "lightwell"
    )


    assert lightwell is not None



    units = [

        item

        for item in layout

        if item.get(
            "type"
        ) == "unit"

    ]



    assert len(
        units
    ) == 4



    for unit in units:


        assert unit.get(
            "access"
        ) == "corridor"


        assert unit.get(
            "lightwell_access"
        ) is True



    corridor = find_layout_item(
        layout,
        "corridor"
    )


    assert corridor is not None


    assert corridor.get(
        "position"
    ) == "central"



    print(
        "\n✅ SPATIAL FLOOR LAYOUT ENGINE TEST PASSED"
    )



if __name__ == "__main__":

    test_spatial_floor_layout_engine()