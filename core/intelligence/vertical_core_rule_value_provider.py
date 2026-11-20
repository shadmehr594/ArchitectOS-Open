"""
ArchitectOS Vertical Core Rule Value Provider v1.0

Provides verified or explicitly supplied vertical sizing rule values.

Important:
- Does not invent regulatory values.
- Supports project overrides.
- Supports profile-specific rule sources.
- Keeps unresolved rules explicit.
"""


class VerticalCoreRuleValueProvider:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"Vertical Core Rule Value Provider v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # MAIN
    # ==================================================

    def resolve(
        self,
        rule_evaluation,
        building_context=None
    ):

        rule_evaluation = (
            rule_evaluation
            or
            {}
        )

        building_context = (
            building_context
            or
            {}
        )


        global_values = building_context.get(
            "vertical_rule_values",
            {}
        )


        profile_values = building_context.get(
            "vertical_profile_rule_values",
            {}
        )


        systems = []


        for system in rule_evaluation.get(
            "systems",
            []
        ):


            system_type = system.get(
                "type"
            )


            profile = system.get(
                "profile",
                "generic"
            )


            resolved_rules = list(
                system.get(
                    "resolved_rules",
                    []
                )
            )


            unresolved_rules = list(
                system.get(
                    "unresolved_rules",
                    []
                )
            )


            resolved_names = {

                item.get("rule")

                for item in resolved_rules

                if item.get("rule")
            }


            profile_rule_values = (
                profile_values.get(
                    profile,
                    {}
                )
            )


            system_profile_values = (
                profile_rule_values.get(
                    system_type,
                    {}
                )
            )


            still_unresolved = []


            for rule_name in unresolved_rules:


                value = None

                source = None


                # ==========================================
                # PROFILE + SYSTEM OVERRIDE
                # ==========================================

                if rule_name in system_profile_values:

                    value = system_profile_values.get(
                        rule_name
                    )

                    source = (
                        "profile_system_override"
                    )


                # ==========================================
                # GLOBAL PROJECT RULE VALUE
                # ==========================================

                elif rule_name in global_values:

                    value = global_values.get(
                        rule_name
                    )

                    source = (
                        "project_rule_value"
                    )


                # ==========================================
                # RESULT
                # ==========================================

                if value is None:

                    still_unresolved.append(
                        rule_name
                    )

                    continue


                if rule_name not in resolved_names:

                    resolved_rules.append(

                        {

                            "rule":
                                rule_name,

                            "value":
                                value,

                            "source":
                                source

                        }

                    )


                    resolved_names.add(
                        rule_name
                    )


            systems.append(

                {

                    "type":
                        system_type,

                    "profile":
                        profile,

                    "priority":
                        system.get(
                            "priority"
                        ),

                    "resolved_rules":
                        resolved_rules,

                    "unresolved_rules":
                        still_unresolved,

                    "status":
                        (
                            "rule_values_resolved"
                            if not still_unresolved
                            else
                            "rule_values_partially_resolved"
                        ),

                    "rule_values_ready":
                        (
                            len(still_unresolved)
                            ==
                            0
                        ),

                    "source_rule_evaluation":
                        system

                }

            )


        return {

            "engine":
                "VERTICAL_CORE_RULE_VALUE_PROVIDER",

            "version":
                self.VERSION,

            "systems":
                systems,

            "all_rule_values_ready":
                (
                    len(systems) > 0
                    and
                    all(
                        item.get(
                            "rule_values_ready"
                        )
                        is True

                        for item in systems
                    )
                )

        }