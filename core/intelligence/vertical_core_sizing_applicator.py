"""
ArchitectOS Vertical Core Sizing Applicator v1.0

Applies resolved vertical sizing rule values
to stair and elevator system parameters.

Important:
- Does not invent dimensions.
- Does not treat semantic placeholders as geometry.
- Only applies compatible resolved values.
"""


class VerticalCoreSizingApplicator:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"Vertical Core Sizing Applicator v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # HELPERS
    # ==================================================

    def build_rule_map(
        self,
        resolved_rules
    ):

        return {

            item.get("rule"):
                item.get("value")

            for item in resolved_rules

            if item.get("rule")
        }


    def is_numeric(
        self,
        value
    ):

        return isinstance(
            value,
            (int, float)
        ) and not isinstance(
            value,
            bool
        )


    # ==================================================
    # STAIRS
    # ==================================================

    def apply_stair_rules(
        self,
        source_system,
        rule_map
    ):

        system = dict(
            source_system
        )


        parameters = dict(
            source_system.get(
                "parameters",
                {}
            )
        )


        # ----------------------------------------------
        # REQUIRED COUNT
        # ----------------------------------------------

        value = rule_map.get(
            "required_exit_stair_count",
            rule_map.get(
                "required_stair_count"
            )
        )


        if self.is_numeric(value):

            parameters["required_count"] = (
                int(value)
            )


        # ----------------------------------------------
        # CLEAR WIDTH
        # ----------------------------------------------

        value = rule_map.get(
            "minimum_clear_width"
        )


        if self.is_numeric(value):

            parameters["clear_width"] = (
                float(value)
            )


        # ----------------------------------------------
        # RISER
        # ----------------------------------------------

        value = rule_map.get(
            "maximum_riser"
        )


        if self.is_numeric(value):

            parameters["riser"] = (
                float(value)
            )


        # ----------------------------------------------
        # TREAD
        # ----------------------------------------------

        value = rule_map.get(
            "minimum_tread"
        )


        if self.is_numeric(value):

            parameters["tread"] = (
                float(value)
            )


        # ----------------------------------------------
        # HANDRAIL
        # ----------------------------------------------

        value = rule_map.get(
            "handrail_requirement"
        )


        if isinstance(
            value,
            bool
        ):

            parameters["handrail_required"] = (
                value
            )


        # ----------------------------------------------
        # FIRE PROTECTION
        # ----------------------------------------------

        value = rule_map.get(
            "fire_protection"
        )


        if value is not None:

            parameters["fire_rating"] = (
                value
            )


        parameters["sizing_application_status"] = (
            "partially_applied"
        )


        system["parameters"] = (
            parameters
        )


        return system


    # ==================================================
    # ELEVATOR
    # ==================================================

    def apply_elevator_rules(
        self,
        source_system,
        rule_map
    ):

        system = dict(
            source_system
        )


        parameters = dict(
            source_system.get(
                "parameters",
                {}
            )
        )


        # ----------------------------------------------
        # REQUIRED COUNT
        # ----------------------------------------------

        value = rule_map.get(
            "required_elevator_count"
        )


        if self.is_numeric(value):

            parameters["required_count"] = (
                int(value)
            )


        # ----------------------------------------------
        # CAPACITY
        # ----------------------------------------------

        value = rule_map.get(
            "car_capacity"
        )


        if self.is_numeric(value):

            parameters["capacity"] = (
                value
            )


        # ----------------------------------------------
        # RATED LOAD
        # ----------------------------------------------

        value = rule_map.get(
            "rated_load"
        )


        if self.is_numeric(value):

            parameters["rated_load"] = (
                value
            )


        # ----------------------------------------------
        # DOOR WIDTH
        # ----------------------------------------------

        value = rule_map.get(
            "door_clear_width"
        )


        if self.is_numeric(value):

            parameters["door_width"] = (
                float(value)
            )


        # ----------------------------------------------
        # SHAFT DIMENSIONS
        # ----------------------------------------------

        shaft_dimensions = rule_map.get(
            "shaft_dimensions"
        )


        if isinstance(
            shaft_dimensions,
            dict
        ):

            shaft_width = shaft_dimensions.get(
                "width"
            )

            shaft_depth = shaft_dimensions.get(
                "depth"
            )


            if self.is_numeric(
                shaft_width
            ):

                parameters["shaft_width"] = (
                    float(shaft_width)
                )


            if self.is_numeric(
                shaft_depth
            ):

                parameters["shaft_depth"] = (
                    float(shaft_depth)
                )


        # ----------------------------------------------
        # ACCESSIBILITY
        # ----------------------------------------------

        value = rule_map.get(
            "wheelchair_access"
        )


        if isinstance(
            value,
            bool
        ):

            parameters["wheelchair_access"] = (
                value
            )


        parameters["sizing_application_status"] = (
            "partially_applied"
        )


        system["parameters"] = (
            parameters
        )


        return system

    # ==================================================
    # ACCESSIBLE RAMP
    # ==================================================

    def apply_accessible_ramp_rules(
        self,
        source_system,
        rule_map
    ):

        system = dict(
            source_system
        )


        parameters = dict(
            source_system.get(
                "parameters",
                {}
            )
        )


        # ----------------------------------------------
        # CLEAR WIDTH
        # ----------------------------------------------

        value = rule_map.get(
            "minimum_accessible_ramp_width"
        )


        if self.is_numeric(value):

            parameters["clear_width"] = (
                float(value)
            )


        # ----------------------------------------------
        # MAXIMUM SLOPE
        # ----------------------------------------------

        value = rule_map.get(
            "maximum_accessible_ramp_slope"
        )


        if self.is_numeric(value):

            parameters["slope"] = (
                float(value)
            )


        # ----------------------------------------------
        # LANDING LENGTH
        # ----------------------------------------------

        value = rule_map.get(
            "minimum_landing_length"
        )


        if self.is_numeric(value):

            parameters["landing_length"] = (
                float(value)
            )


        # ----------------------------------------------
        # HANDRAIL
        # ----------------------------------------------

        value = rule_map.get(
            "handrail_requirement"
        )


        if isinstance(
            value,
            bool
        ):

            parameters["handrail_required"] = (
                value
            )


        # ----------------------------------------------
        # EDGE PROTECTION
        # ----------------------------------------------

        value = rule_map.get(
            "edge_protection_requirement"
        )


        if isinstance(
            value,
            bool
        ):

            parameters[
                "edge_protection_required"
            ] = value


        # ----------------------------------------------
        # WHEELCHAIR ACCESS
        # ----------------------------------------------

        value = rule_map.get(
            "wheelchair_access"
        )


        if isinstance(
            value,
            bool
        ):

            parameters["wheelchair_access"] = (
                value
            )


        parameters[
            "sizing_application_status"
        ] = "partially_applied"


        system["parameters"] = (
            parameters
        )


        return system


    # ==================================================
    # MAIN
    # ==================================================

    def apply(
        self,
        rule_value_result
    ):

        rule_value_result = (
            rule_value_result
            or
            {}
        )


        systems = []


        for item in rule_value_result.get(
            "systems",
            []
        ):


            system_type = item.get(
                "type"
            )


            resolved_rules = item.get(
                "resolved_rules",
                []
            )


            rule_map = self.build_rule_map(
                resolved_rules
            )


            source_rule_evaluation = item.get(
                "source_rule_evaluation",
                {}
            )


            source_profile = source_rule_evaluation.get(
                "source_profile",
                {}
            )


            source_sizing = source_profile.get(
                "source_sizing",
                {}
            )


            source_system = source_sizing.get(
                "source_system",
                {}
            )


            if not source_system:

                continue


            if system_type == "stairs":

                applied_system = (
                    self.apply_stair_rules(
                        source_system,
                        rule_map
                    )
                )


            elif system_type == "elevator":

                applied_system = (
                    self.apply_elevator_rules(
                        source_system,
                        rule_map
                    )
                )

            elif system_type == "accessible_ramp":

                applied_system = (
                    self.apply_accessible_ramp_rules(
                        source_system,
                        rule_map
                    )
                )


            else:

                continue


            applied_system[
                "sizing_profile"
            ] = item.get(
                "profile"
            )


            applied_system[
                "rule_values_ready"
            ] = item.get(
                "rule_values_ready",
                False
            )


            systems.append(
                applied_system
            )


        return {

            "engine":
                "VERTICAL_CORE_SIZING_APPLICATOR",

            "version":
                self.VERSION,

            "vertical_systems":
                systems,

            "sizing_applied":
                len(systems) > 0

        }