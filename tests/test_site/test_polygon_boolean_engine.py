"""
ArchitectOS Polygon Boolean Engine Test v1.0
"""


from core.geometry.polygon_boolean_engine import PolygonBooleanEngine



def test_polygon_boolean_engine():


    engine = PolygonBooleanEngine()



    building_polygon = [

        [0,0],

        [20,0],

        [20,18],

        [0,18]

    ]



    lightwell_polygon = [

        [8.5,7],

        [11.5,7],

        [11.5,11],

        [8.5,11]

    ]



    result = engine.subtract(

        building_polygon,

        [

            lightwell_polygon

        ]

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    assert result.get(
        "outer_area"
    ) == 360



    assert result.get(
        "void_area"
    ) == 12



    assert result.get(
        "solid_area"
    ) == 348



    assert len(
        result.get(
            "voids"
        )
    ) == 1



    print(
        "\n✅ POLYGON BOOLEAN ENGINE TEST PASSED"
    )



if __name__ == "__main__":

    test_polygon_boolean_engine()