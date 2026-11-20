# ==========================================================
# PLANNER CONTEXT INJECTION V1
# ARCHITECTOS IFC → PLANNER INPUT
# ==========================================================


class PlannerContextInjectionV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🔗 Planner Context Injection v1.0 ACTIVE"
        )



    # ======================================================
    # BUILD PLANNER DECISION INPUT
    # ======================================================


    def inject(
        self,
        planner_bridge_result
    ):


        planner_context = (
            planner_bridge_result.get(
                "planner_context"
            )
        )


        decision_input = {


            "context_source":

                "IFC",



            "context":

                planner_context,



            "analysis_type":

                planner_bridge_result.get(
                    "intent"
                ),



            "planner_ready":

                planner_bridge_result.get(
                    "ready",
                    False
                )

        }



        return decision_input