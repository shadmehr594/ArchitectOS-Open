"""
ArchitectOS Reasoning Program Bridge v1.0

Converts architectural reasoning decisions
into floor program requirements.
"""


class ReasoningProgramBridge:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"🔗 Reasoning Program Bridge v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # DECISION TRANSLATION
    # ==================================================

    def translate(
        self,
        reasoning_result
    ):


        program_requirements = []


        decisions = reasoning_result.get(
            "decisions",
            []
        )


        for decision in decisions:


            requirements = decision.get(
                "requirements",
                []
            )


            additions = []


            for requirement in requirements:


                if requirement == "vehicle_access_required":

                    additions.append(
                        "vehicle_access_required"
                    )


                elif requirement == "vehicle_circulation":

                    additions.append(
                        "parking_circulation"
                    )


                elif requirement == "mezzanine_possible":

                    additions.append(
                        "mezzanine_possible"
                    )


                elif requirement == "frontage":

                    additions.append(
                        "street_frontage"
                    )


                elif requirement == "internal_stair":

                    additions.append(
                        "internal_stair"
                    )


                elif requirement == "terrace":

                    additions.append(
                        "private_terrace"
                    )


                elif requirement == "large_openings":

                    additions.append(
                        "expanded_glazing"
                    )


            program_requirements.append(

                {
                    "target":
                        decision.get("target"),

                    "function":
                        decision.get("function"),

                    "space_types":
                        decision.get(
                            "space_types",
                            []
                        ),

                    "additions":
                        additions
                }

            )



        return {

            "program_requirements":
                program_requirements

        }