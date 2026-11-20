# ==========================================================
# BRAIN PLANNER CONTEXT BRIDGE V1
# ARCHITECTOS PLANNER -> BRAIN CONNECTOR
# ==========================================================


class BrainPlannerContextBridgeV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🔗 Brain Planner Context Bridge v1.0 ACTIVE"
        )



    # ======================================================
    # BRIDGE PLANNER CONTEXT
    # ======================================================


    def bridge(
        self,
        planner_context_result
    ):


        planner_context = (
            planner_context_result.get(
                "planner_context",
                {}
            )
        )



        brain_context = {


            "building_type":

                planner_context.get(
                    "building_type"
                ),


            "architectural_intent":

                planner_context.get(
                    "intent"
                ),


            "architectural_goal":

                planner_context.get(
                    "goal"
                ),


            "target":

                planner_context.get(
                    "target"
                ),


            "confidence":

                planner_context.get(
                    "confidence",
                    0
                ),


            "planner_ready":

                True

        }



        return {


            "engine":

                "BRAIN_PLANNER_CONTEXT_BRIDGE_V1",


            "version":

                self.VERSION,


            "brain_context":

                brain_context,


            "source_planner_context":

                planner_context_result,


            "ready":

                True

        }