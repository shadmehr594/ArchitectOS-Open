# ==========================================================
# PLANNER CONTEXT CONSUMER V1
# ARCHITECTOS ARCHITECTURAL INTELLIGENCE
# ==========================================================


class PlannerContextConsumerV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 Planner Context Consumer v1.0 ACTIVE"
        )



    # ======================================================
    # BUILD PLANNER REQUEST
    # ======================================================


    def consume(
        self,
        planner_context
    ):


        building_state = (
            planner_context
            .get(
                "context",
                {}
            )
            .get(
                "building_state",
                {}
            )
        )


        intent = (
            planner_context
            .get(
                "analysis_type",
                "existing_building_analysis"
            )
        )


        request = {


            "source":
                planner_context.get(
                    "context_source",
                    "UNKNOWN"
                ),


            "intent":
                intent,


            "planner_request":
            {


                "building_type":
                    "existing_building",


                "floors":
                    building_state.get(
                        "floors",
                        0
                    ),


                "walls":
                    building_state.get(
                        "walls",
                        0
                    ),


                "doors":
                    building_state.get(
                        "doors",
                        0
                    ),


                "windows":
                    building_state.get(
                        "windows",
                        0
                    ),


                "openings":
                    building_state.get(
                        "openings",
                        0
                    )

            },


            "ready":
                True

        }


        return request