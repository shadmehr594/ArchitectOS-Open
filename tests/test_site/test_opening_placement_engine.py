"""
ArchitectOS Opening Placement Engine Test v1.0
"""


from core.geometry.opening_placement_engine import (
    OpeningPlacementEngine
)



def test_opening_placement_engine():


    engine = OpeningPlacementEngine()



    geometry = {


        "rooms":[


            {

                "type":
                    "living"

            },


            {

                "type":
                    "bedroom"

            },


            {

                "type":
                    "bathroom"

            }

        ]

    }



    result = engine.generate(

        geometry

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    openings = result.get(
        "openings",
        []
    )



    assert len(
        openings
    ) == 6



    living_window = False

    bedroom_window = False

    entrance_door = False

    corridor_door = False

    vent_found = False



    for opening in openings:


        if (

            opening.get("type")
            ==
            "window"

        ):


            if opening.get(
                "room"
            ) == "living":


                living_window = True


                assert opening.get(
                    "source"
                ) == "facade"



            if opening.get(
                "room"
            ) == "bedroom":


                bedroom_window = True


                assert opening.get(
                    "source"
                ) == "lightwell_or_facade"


                assert opening.get(
                    "rule"
                ) == "no_direct_opposite"



        if (

            opening.get("type")
            ==
            "door"

        ):


            if opening.get(
                "room"
            ) == "living":


                entrance_door = True


                assert opening.get(
                    "access"
                ) == "entrance"



            if opening.get(
                "room"
            ) in [

                "bedroom",

                "bathroom"

            ]:


                corridor_door = True


                assert opening.get(
                    "access"
                ) == "corridor"


        if (

            opening.get("type")
            ==
            "vent"

        ):


            if opening.get(
                "room"
            ) == "bathroom":


                vent_found = True


                assert opening.get(
                    "source"
                ) == "bathroom_duct"



    assert living_window

    assert bedroom_window

    assert entrance_door

    assert corridor_door

    assert vent_found



    print(
        "\n✅ OPENING PLACEMENT ENGINE TEST PASSED"
    )



if __name__ == "__main__":

    test_opening_placement_engine()