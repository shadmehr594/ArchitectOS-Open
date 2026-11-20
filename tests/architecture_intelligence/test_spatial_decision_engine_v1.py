from core.spatial.spatial_decision_engine_v1 import (
    SpatialDecisionEngineV1
)



def test_spatial_decision_engine_v1():


    print(
        "====== SPATIAL DECISION ENGINE TEST ======"
    )


    engine = SpatialDecisionEngineV1()



    spatial_intent = {


        "spaces":

        {


            "living":

            {

                "role":
                    "public_space",

                "privacy":
                    "low"

            },


            "bedroom":

            {

                "role":
                    "private_space",

                "privacy":
                    "high"

            },


            "garden":

            {

                "role":
                    "external_space",

                "privacy":
                    "medium"

            },


            "bathroom":

            {

                "role":
                    "service_space",

                "privacy":
                    "medium"

            }

        }

    }



    result = engine.decide(
        spatial_intent
    )



    print(
        result
    )



    assert result["ready"] is True



    assert (
        result["decisions"]["living"]["preferred_zone"]
        ==
        "front"
    )


    assert (
        result["decisions"]["bedroom"]["preferred_zone"]
        ==
        "rear"
    )


    assert (
        result["decisions"]["garden"]["preferred_zone"]
        ==
        "external"
    )


    assert (
        result["decisions"]["bathroom"]["preferred_zone"]
        ==
        "service"
    )


    print(
        "====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_spatial_decision_engine_v1()