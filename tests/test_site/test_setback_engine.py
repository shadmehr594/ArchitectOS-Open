"""
ArchitectOS Setback Engine Test

Tests:
- Site boundary input
- Neighbor conditions
- Setback calculation
- Buildable zone generation
"""


from core.site.setback_engine import SetbackEngine



def test_setback_analysis():


    engine = SetbackEngine()


    site = {

        "boundary":

        [

            [0, 0],

            [20, 0],

            [20, 30],

            [0, 30]

        ]

    }


    neighbors = {


        "north":

        {

            "exists": False,

            "neighbor_type": None,

            "shared_wall": False,

            "road": False,

            "access": False

        },


        "south":

        {

            "exists": False,

            "neighbor_type": None,

            "shared_wall": False,

            "road": True,

            "access": True

        },


        "east":

        {

            "exists": True,

            "neighbor_type": "building",

            "shared_wall": True,

            "light_allowed": False,

            "road": False,

            "access": False

        },


        "west":

        {

            "exists": True,

            "neighbor_type": "building",

            "shared_wall": True,

            "light_allowed": False,

            "road": False,

            "access": False

        }

    }



    result = engine.analyze(

        site,

        neighbors

    )


    print(

        "\n========== RESULT =========="

    )


    print(

        result

    )


    assert result["buildable_area"] > 0


    assert result["setbacks"]["east"] == 0


    assert result["setbacks"]["west"] == 0


    print(

        "\n✅ Setback Engine TEST PASSED"

    )



if __name__ == "__main__":

    test_setback_analysis()