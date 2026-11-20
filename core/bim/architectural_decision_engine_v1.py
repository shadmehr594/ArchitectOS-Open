# ==========================================================
# ARCHITECTURAL DECISION ENGINE V1
# ARCHITECTOS EXISTING IFC INTELLIGENCE
# ==========================================================


class ArchitecturalDecisionEngineV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 Architectural Decision Engine v1.0 ACTIVE"
        )



    # ======================================================
    # MAIN DECISION
    # ======================================================


    def decide(
        self,
        existing_context
    ):


        building_state = (
            existing_context.get(
                "building_analysis",
                {}
            )
        )


        floors = building_state.get(
            "floors",
            0
        )


        walls = building_state.get(
            "walls",
            0
        )


        openings = building_state.get(
            "openings",
            0
        )



        decisions = []



        # ==============================================
        # BUILDING TYPE
        # ==============================================


        if floors > 1:

            decisions.append(
                "existing_multistory_building"
            )


        else:

            decisions.append(
                "existing_single_story_building"
            )



        # ==============================================
        # ARCHITECTURAL SHELL
        # ==============================================


        if walls > 0:

            decisions.append(
                "architectural_shell_detected"
            )



        # ==============================================
        # OPENINGS
        # ==============================================


        if openings > 0:

            decisions.append(
                "opening_pattern_available"
            )



        # ==============================================
        # PLANNER STATE
        # ==============================================


        planner_ready = (

            len(decisions)
            >
            0

        )



        return {


            "engine":
                "ARCHITECTURAL_DECISION_ENGINE_V1",


            "version":
                self.VERSION,


            "decision_type":
                "existing_building_evaluation",


            "decisions":
                decisions,


            "source_context":
                existing_context,


            "planner_ready":
                planner_ready

        }