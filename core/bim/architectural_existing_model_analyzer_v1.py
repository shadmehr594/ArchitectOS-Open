# ==========================================================
# ARCHITECTURAL EXISTING MODEL ANALYZER V1
# ARCHITECTOS EXISTING IFC UNDERSTANDING
# ==========================================================


class ArchitecturalExistingModelAnalyzerV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏛 Architectural Existing Model Analyzer v1.0 ACTIVE"
        )



    # ======================================================
    # ANALYZE IFC CONTEXT
    # ======================================================


    def analyze(
        self,
        planner_context
    ):


        building_state = (
            planner_context.get(
                "building_state",
                {}
            )
        )



        floors = (
            building_state.get(
                "floors",
                0
            )
        )


        walls = (
            building_state.get(
                "walls",
                0
            )
        )


        doors = (
            building_state.get(
                "doors",
                0
            )
        )


        windows = (
            building_state.get(
                "windows",
                0
            )
        )


        openings = (
            doors
            +
            windows
        )



        observations = []



        if floors > 0:

            observations.append(
                f"{floors} existing floors detected"
            )



        if walls > 0:

            observations.append(
                f"{walls} architectural walls analyzed"
            )



        if openings > 0:

            observations.append(
                f"{openings} openings detected"
            )



        if windows > 0 and walls > 0:


            ratio = round(
                windows / walls,
                2
            )


            observations.append(
                f"window to wall indicator: {ratio}"
            )



        return {


            "engine":
                "ARCHITECTURAL_EXISTING_MODEL_ANALYZER_V1",


            "version":
                self.VERSION,


            "analysis_type":
                "existing_building_architectural_analysis",



            "building_analysis":
                {


                    "floors":
                        floors,


                    "walls":
                        walls,


                    "doors":
                        doors,


                    "windows":
                        windows,


                    "openings":
                        openings

                },



            "observations":
                observations,



            "planner_ready":
                True


        }