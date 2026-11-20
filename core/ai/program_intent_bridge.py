# ==========================================================
# ArchitectOS Program Intent Bridge v1.0
#
# Architectural Intent
#        |
#        ↓
# Program Intent Bridge
#        |
#        ↓
# Parking + Vertical + Program Generator
#        |
#        ↓
# Final Building Program
#
# ==========================================================


from core.ai.parking_intelligence_engine import (
    ParkingIntelligenceEngine
)

from core.ai.building_program_generator import (
    BuildingProgramGenerator
)

from core.intelligence.vertical_circulation_reasoning import (
    VerticalCirculationReasoning
)



class ProgramIntentBridge:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🔗 Program Intent Bridge v1.0 ACTIVE"
        )


        self.parking_engine = (
            ParkingIntelligenceEngine()
        )


        self.program_generator = (
            BuildingProgramGenerator()
        )


        self.vertical_reasoning = (
            VerticalCirculationReasoning()
        )



    # ==================================================
    # BUILD
    # ==================================================

    def build(
        self,
        intent
    ):


        if not isinstance(
            intent,
            dict
        ):

            intent = {}



        # ==============================================
        # PARKING ANALYSIS
        # ==============================================

        parking_input = {

            "type":
            intent.get(
                "building_type",
                "building"
            ),


            "gross_area":
            intent.get(
                "gross_area",
                0
            ),


            "units":
            intent.get(
                "units",
                0
            )

        }



        parking = (
            self.parking_engine.analyze(
                parking_input
            )
        )



        # ==============================================
        # MERGE INTENT
        # ==============================================

        program_input = dict(
            intent
        )


        program_input["parking"] = (
            parking
        )

        # ==============================================
        # VERTICAL CIRCULATION CONTEXT
        # ==============================================

        levels = intent.get(
            "levels",
            {}
        )

        if not isinstance(
            levels,
            dict
        ):
            levels = {}


        total_floors = levels.get(
            "total"
        )

        if not isinstance(
            total_floors,
            int
        ):
            total_floors = 0


        vertical_context = dict(
            intent
        )

        vertical_context["floors"] = [
            f"F{floor_number}"
            for floor_number in range(
                1,
                total_floors + 1
            )
        ]

        # ==============================================
        # VERTICAL REQUIREMENT NORMALIZATION
        # ==============================================

        vertical_requirements = []


        explicit_requirements = intent.get(
            "requirements",
            []
        )

        if isinstance(
            explicit_requirements,
            str
        ):
            explicit_requirements = [
                explicit_requirements
            ]

        if isinstance(
            explicit_requirements,
            (list, tuple, set)
        ):
            vertical_requirements.extend(
                explicit_requirements
            )


        intent_functions = intent.get(
            "functions",
            []
        )

        if isinstance(
            intent_functions,
            (list, tuple, set)
        ):
            vertical_requirements.extend(
                intent_functions
            )


        intent_spaces = intent.get(
            "spaces",
            []
        )

        if isinstance(
            intent_spaces,
            (list, tuple, set)
        ):
            vertical_requirements.extend(
                intent_spaces
            )


        vertical_requirements = list(
            dict.fromkeys(
                str(item).lower()
                for item in vertical_requirements
                if item is not None
            )
        )


        vertical_context["requirements"] = (
            vertical_requirements
        )


        vertical_result = (
            self.vertical_reasoning.analyze(
                vertical_context
            )
        )


        program_input[
            "vertical_systems"
        ] = vertical_result.get(
            "vertical_systems",
            []
        )



        # ==============================================
        # PROGRAM GENERATION
        # ==============================================

        result = (
            self.program_generator.generate(
                program_input
            )
        )

        # ==============================================
        # MERGE VERTICAL SYSTEM CONTRACT
        # ==============================================

        generated_program = result.get(
            "program",
            {}
        )

        if not isinstance(
            generated_program,
            dict
        ):
            generated_program = {}


        generated_program[
            "vertical_systems"
        ] = vertical_result.get(
            "vertical_systems",
            []
        )


        generated_program[
            "vertical_decision_context"
        ] = vertical_result.get(
            "decision_context",
            {}
        )


        # ==============================================
        # INTELLIGENCE FUSION
        # ==============================================

        site_analysis = (
            intent.get(
                "site_constraints",
                {}
            )
        )


        transport_analysis = (
            intent.get(
                "vertical_transport",
                {}
            )
        )


        regulation_analysis = (
            intent.get(
                "regulations",
                {}
            )
        )



        intent["building_program"] = (
            result["program"]
        )


        # ==============================================
        # ATTACH PROGRAM TO INTENT
        # ==============================================

        intent["building_program"] = (
            result["program"]
        )



        return {


            "engine":

            "program_intent_bridge_v1.1",



            "parking":

            parking,



            "site_analysis":

            site_analysis,



            "transport_analysis":

            transport_analysis,



            "regulation_analysis":

            regulation_analysis,



            "building_program":

            result["program"],



            "source_intent": {
                "building_type": intent.get("building_type"),
                "style": intent.get("style"),
                "materials": intent.get("materials", []),
                "functions": intent.get("functions", []),
                "spaces": intent.get("spaces", []),
                "site": intent.get("site", []),
                "environment": intent.get("environment", [])
            }

        }