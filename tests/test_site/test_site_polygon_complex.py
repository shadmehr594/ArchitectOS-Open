"""
ArchitectOS Site Polygon Engine v1.1 Complex Test
"""


from core.site.site_polygon_engine import SitePolygonEngine



def test_complex_site_polygon():


    engine = SitePolygonEngine()



    site = {

        "width":20,

        "depth":30

    }



    scenarios = [


        {

            "name":"north_west",

            "polygon":

            [

                [0,28.3],

                [7,28.3],

                [7,30],

                [0,30]

            ]

        },


        {

            "name":"north_east",

            "polygon":

            [

                [13,28.3],

                [20,28.3],

                [20,30],

                [13,30]

            ]

        },


        {

            "name":"east_north",

            "polygon":

            [

                [18.3,23],

                [20,23],

                [20,30],

                [18.3,30]

            ]

        },


        {

            "name":"west_south",

            "polygon":

            [

                [0,0],

                [1.7,0],

                [1.7,7],

                [0,7]

            ]

        }

    ]



    for scenario in scenarios:


        print(
            "\n========== SCENARIO =========="
        )


        print(
            scenario["name"]
        )


        courtyard = {

            "polygon":
                scenario["polygon"]

        }



        result = engine.generate(

            site,

            courtyard

        )



        print(
            result
        )



        assert result.get(

            "courtyard_polygon"

        ) == scenario["polygon"]



        assert len(

            result.get(

                "buildable_polygons",

                []

            )

        ) >= 1



    print(

        "\n✅ COMPLEX SITE POLYGON TEST PASSED"

    )





if __name__ == "__main__":

    test_complex_site_polygon()