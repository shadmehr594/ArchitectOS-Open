"""
ArchitectOS Site Design Engine Test v1.0
"""


from core.site.site_design_engine import SiteDesignEngine



def test_site_design():


    engine = SiteDesignEngine()



    site = {


        "area": 600

    }



    analysis = {


        "access":

        {

            "side": "south"

        },


        "neighbors":

        {

            "north":

            {

                "exists": False

            },


            "south":

            {

                "exists": False

            },


            "east":

            {

                "exists": True

            },


            "west":

            {

                "exists": True

            }

        },


        "courtyard":

        {

            "side": "north",

            "area": 12

        }

    }



    building_form = {


        "placement": "north",


        "footprint":

        {

            "area": 360,

            "coverage": 60

        }

    }



    separation = {


        "separation_joints":

        {

            "east":

            {

                "joint": 0.2

            },


            "west":

            {

                "joint": 0.2

            }

        }

    }



    result = engine.generate(

        site,

        analysis,

        building_form,

        separation

    )



    print(

        "\n========== RESULT =========="

    )


    print(

        result

    )



    # -----------------------------
    # BUILDING CHECK
    # -----------------------------

    assert result.get(

        "building",

        {}

    ).get(

        "placement"

    ) == "north"



    # -----------------------------
    # COURTYARD CHECK
    # -----------------------------

    assert result.get(

        "open_spaces",

        {}

    ).get(

        "courtyard",

        {}

    ).get(

        "side"

    ) == "north"



    # -----------------------------
    # FACADE CHECK
    # -----------------------------

    facades = result.get(

        "facades",

        {}

    )


    assert facades.get(

        "north"

    ) == "courtyard"



    assert facades.get(

        "south"

    ) == "street"



    assert facades.get(

        "east"

    ) == "neighbor"



    assert facades.get(

        "west"

    ) == "neighbor"



    print(

        "\n✅ Site Design Engine TEST PASSED"

    )



if __name__ == "__main__":

    test_site_design()