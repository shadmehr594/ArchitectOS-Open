"""
ArchitectOS Courtyard Engine v3 Direction Test
"""


from core.site.courtyard_engine import CourtyardEngine



def test_courtyard_directions():


    engine = CourtyardEngine()


    site = {

        "width": 20,

        "depth": 30

    }



    scenarios = [


        {

            "name": "north_west",

            "side": "north",

            "position": "west"

        },


        {

            "name": "north_east",

            "side": "north",

            "position": "east"

        },


        {

            "name": "south_west",

            "side": "south",

            "position": "west"

        },


        {

            "name": "east_north",

            "side": "east",

            "position": "north"

        },


        {

            "name": "west_south",

            "side": "west",

            "position": "south"

        }

    ]



    for item in scenarios:


        print(
            "\n========== SCENARIO =========="
        )


        print(
            item["name"]
        )



        requirement = {


            "enabled": True,


            "side":
                item["side"],


            "position":
                item["position"],


            "width": 7,


            "depth": 1.7


        }



        result = engine.generate(

            site,

            requirement

        )



        courtyard = result.get(

            "courtyard",

            {}

        )



        assert courtyard.get(

            "area"

        ) >= 11.5



        assert len(

            courtyard.get(

                "polygon",

                []

            )

        ) == 4



        print(

            "AREA:",

            courtyard["area"]

        )


        print(

            "POLYGON:",

            courtyard["polygon"]

        )



    print(

        "\n✅ ALL COURTYARD DIRECTION TESTS PASSED"

    )





if __name__ == "__main__":


    test_courtyard_directions()