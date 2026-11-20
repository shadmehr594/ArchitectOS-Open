# ==========================================
# BIM Optimization Intelligence Engine v59.0
# ==========================================


class BIMOptimizationIntelligenceEngine:

    def __init__(self):

        self.version = "bim_optimization_v59.0"


    def build(self, graph):

        print(
            "▶️ BUILD BIM OPTIMIZATION v59"
        )


        scenario_data = graph.get(
            "scenario",
            {}
        )


        scenarios = scenario_data.get(
            "scenario",
            {}
        ).get(
            "scenarios",
            []
        )


        best_scenario = "baseline"

        best_score = 0


        checked = 0


        for scenario in scenarios:

            checked += 1


            before = scenario.get(
                "before",
                {}
            )

            after = scenario.get(
                "after",
                {} 
            )


            before_energy = before.get(
                "energy",
                0
            )

            after_energy = after.get(
                "energy",
                0
            )


            if after_energy <= before_energy:

                score = 100

            else:

                score = max(
                    50,
                    100 - (
                        (after_energy - before_energy)
                        / max(before_energy,1)
                        * 100
                    )
                )


            if score > best_score:

                best_score = score

                best_scenario = scenario.get(
                    "name",
                    "unknown"
                )


        result = {

            "engine":
                self.version,


            "optimization": {

                "best_scenario":
                    best_scenario,

                "score":
                    round(best_score,2),

                "recommendations": [

                    "optimize_hvac_schedule",

                    "reduce_unused_lighting",

                    "balance_room_usage"

                ]

            },


            "statistics": {

                "scenarios_checked":
                    checked,

                "optimized":
                    True

            }

        }


        return result