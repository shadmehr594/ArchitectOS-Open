"""
ArchitectOS Site Polygon Engine Test
"""


from core.site.site_polygon_engine import SitePolygonEngine



def test_site_polygon():


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
        "courtyard_polygon"
    ) == courtyard["polygon"]



    print(
        "\n✅ SITE POLYGON ENGINE TEST PASSED"
    )



if __name__ == "__main__":

    test_site_polygon()