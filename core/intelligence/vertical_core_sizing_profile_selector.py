"""
ArchitectOS Vertical Core Sizing Profile Selector v1.0

Selects a sizing profile for vertical circulation systems.

Important:
- Does not calculate final code dimensions.
- Does not invent regulatory values.
- Only selects the semantic sizing profile.
"""


class VerticalCoreSizingProfileSelector:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"Vertical Core Sizing Profile Selector v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # MAIN
    # ==================================================

    def select(
        self,
        sizing_result,
        building_context=None
    ):

        sizing_result = (
            sizing_result
            or
            {}
        )

        building_context = (
            building_context
            or
            {}
        )


        building_type = str(
            building_context.get(
                "building_type",
                ""
            )
        ).lower()


        function = str(
            building_context.get(
                "function",
                building_type
            )
        ).lower()


        program_type = str(
            building_context.get(
                "program_type",
                ""
            )
        ).lower()


        candidates = {
            building_type,
            function,
            program_type
        }


        # ==================================================
        # PROFILE SELECTION
        # ==================================================

        if any(
            item in candidates
            for item in [
                "cinema",
                "movie_theater",
                "movie_theatre"
            ]
        ):

            profile = "cinema"


        elif any(
            item in candidates
            for item in [
                "amphitheater",
                "amphitheatre",
                "auditorium"
            ]
        ):

            profile = "assembly"


        elif any(
            item in candidates
            for item in [
                "commercial",
                "shopping_center",
                "shopping_centre",
                "mall",
                "retail",
                "shop"
            ]
        ):

            profile = "commercial"


        elif any(
            item in candidates
            for item in [
                "parking",
                "parking_garage"
            ]
        ):

            profile = "parking"


        elif any(
            item in candidates
            for item in [
                "residential",
                "villa",
                "single_family",
                "apartment",
                "housing"
            ]
        ):

            profile = "residential"


        else:

            profile = "generic"


        systems = []


        for item in sizing_result.get(
            "systems",
            []
        ):


            system_type = item.get(
                "type"
            )


            systems.append(

                {

                    "type":
                        system_type,

                    "profile":
                        profile,

                    "status":
                        item.get(
                            "status"
                        ),

                    "rule_application_ready":
                        (
                            item.get("status")
                            ==
                            "ready_for_rule_based_sizing"
                        ),

                    "evidence":
                        item.get(
                            "evidence",
                            {}
                        ),

                    "sizing_requirements":
                        item.get(
                            "sizing_requirements",
                            []
                        ),

                    "source_sizing":
                        item

                }

            )


        return {

            "engine":
                "VERTICAL_CORE_SIZING_PROFILE_SELECTOR",

            "version":
                self.VERSION,

            "profile":
                profile,

            "systems":
                systems,

            "rule_application_ready":
                (
                    len(systems) > 0
                    and
                    all(
                        item.get(
                            "rule_application_ready"
                        )
                        is True

                        for item in systems
                    )
                )

        }