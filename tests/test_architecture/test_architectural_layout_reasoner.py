from core.architecture.architectural_layout_reasoner import (
    ArchitecturalLayoutReasoner
)



def test_architectural_layout_reasoner():


    engine = ArchitecturalLayoutReasoner()



    spaces = [

        {

            "id":

            "shop_001",

            "type":

            "commercial"

        },


        {

            "id":

            "storage_001",

            "type":

            "storage"

        },


        {

            "id":

            "courtyard_001",

            "type":

            "courtyard"

        }

    ]



    result = engine.reason(
        spaces
    )


    print(result)



    assert len(result) == 3


    assert (

        "place_near_public_access"

        in

        result[0]["rules"]

    )


    assert (

        "place_away_from_public_flow"

        in

        result[1]["rules"]

    )


    assert (

        "maximize_daylight_connection"

        in

        result[2]["rules"]

    )