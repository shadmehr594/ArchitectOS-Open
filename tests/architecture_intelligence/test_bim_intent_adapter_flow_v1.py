from core.bim.bim_intent_adapter import (
    BIMIntentAdapter
)


def test_bim_intent_adapter_flow_v1():

    print(
        "====== BIM INTENT ADAPTER FLOW TEST ======"
    )


    building_model = {

        "building": {

            "type":
                "villa",

            "levels": {

                "total":
                    2,

                "ground":
                    1

            }

        },


        "spatial": {

            "space_registry": [

                {
                    "id":
                        "living",

                    "status":
                        "planned"

                },

                {
                    "id":
                        "bedroom",

                    "status":
                        "planned"

                }

            ],


            "connections": [

                {
                    "from":
                        "living",

                    "to":
                        "garden",

                    "type":
                        "visual_connection"
                }

            ],


            "adjacency": [

                {
                    "from":
                        "bedroom",

                    "to":
                        "bathroom",

                    "type":
                        "adjacent"
                }

            ]

        }

    }



    adapter = BIMIntentAdapter()


    result = adapter.convert(
        building_model
    )


    print()

    print(
        "====== BIM INTENT OUTPUT ======"
    )

    print(
        result
    )



    assert result is not None


    assert "spaces" in result


    assert result["spaces"][0]["ifc_type"] == "IfcSpace"



    assert (
        result["relationships"]
        ["connections"]
    )



    print()

    print(
        "====== TEST PASSED ======"
    )