"""
ArchitectOS Vertical Core Sizing Reasoner v1.0

Evaluates whether stairs and elevators
have sufficient architectural evidence
for technical sizing.

Important:
- Does not invent code values.
- Does not assume occupancy.
- Does not generate geometry.
"""


class VerticalCoreSizingReasoner:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"Vertical Core Sizing Reasoner v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # MAIN
    # ==================================================

    def evaluate(
        self,
        vertical_result,
        building_context=None
    ):

        vertical_result = (
            vertical_result
            or
            {}
        )

        building_context = (
            building_context
            or
            {}
        )


        systems = vertical_result.get(
            "vertical_systems",
            []
        )


        results = []


        for system in systems:


            system_type = system.get(
                "type"
            )


            if system_type not in [
                "stairs",
                "elevator",
                "accessible_ramp"
            ]:

                continue


            parameters = system.get(
                "parameters",
                {}
            )


            evidence = parameters.get(
                "sizing_evidence",
                {}
            )


            occupancy = parameters.get(
                "occupancy_basis"
            )


            gross_area = parameters.get(
                "gross_area_basis"
            )


            floor_height = parameters.get(
                "floor_height_basis"
            )


            floor_count = evidence.get(
                "floor_count"
            )


            missing_evidence = []


            # ==================================================
            # ACCESSIBLE RAMP
            # ==================================================

            if system_type == "accessible_ramp":

                sizing_requirements = [
                    "clear_width",
                    "slope",
                    "landing_length",
                    "handrail_required",
                    "edge_protection_required"
                ]


                ramp_evidence = {

                    "building_type":
                        building_context.get(
                            "building_type"
                        ),

                    "accessibility_required":
                        True,

                    "connects":
                        system.get(
                            "connects",
                            []
                        ),

                    "site_fit_required":
                        parameters.get(
                            "site_fit_required",
                            True
                        ),

                    "level_difference":
                        building_context.get(
                            "accessible_level_difference"
                        )

                }


                status = (
                    "ready_for_rule_based_sizing"
                )


                result_evidence = (
                    ramp_evidence
                )


            # ==================================================
            # STAIRS / ELEVATOR
            # ==================================================

            else:

                if occupancy is None:

                    missing_evidence.append(
                        "occupancy"
                    )


                if gross_area is None:

                    missing_evidence.append(
                        "gross_area"
                    )


                if floor_count is None:

                    missing_evidence.append(
                        "floor_count"
                    )


                if system_type == "stairs":

                    sizing_requirements = [
                        "required_count",
                        "clear_width",
                        "riser",
                        "tread",
                        "flight_count"
                    ]


                    if floor_height is None:

                        missing_evidence.append(
                            "floor_height"
                        )


                else:

                    sizing_requirements = [
                        "required_count",
                        "capacity",
                        "rated_load",
                        "car_width",
                        "car_depth",
                        "door_width",
                        "shaft_width",
                        "shaft_depth"
                    ]


                if missing_evidence:

                    status = (
                        "insufficient_evidence"
                    )

                else:

                    status = (
                        "ready_for_rule_based_sizing"
                    )


                result_evidence = {

                    "occupancy":
                        occupancy,

                    "gross_area":
                        gross_area,

                    "floor_height":
                        floor_height,

                    "floor_count":
                        floor_count,

                    "building_type":
                        evidence.get(
                            "building_type"
                        )

                }


            results.append(

                {

                    "type":
                        system_type,

                    "status":
                        status,

                    "missing_evidence":
                        missing_evidence,

                    "sizing_requirements":
                        sizing_requirements,

                    "evidence":
                        result_evidence,

                    "source_system":
                        system

                }

            )


        return {

            "engine":
                "VERTICAL_CORE_SIZING_REASONER",

            "version":
                self.VERSION,

            "systems":
                results,

            "sizing_ready":
                (
                    len(results) > 0
                    and
                    all(
                        item.get("status")
                        ==
                        "ready_for_rule_based_sizing"

                        for item in results
                    )
                )

        }