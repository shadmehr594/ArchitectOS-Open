# ==========================================================
# PLANNER AGENT PROGRAM AWARE CONTEXT CONSUMER V2
# PROGRAM AWARE PLANNER INPUT ADAPTER
# ==========================================================


class PlannerAgentProgramAwareContextConsumerV2:


    VERSION = "2.0"



    def __init__(self):


        print(
            "🧠 PlannerAgent Program Aware Context Consumer v2.0 ACTIVE"
        )



    # ======================================================
    # BUILD PLANNER INPUT
    # ======================================================


    def consume(
        self,
        context
    ):


        planner_context = (
            context.get(
                "planner_context",
                {}
            )
        )


        planner_input = {


            "task":

                "adaptive_reuse_design_planning",


            "building_type":

                planner_context.get(
                    "building_type"
                ),


            "planning_goal":

                planner_context.get(
                    "planning_goal"
                ),


            "target_program":

                planner_context.get(
                    "target_program"
                ),


                "program_category":
                planner_context.get(
                    "program_category"
                ),


            "requirements":
                planner_context.get(
                    "requirements",
                    []
                ),


            "architectural_strategy":

                planner_context.get(
                    "architectural_strategy"
                ),


            "architectural_action":

                planner_context.get(
                    "architectural_action"
                ),


            "confidence":

                planner_context.get(
                    "confidence"
                )

        }



        return {


            "engine":

                "PLANNER_AGENT_PROGRAM_AWARE_CONTEXT_CONSUMER_V2",


            "version":

                self.VERSION,


            "planner_input":

                planner_input,


            "source_context":

                context,


            "planner_ready":

                True

        }