# ==========================================================
# PLANNER AGENT DECISION ADAPTER PROGRAM AWARE V2
# PROGRAM AWARE DESIGN DECISION LAYER
# ==========================================================


class PlannerAgentDecisionAdapterProgramAwareV2:


    VERSION = "2.0"



    def __init__(self):


        print(
            "🔄 PlannerAgent Decision Adapter Program Aware v2.0 ACTIVE"
        )



    # ======================================================
    # BUILD DESIGN DECISION
    # ======================================================


    def adapt(
        self,
        planner_context
    ):


        planner_input = (
            planner_context.get(
                "planner_input",
                {}
            )
        )


        target_program = (
            planner_input.get(
                "target_program"
            )
        )


        program_category = (
            planner_input.get(
                "program_category"
            )
        )


        requirements = (
            planner_input.get(
                "requirements",
                []
            )
        )


        building_type = (
            planner_input.get(
                "building_type"
            )
        )


        strategy = (
            planner_input.get(
                "architectural_strategy"
            )
        )



        decision = {


            "type":

                "adaptive_reuse_architectural_plan",


            "building_type":

                building_type,


            "action":

                "modify_existing_layout_for_program",


            "preserve":

                "existing_shell",


            "architectural_strategy":

                strategy,


            "target_program":

                target_program,


            "program_category":
                program_category,


            "requirements":
                requirements,


            "next_stage":

                "bim_modification_planning",


            "confidence":

                planner_input.get(
                    "confidence",
                    0
                )

        }



        return {


            "engine":

                "PLANNER_AGENT_DECISION_ADAPTER_PROGRAM_AWARE_V2",


            "version":

                self.VERSION,


            "decision":

                decision,


            "source_planner_input":

                planner_context,


            "decision_ready":

                True

        }