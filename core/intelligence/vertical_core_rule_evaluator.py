"""
ArchitectOS Vertical Core Rule Evaluator v1.0

Evaluates whether required vertical sizing rules
have sufficient evidence / rule values.

Important:
- Does not invent regulatory dimensions.
- Does not calculate final geometry.
- Preserves unresolved rule state explicitly.
"""


class VerticalCoreRuleEvaluator:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"Vertical Core Rule Evaluator v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # MAIN
    # ==================================================

    def evaluate(
        self,
        profile_result,
        rules_engine,
        building_context=None
    ):

        profile_result = (
            profile_result
            or
            {}
        )

        building_context = (
            building_context
            or
            {}
        )


        systems = []


        rule_values = building_context.get(
            "vertical_rule_values",
            {}
        )


        for system in profile_result.get(
            "systems",
            []
        ):


            system_type = system.get(
                "type"
            )


            profile = system.get(
                "profile",
                profile_result.get(
                    "profile",
                    "generic"
                )
            )


            rule_profile = rules_engine.get_rules(
                profile,
                system_type
            )


            required_rules = rule_profile.get(
                "required_rules",
                []
            )


            evidence = system.get(
                "evidence",
                {}
            )


            resolved_rules = []

            unresolved_rules = []


            for rule_name in required_rules:


                # ==========================================
                # EVIDENCE-BACKED RULES
                # ==========================================

                if rule_name in [
                    "occupant_load",
                    "assembly_occupant_load",
                    "occupant_demand"
                ]:

                    value = evidence.get(
                        "occupancy"
                    )


                elif rule_name == "service_floor_count":

                    value = evidence.get(
                        "floor_count"
                    )


                # ==========================================
                # EXPLICIT RULE VALUES
                # ==========================================

                else:

                    value = rule_values.get(
                        rule_name
                    )


                if value is None:

                    unresolved_rules.append(
                        rule_name
                    )

                else:

                    resolved_rules.append(

                        {

                            "rule":
                                rule_name,

                            "value":
                                value

                        }

                    )


            status = (
                "rules_resolved"
                if not unresolved_rules
                else
                "rules_partially_resolved"
            )


            systems.append(

                {

                    "type":
                        system_type,

                    "profile":
                        profile,

                    "priority":
                        rule_profile.get(
                            "priority"
                        ),

                    "status":
                        status,

                    "resolved_rules":
                        resolved_rules,

                    "unresolved_rules":
                        unresolved_rules,

                    "rule_application_ready":
                        (
                            len(unresolved_rules)
                            ==
                            0
                        ),

                    "source_profile":
                        system,

                    "source_rule_profile":
                        rule_profile

                }

            )


        return {

            "engine":
                "VERTICAL_CORE_RULE_EVALUATOR",

            "version":
                self.VERSION,

            "systems":
                systems,

            "all_rules_resolved":
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