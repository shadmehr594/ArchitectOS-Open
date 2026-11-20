"""
ArchitectOS Site Polygon Engine v1.1 Test
"""


from core.site.site_polygon_engine import SitePolygonEngine



def test_site_polygon_v11():


    engine = SitePolygonEngine()



    site = {

        "width":20,

        "depth":30

    }



    courtyard = {

        "polygon":

        [

            [0,28.3],

            [7,28.3],

            [7,30],

            [0,30]

        ]

    }



    result = engine.generate(

        site,

        courtyard

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    assert result.get(
        "type"
    ) == "site_with_open_space"



    assert len(

        result.get(

            "buildable_polygons",

            []

        )

    ) >= 1



    assert result.get(
        "courtyard_polygon"
    ) == courtyard["polygon"]



    print(
        "\n✅ SITE POLYGON ENGINE v1.1 TEST PASSED"
    )



if __name__ == "__main__":

    test_site_polygon_v11()