# ==========================================================
# ARCHITECTURAL DECISION ENGINE PROGRAM AWARE V1
# PROGRAM AWARE ARCHITECTURAL DECISION LAYER
# ==========================================================


class ArchitecturalDecisionEngineProgramAwareV1:


    VERSION = "1.0"



    def __init__(self):


        print(
            "🧠 Architectural Decision Engine Program Aware v1.0 ACTIVE"
        )



    # ======================================================
    # BUILD ARCHITECTURAL DECISION
    # ======================================================


    def decide(
        self,
        decision_context
    ):


        target_program = (
            decision_context.get(
                "target_program"
            )
        )



        program_category = (
            decision_context.get(
                "program_category"
            )
        )



        requirements = (
            decision_context.get(
                "requirements",
                []
            )
        )



        decisions = []



        if target_program:


            decisions.append(

                "preserve_existing_shell"

            )


            decisions.append(

                "adapt_existing_layout"

            )


            decisions.append(

                f"validate_{target_program}_requirements"

            )



            decision_type = (

                "existing_building_program_transformation"

            )



        else:


            decisions.append(

                "evaluate_existing_building"

            )


            decision_type = (

                "existing_building_evaluation"

            )



        return {


            "engine":

                "ARCHITECTURAL_DECISION_ENGINE_PROGRAM_AWARE_V1",


            "version":

                self.VERSION,


            "decision":

            {


                "decision_type":

                    decision_type,


                "target_program":

                    target_program,


                "program_category":

                    program_category,


                "decisions":

                    decisions,


                "requirements":

                    requirements,


                "confidence":

                    0.92

            },


            "source_context":

                decision_context,


            "decision_ready":

                True

        }