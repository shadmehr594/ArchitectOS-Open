# ==========================================================
# ARCHITECTURAL INTENT BRIDGE PROGRAM AWARE V1
# PROGRAM AWARE ARCHITECTURAL INTENT LAYER
# ==========================================================


class ArchitecturalIntentBridgeProgramAwareV1:


    VERSION = "1.0"



    def __init__(self):


        print(
            "🔗 Architectural Intent Bridge Program Aware v1.0 ACTIVE"
        )



    # ======================================================
    # BUILD ARCHITECTURAL INTENT
    # ======================================================


    def build_intent(
        self,
        decision_context
    ):


        decision = (
            decision_context.get(
                "decision",
                {}
            )
        )


        proposal = (
            decision.get(
                "proposal"
            )
        )


        action = (
            decision.get(
                "action"
            )
        )


        target_program = (
            decision.get(
                "target_program"
            )
        )


        program_category = (
            decision.get(
                "program_category"
            )
        )


        requirements = (
            decision.get(
                "requirements",
                []
            )
        )



        if target_program:


            intent_type = (

                "existing_building_program_transformation"

            )


            architectural_goal = (

                "preserve_and_adapt_existing_shell"

            )


            architectural_action = (

                "adaptive_reuse"

            )


        else:


            intent_type = (

                "existing_building_evaluation"

            )


            architectural_goal = (

                "preserve_existing_shell"

            )


            architectural_action = (

                action

            )



        return {


            "engine":

                "ARCHITECTURAL_INTENT_BRIDGE_PROGRAM_AWARE_V1",


            "version":

                self.VERSION,


            "intent":

            {


                "intent_type":

                    intent_type,


                "architectural_goal":

                    architectural_goal,


                "architectural_action":

                    architectural_action,


                "selected_proposal":

                    proposal,


                "target_program":

                    target_program,


                "program_category":
                    program_category,


                "requirements":
                    requirements,


                "confidence":

                    decision.get(

                        "confidence",

                        0

                    )

            },


            "source_decision":

                decision_context,


            "intent_ready":

                True

        }