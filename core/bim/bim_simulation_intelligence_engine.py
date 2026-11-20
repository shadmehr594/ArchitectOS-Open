# =====================================================
# BIM SIMULATION INTELLIGENCE ENGINE v57
# =====================================================


class BIMSimulationIntelligenceEngine:


    def __init__(self):

        print(
            "⚙️ BIM Simulation Intelligence Engine v57.0 ACTIVE"
        )


    # =================================================
    # MAIN BUILD
    # =================================================

    def build(self, graph=None):

        print(
            "▶️ BUILD BIM SIMULATION v57"
        )


        if not isinstance(graph, dict):
            graph = {}


        digital_twin = graph.get(
            "digital_twin",
            {}
        )


        state = self._build_state(
            digital_twin
        )


        energy = self._energy_simulation(
            graph
        )


        timeline = self._timeline()


        result = {

            "engine":
                "bim_simulation_v57.0",


            "state":
                state,


            "energy":
                energy,


            "timeline":
                timeline,


            "statistics":
            {

                "occupancy":
                    state["occupancy"],

                "energy_total":
                    energy["total"],

                "events":
                    len(timeline)

            }

        }


        print(
            f"👥 OCCUPANCY GENERATED: {state['occupancy']}"
        )


        print(
            "⚡ ENERGY STATE GENERATED"
        )


        print(
            f"🕒 TIME STATES GENERATED: {len(timeline)}"
        )


        return result



    # =================================================
    # BUILDING STATE
    # =================================================

    def _build_state(self, digital_twin):


        assets = []


        if isinstance(digital_twin, dict):

            assets = digital_twin.get(
                "assets",
                []
            )


        return {

            "time":
                "08:00",


            "occupancy":
                len(assets),


            "temperature":
                22,


            "lights":
                "ON",


            "hvac":
                "AUTO"

        }



    # =================================================
    # ENERGY SIMULATION
    # =================================================

    def _energy_simulation(self, graph):


        lighting = 120

        hvac = 800


        return {

            "lighting_load":
                lighting,


            "hvac_load":
                hvac,


            "total":
                lighting + hvac

        }



    # =================================================
    # TIME LINE
    # =================================================

    def _timeline(self):


        return [

            {
                "time": "08:00",
                "state": "morning"
            },

            {
                "time": "12:00",
                "state": "peak"
            },

            {
                "time": "18:00",
                "state": "evening"
            },

            {
                "time": "22:00",
                "state": "night"
            }

        ]