# ==========================================================
# ARCHITECTURAL PROPOSAL GENERATOR PROGRAM AWARE V1
# PROGRAM AWARE ARCHITECTURAL PROPOSAL LAYER
# ==========================================================


class ArchitecturalProposalGeneratorProgramAwareV1:


    VERSION = "1.0"



    def __init__(self):


        print(
            "🏗 Architectural Proposal Generator Program Aware v1.0 ACTIVE"
        )



    # ======================================================
    # GENERATE PROPOSAL
    # ======================================================


    def generate(
        self,
        decision
    ):


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


        decisions = (
            decision.get(
                "decisions",
                []
            )
        )


        proposals = []



        if "preserve_existing_shell" in decisions:


            proposals.append(

                {

                    "type":

                        "architectural_shell_preservation",


                    "action":

                        "retain_existing_structure"

                }

            )



        if "adapt_existing_layout" in decisions:


            proposals.append(

                {

                    "type":

                        "space_reconfiguration",


                    "action":

                        f"create_{target_program}_layout"

                }

            )



        if target_program:


            proposals.append(

                {

                    "type":

                        "program_validation",


                    "action":

                        f"validate_{target_program}_requirements"

                }

            )



        return {


            "engine":

                "ARCHITECTURAL_PROPOSAL_GENERATOR_PROGRAM_AWARE_V1",


            "version":

                self.VERSION,


            "proposal":

            {


                "proposal_type":

                    "existing_building_program_transformation",


                "target_program":

                    target_program,


                "program_category":
                    program_category,


                "requirements":
                    requirements,


                "proposals":

                    proposals

            },


            "source_decision":

                decision,


            "proposal_ready":

                True

        }