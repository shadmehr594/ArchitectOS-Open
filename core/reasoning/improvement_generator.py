# ==========================================================
# IMPROVEMENT GENERATOR ENGINE v20.2
# ==========================================================


class ImprovementGenerator:


    def __init__(self):

        self.version = "20.2"

        print(
            "⚙️ Improvement Generator Engine v20.2 ACTIVE"
        )


    def generate(
        self,
        critic_report,
        plan
    ):

        improvements = []


        for item in critic_report.get(
            "improvements",
            []
        ):

            area = item.get(
                "area"
            )

            suggestion = item.get(
                "suggestion"
            )


            # ==========================
            # SUSTAINABILITY
            # ==========================

            if area == "sustainability":

                improvements.append(
                    {
                        "target":
                            "roof",

                        "action":
                            "increase_green_integration",

                        "strategy":
                            suggestion,

                        "expected_gain":
                            0.05
                    }
                )


            # ==========================
            # SPATIAL
            # ==========================

            elif area == "spatial_efficiency":

                improvements.append(
                    {
                        "target":
                            "layout",

                        "action":
                            "optimize_room_relationships",

                        "strategy":
                            suggestion,

                        "expected_gain":
                            0.08
                    }
                )


            # ==========================
            # DAYLIGHT
            # ==========================

            elif area == "daylight":

                improvements.append(
                    {
                        "target":
                            "orientation",

                        "action":
                            "increase_daylight",

                        "strategy":
                            suggestion,

                        "expected_gain":
                            0.07
                    }
                )


        return {

            "engine":
                "improvement_generator_v20.2",

            "generated":
                len(improvements),

            "actions":
                improvements
        }