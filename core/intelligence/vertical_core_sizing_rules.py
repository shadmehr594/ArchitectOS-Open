"""
ArchitectOS Vertical Core Sizing Rules v1.0

Semantic rule profiles for vertical circulation sizing.

Important:
- Does not contain jurisdiction-specific code values.
- Does not invent regulatory dimensions.
- Defines which rule categories must be resolved.
"""


class VerticalCoreSizingRules:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"Vertical Core Sizing Rules v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # RULE PROFILES
    # ==================================================

    ACCESSIBLE_RAMP_RULES = {

        "required_rules":
        [
            "minimum_accessible_ramp_width",
            "maximum_accessible_ramp_slope",
            "minimum_landing_length",
            "handrail_requirement",
            "edge_protection_requirement",
            "wheelchair_access"
        ],

        "priority":
            "accessible_pedestrian_route"

    }

    RULES = {

        "residential":
        {

            "stairs":
            {
                "required_rules":
                [
                    "occupant_load",
                    "minimum_clear_width",
                    "maximum_riser",
                    "minimum_tread",
                    "landing_geometry",
                    "handrail_requirement"
                ],

                "priority":
                    "private_circulation"
            },

            "elevator":
            {
                "required_rules":
                [
                    "accessibility_requirement",
                    "service_floor_count",
                    "car_capacity",
                    "car_dimensions",
                    "door_clear_width",
                    "shaft_dimensions"
                ],

                "priority":
                    "residential_vertical_transport"
            }

        },


        "commercial":
        {

            "stairs":
            {
                "required_rules":
                [
                    "occupant_load",
                    "egress_capacity",
                    "required_stair_count",
                    "minimum_clear_width",
                    "maximum_riser",
                    "minimum_tread",
                    "landing_geometry",
                    "handrail_requirement",
                    "fire_protection"
                ],

                "priority":
                    "public_egress"
            },

            "elevator":
            {
                "required_rules":
                [
                    "occupant_demand",
                    "service_floor_count",
                    "required_elevator_count",
                    "car_capacity",
                    "rated_load",
                    "car_dimensions",
                    "door_clear_width",
                    "shaft_dimensions",
                    "accessible_service"
                ],

                "priority":
                    "public_vertical_transport"
            }

        },


        "cinema":
        {

            "stairs":
            {
                "required_rules":
                [
                    "assembly_occupant_load",
                    "assembly_egress_capacity",
                    "required_exit_stair_count",
                    "minimum_clear_width",
                    "crowd_discharge",
                    "landing_geometry",
                    "handrail_requirement",
                    "fire_protection"
                ],

                "priority":
                    "assembly_egress"
            },

            "elevator":
            {
                "required_rules":
                [
                    "assembly_accessibility",
                    "occupant_demand",
                    "required_elevator_count",
                    "car_capacity",
                    "door_clear_width",
                    "shaft_dimensions",
                    "wheelchair_access"
                ],

                "priority":
                    "assembly_public_transport"
            }

        },


        "assembly":
        {

            "stairs":
            {
                "required_rules":
                [
                    "assembly_occupant_load",
                    "assembly_egress_capacity",
                    "required_exit_stair_count",
                    "minimum_clear_width",
                    "crowd_discharge",
                    "landing_geometry",
                    "handrail_requirement",
                    "fire_protection"
                ],

                "priority":
                    "assembly_egress"
            },

            "elevator":
            {
                "required_rules":
                [
                    "assembly_accessibility",
                    "occupant_demand",
                    "required_elevator_count",
                    "car_capacity",
                    "door_clear_width",
                    "shaft_dimensions",
                    "wheelchair_access"
                ],

                "priority":
                    "assembly_public_transport"
            }

        },


        "parking":
        {

            "stairs":
            {
                "required_rules":
                [
                    "occupant_load",
                    "egress_capacity",
                    "required_stair_count",
                    "minimum_clear_width",
                    "fire_protection"
                ],

                "priority":
                    "parking_egress"
            },

            "elevator":
            {
                "required_rules":
                [
                    "accessible_service",
                    "service_floor_count",
                    "car_capacity",
                    "door_clear_width",
                    "shaft_dimensions"
                ],

                "priority":
                    "parking_pedestrian_transport"
            }

        },


        "generic":
        {

            "stairs":
            {
                "required_rules":
                [
                    "occupant_load",
                    "minimum_clear_width"
                ],

                "priority":
                    "generic_vertical_access"
            },

            "elevator":
            {
                "required_rules":
                [
                    "service_floor_count",
                    "capacity"
                ],

                "priority":
                    "generic_vertical_transport"
            }

        }

    }


    # ==================================================
    # GET RULES
    # ==================================================

    def get_rules(
        self,
        profile,
        system_type
    ):

        profile_rules = self.RULES.get(
            profile,
            self.RULES["generic"]
        )


        rules = profile_rules.get(
            system_type
        )

        if (
            not rules
            and
            system_type == "accessible_ramp"
        ):

            rules = (
                self.ACCESSIBLE_RAMP_RULES
            )


        if not rules:

            return {
                "profile":
                    profile,

                "system_type":
                    system_type,

                "status":
                    "unsupported_system",

                "required_rules":
                    []
            }


        return {

            "profile":
                profile,

            "system_type":
                system_type,

            "status":
                "rule_profile_available",

            "priority":
                rules.get(
                    "priority"
                ),

            "required_rules":
                list(
                    rules.get(
                        "required_rules",
                        []
                    )
                )

        }