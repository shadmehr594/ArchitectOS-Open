# ==================================================
# ArchitectOS Architectural Design Action Executor V2
# Planner Decision -> Execution Action Graph
# Adaptive Reuse Program Aware Layer
# ==================================================


class ArchitecturalDesignActionExecutorV2:


    VERSION = "2.0"



    def __init__(self):

        print(
            f"🏛 Architectural Design Action Executor v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # EXECUTE DECISION
    # ==================================================

    def execute(
        self,
        decision
    ):


        actions = []


        if not isinstance(
            decision,
            dict
        ):

            return actions



        decision_type = decision.get(
            "type"
        )


        action = decision.get(
            "action"
        )



        # ==========================================
        # ADAPTIVE REUSE
        # ==========================================

        if (
            decision_type
            ==
            "adaptive_reuse_architectural_plan"
        ):


            preserve = decision.get(
                "preserve"
            )


            target_program = decision.get(
                "target_program"
            )


            next_stage = decision.get(
                "next_stage"
            )



            if preserve:

                actions.append(

                    {

                        "module":
                            "adaptive_reuse",


                        "action":
                            "preserve_existing_shell",


                        "parameters":
                            {

                                "preserve":
                                    preserve

                            }

                    }

                )



            if (
                action
                ==
                "modify_existing_layout_for_program"
            ):


                actions.append(

                    {

                        "module":
                            "adaptive_reuse",


                        "action":
                            "modify_existing_layout",


                        "parameters":
                            {

                                "target_program":
                                    target_program

                            }

                    }

                )



            if next_stage:

                actions.append(

                    {

                        "module":
                            "bim",


                        "action":
                            "create_modification_plan",


                        "parameters":
                            {

                                "stage":
                                    next_stage

                            }

                    }

                )



        return actions