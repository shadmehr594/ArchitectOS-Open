"""
ArchitectOS Lightwell Geometry Engine Test v1.0
"""


from core.site.lightwell_geometry_engine import LightwellGeometryEngine



def test_lightwell_geometry():


    engine = LightwellGeometryEngine()



    building_polygon = [

        [0,0],

        [20,0],

        [20,18],

        [0,18]

    ]



    lightwell = {

        "required":True,

        "count":1,

        "width":3,

        "depth":4,

        "position":"center"

    }



    result = engine.solve(

        building_polygon,

        lightwell

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    lightwells = result.get(
        "lightwells",
        []
    )



    assert len(
        lightwells
    ) == 1



    assert lightwells[0] == [

        [8.5,7.0],

        [11.5,7.0],

        [11.5,11.0],

        [8.5,11.0]

    ]



    print(
        "\n✅ LIGHTWELL GEOMETRY ENGINE TEST PASSED"
    )



if __name__ == "__main__":

    test_lightwell_geometry()