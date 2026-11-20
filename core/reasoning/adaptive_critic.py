# ==========================================================
# ADAPTIVE CRITIC ENGINE v20.2
# ==========================================================


class AdaptiveCritic:


    def __init__(self):

        self.version = "20.2"

        print(
            "🧠 Adaptive Critic Engine v20.2 ACTIVE"
        )


    def evaluate(
        self,
        reasoning,
        design
    ):


        issues = []

        improvements = []


        # ==========================
        # DAYLIGHT CHECK
        # ==========================

        if isinstance(reasoning, dict):

            daylight = reasoning.get(
                "reasoning",
                {}
            ).get(
                "daylight",
                {}
            )


            if daylight:

                if daylight.get(
                    "checked"
                ):

                    pass

                else:

                    issues.append(
                        "daylight_optimization"
                    )

                    improvements.append(
                        {
                            "area":
                                "daylight",

                            "suggestion":
                                "increase_natural_light_access",

                            "priority":
                                "medium"
                        }
                    )


        # ==========================
        # SPATIAL OPTIMIZATION
        # ==========================

        if isinstance(design, dict):

            spaces = len(design.keys())


            if spaces > 5:

                issues.append(
                    "spatial_complexity"
                )

                improvements.append(
                    {
                        "area":
                            "spatial_efficiency",

                        "suggestion":
                            "optimize_room_relationships",

                        "priority":
                            "medium"
                    }
                )


        # ==========================
        # DEFAULT CRITIC
        # ==========================

        if not issues:

            issues.append(
                "minor_spatial_optimization_possible"
            )

            improvements.append(
                {
                    "area":
                        "sustainability",

                    "suggestion":
                        "increase_green_design_integration",

                    "priority":
                        "low"
                }
            )


        return {


            "engine":
                "adaptive_critic_v20.2",


            "status":
                "active",


            "issues":
                issues,


            "improvements":
                improvements,


            "confidence":
                0.85

        }