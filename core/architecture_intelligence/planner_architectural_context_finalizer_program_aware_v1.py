# ==========================================================
# PLANNER ARCHITECTURAL CONTEXT FINALIZER PROGRAM AWARE V1
# PROGRAM AWARE PLANNER CONTEXT LAYER
# ==========================================================


class PlannerArchitecturalContextFinalizerProgramAwareV1:


    VERSION = "1.0"



    def __init__(self):


        print(
            "🧠 Planner Architectural Context Finalizer Program Aware v1.0 ACTIVE"
        )



    # ======================================================
    # FINALIZE PLANNER CONTEXT
    # ======================================================


    def finalize(
        self,
        intent_context
    ):


        intent = (
            intent_context.get(
                "intent",
                {}
            )
        )


        target_program = (
            intent.get(
                "target_program"
            )
        )


        program_category = (
            intent.get(
                "program_category"
            )
        )


        requirements = (
            intent.get(
                "requirements",
                []
            )
        )


        architectural_goal = (
            intent.get(
                "architectural_goal"
            )
        )


        architectural_action = (
            intent.get(
                "architectural_action"
            )
        )



        planner_context = {


            "building_type":

                "existing_building",


            "planning_goal":

                "adaptive_reuse_transformation",


            "architectural_strategy":

                architectural_goal,


            "architectural_action":

                architectural_action,


            "target_program":

                target_program,


            "program_category":
                program_category,


            "requirements":
                requirements,


            "program_transformation":

                True,


            "confidence":

                intent.get(

                    "confidence",

                    0

                )

        }



        return {


            "engine":

                "PLANNER_ARCHITECTURAL_CONTEXT_FINALIZER_PROGRAM_AWARE_V1",


            "version":

                self.VERSION,


            "planner_context":

                planner_context,


            "source_intent":

                intent_context,


            "ready":

                True

        }