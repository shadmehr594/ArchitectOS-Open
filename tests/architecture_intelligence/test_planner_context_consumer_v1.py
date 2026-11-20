from core.architecture.planner.planner_context_consumer_v1 import (
    PlannerContextConsumerV1
)



def test_planner_context_consumer_v1():


    print(
        "\n====== PLANNER CONTEXT CONSUMER V1 ======"
    )


    consumer = PlannerContextConsumerV1()



    injected_context = {


        "context_source":
            "IFC",


        "analysis_type":
            "existing_building_analysis",


        "planner_ready":
            True,


        "context":
        {

            "context_type":
                "architectural_existing_model",


            "building_state":
            {

                "floors":
                    3,


                "walls":
                    38,


                "doors":
                    17,


                "windows":
                    20,


                "openings":
                    37

            },


            "architectural_quality":
            {

                "score":
                    100,


                "status":
                    "healthy"

            },


            "planner_ready":
                True

        }

    }



    result = consumer.consume(
        injected_context
    )



    print(
        "\n====== PLANNER REQUEST RESULT ======"
    )


    print(
        result
    )



    assert (
        result["source"]
        ==
        "IFC"
    )


    assert (
        result["intent"]
        ==
        "existing_building_analysis"
    )


    assert (
        result["ready"]
        ==
        True
    )


    assert (
        result["planner_request"]["building_type"]
        ==
        "existing_building"
    )


    assert (
        result["planner_request"]["floors"]
        ==
        3
    )


    assert (
        result["planner_request"]["walls"]
        ==
        38
    )


    assert (
        result["planner_request"]["openings"]
        ==
        37
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_planner_context_consumer_v1()