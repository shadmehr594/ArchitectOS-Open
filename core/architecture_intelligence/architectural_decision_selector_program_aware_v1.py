# ==========================================================
# ARCHITECTURAL DECISION SELECTOR PROGRAM AWARE V1
# PROGRAM AWARE DECISION SELECTION LAYER
# ==========================================================


class ArchitecturalDecisionSelectorProgramAwareV1:


    VERSION = "1.0"



    def __init__(self):


        print(
            "🧭 Architectural Decision Selector Program Aware v1.0 ACTIVE"
        )



    # ======================================================
    # SELECT BEST DECISION
    # ======================================================


    def select(
        self,
        evaluation_context
    ):


        evaluation = (
            evaluation_context.get(
                "evaluation",
                {}
            )
        )


        evaluations = (
            evaluation.get(
                "evaluations",
                []
            )
        )


        target_program = (
            evaluation.get(
                "target_program"
            )
        )


        program_category = (
            evaluation.get(
                "program_category"
            )
        )


        requirements = (
            evaluation.get(
                "requirements",
                []
            )
        )



        selected = None



        if evaluations:


            selected = max(

                evaluations,

                key=lambda item:
                    item.get(
                        "score",
                        0
                    )

            )



        return {


            "engine":

                "ARCHITECTURAL_DECISION_SELECTOR_PROGRAM_AWARE_V1",


            "version":

                self.VERSION,


            "decision":

            {


                "proposal":

                    selected.get(
                        "proposal"
                    )
                    if selected
                    else None,


                "action":

                    selected.get(
                        "action"
                    )
                    if selected
                    else None,


                "target_program":

                    target_program,


                "program_category":
                    program_category,


                "requirements":
                    requirements,


                "score":

                    selected.get(
                        "score"
                    )
                    if selected
                    else 0,


                "confidence":

                    round(

                        (
                            selected.get(
                                "score",
                                0
                            )
                            / 100
                        ),

                        2

                    )
                    if selected
                    else 0

            },


            "source_evaluation":

                evaluation_context,


            "decision_ready":

                True

        }