# =====================================================
# BIM Scenario Intelligence Engine v58
# =====================================================


class BIMScenarioIntelligenceEngine:


    def __init__(self):

        print(
            "🎭 BIM Scenario Intelligence Engine v58.0 ACTIVE"
        )



    def build(
        self,
        graph
    ):

        print(
            "▶️ BUILD BIM SCENARIO v58"
        )


        digital_twin = graph.get(
            "digital_twin",
            {}
        )


        simulation = graph.get(
            "simulation",
            {}
        )


        base_state = simulation.get(
            "state",
            {}
        )


        occupancy = base_state.get(
            "occupancy",
            0
        )


        energy = simulation.get(
            "energy",
            {}
        ).get(
            "total",
            0
        )


        scenario = {

            "name":
                "baseline_analysis",


            "before":
            {
                "occupancy": occupancy,
                "energy": energy
            },


            "after":
            {
                "occupancy": occupancy,
                "energy": energy
            },


            "changes":
            [],


            "recommendations":
            []

        }



        # -----------------------------
        # Scenario: Crowd Increase
        # -----------------------------

        crowd = self._crowd_scenario(
            occupancy,
            energy
        )


        scenario["scenarios"] = [

            crowd

        ]



        print(
            "🎭 SCENARIOS GENERATED:",
            len(
                scenario["scenarios"]
            )
        )


        return {

            "engine":
                "bim_scenario_v58.0",


            "scenario":
                scenario,


            "statistics":
            {

                "scenarios":
                    len(
                        scenario["scenarios"]
                    ),

                "occupancy":
                    occupancy,

                "energy":
                    energy

            }

        }



    def _crowd_scenario(
        self,
        occupancy,
        energy
    ):


        new_people = occupancy * 2


        new_energy = int(
            energy * 1.35
        )


        return {

            "name":
                "crowd_increase",


            "before":
            {
                "occupancy": occupancy,
                "energy": energy
            },


            "after":
            {
                "occupancy": new_people,
                "energy": new_energy
            },


            "recommendations":
            [

                "increase_hvac",

                "monitor_energy"

            ]

        }