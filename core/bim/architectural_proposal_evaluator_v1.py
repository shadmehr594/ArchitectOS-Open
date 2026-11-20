# ==========================================================
# ARCHITECTURAL PROPOSAL EVALUATOR V1
# ARCHITECTOS ARCHITECTURAL INTELLIGENCE
# ==========================================================


class ArchitecturalProposalEvaluatorV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 Architectural Proposal Evaluator v1.0 ACTIVE"
        )



    # ======================================================
    # EVALUATE PROPOSALS
    # ======================================================


    def evaluate(
        self,
        proposal_context
    ):


        changes = (
            proposal_context.get(
                "changes",
                []
            )
        )


        evaluations = []



        for proposal in changes:


            proposal_type = proposal.get(
                "type"
            )


            score = 50

            priority = "medium"



            # ==========================================
            # PRESERVATION
            # ==========================================


            if (
                proposal_type
                ==
                "architectural_preservation"
            ):

                score = 95

                priority = "high"



            # ==========================================
            # SPACE MODIFICATION
            # ==========================================


            elif (
                proposal_type
                ==
                "space_modification_proposal"
            ):

                score = 80

                priority = "medium"



            # ==========================================
            # OPENING OPTIMIZATION
            # ==========================================


            elif (
                proposal_type
                ==
                "opening_optimization_proposal"
            ):

                score = 75

                priority = "medium"



            evaluations.append(

                {

                    "proposal":
                        proposal_type,

                    "target":
                        proposal.get(
                            "target"
                        ),

                    "score":
                        score,

                    "priority":
                        priority

                }

            )



        return {


            "engine":
                "ARCHITECTURAL_PROPOSAL_EVALUATOR_V1",


            "version":
                self.VERSION,


            "evaluation_type":
                "architectural_proposal_quality_evaluation",


            "evaluations":
                evaluations,


            "source_proposal":
                proposal_context,


            "planner_ready":
                len(evaluations) > 0

        }