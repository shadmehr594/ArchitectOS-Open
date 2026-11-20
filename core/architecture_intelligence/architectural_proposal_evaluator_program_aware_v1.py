# ==========================================================
# ARCHITECTURAL PROPOSAL EVALUATOR PROGRAM AWARE V1
# PROGRAM AWARE PROPOSAL QUALITY EVALUATION
# ==========================================================


class ArchitecturalProposalEvaluatorProgramAwareV1:


    VERSION = "1.0"



    def __init__(self):


        print(
            "🧠 Architectural Proposal Evaluator Program Aware v1.0 ACTIVE"
        )



    # ======================================================
    # EVALUATE PROPOSALS
    # ======================================================


    def evaluate(
        self,
        proposal_context
    ):


        proposal = (
            proposal_context.get(
                "proposal",
                {}
            )
        )


        target_program = (
            proposal.get(
                "target_program"
            )
        )


        program_category = (
            proposal.get(
                "program_category"
            )
        )


        requirements = (
            proposal.get(
                "requirements",
                []
            )
        )


        proposals = (
            proposal.get(
                "proposals",
                []
            )
        )


        evaluations = []



        for item in proposals:


            proposal_type = (
                item.get(
                    "type"
                )
            )



            score = 70



            if proposal_type == "architectural_shell_preservation":


                score = 95



            elif proposal_type == "space_reconfiguration":


                score = 85



            elif proposal_type == "program_validation":


                score = 90



            evaluations.append(

                {

                    "proposal":

                        proposal_type,


                    "action":

                        item.get(
                            "action"
                        ),


                    "target_program":

                        target_program,


                    "score":

                        score

                }

            )



        return {


            "engine":

                "ARCHITECTURAL_PROPOSAL_EVALUATOR_PROGRAM_AWARE_V1",


            "version":

                self.VERSION,


            "evaluation":

            {


                "evaluation_type":

                    "program_aware_architectural_proposal_evaluation",


                "target_program":

                    target_program,


                "program_category":
                    program_category,


                "requirements":
                    requirements,


                "evaluations":

                    evaluations

            },


            "source_proposal":

                proposal_context,


            "evaluation_ready":

                True

        }