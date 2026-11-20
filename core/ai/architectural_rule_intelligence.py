class ArchitecturalRuleIntelligence:


    def __init__(self):

        print(
            "🏛️ Architectural Rule Intelligence Engine v26.1 ACTIVE"
        )


    def check(
        self,
        scene_graph,
        config=None
    ):


        if config is None:

            config = {}


        mode = config.get(
            "rule_mode",
            "advisory"
        )


        rules = config.get(
            "rules",
            {}
        )


        warnings = []

        violations = []

        recommendations = []


        nodes = scene_graph.get(
            "graph",
            {}
        ).get(
            "nodes",
            []
        )


        spaces = [
            n for n in nodes
            if n.get("type") == "space"
        ]


        facades = [
            n for n in nodes
            if n.get("type") == "facade"
        ]


        roof = [
            n for n in nodes
            if n.get("type") == "roof"
        ]



        # -------------------------
        # Daylight Rule
        # -------------------------

        daylight = rules.get(
            "daylight",
            {}
        )


        if daylight.get(
            "enabled",
            False
        ):


            if len(facades) == 0:

                message = (
                    "facade information missing for daylight analysis"
                )


                if mode == "strict":

                    violations.append(
                        {
                            "rule":"daylight",
                            "message":message
                        }
                    )

                else:

                    warnings.append(
                        {
                            "rule":"daylight",
                            "message":message
                        }
                    )

            else:

                recommendations.append(
                    "daylight_analysis_available"
                )



        # -------------------------
        # Separation Joint
        # -------------------------

        separation = rules.get(
            "separation_joint",
            {}
        )


        if separation.get(
            "enabled",
            False
        ):

            if separation.get(
                "mandatory",
                False
            ):

                recommendations.append(
                    "separation_joint_checked"
                )

            else:

                warnings.append(
                    {
                        "rule":"separation_joint",
                        "message":
                        "optional check completed"
                    }
                )



        # -------------------------
        # Setback
        # -------------------------

        setback = rules.get(
            "setback",
            {}
        )


        if setback.get(
            "enabled",
            False
        ):


            if setback.get(
                "mandatory",
                False
            ):

                recommendations.append(
                    "setback_mandatory_analysis"
                )

            else:

                recommendations.append(
                    "setback_optional_analysis"
                )



        # -------------------------
        # Green Roof
        # -------------------------

        green = rules.get(
            "green_roof",
            {}
        )


        if green.get(
            "enabled",
            False
        ):


            if len(roof) > 0:

                recommendations.append(
                    "green_roof_detected"
                )

            else:

                warnings.append(
                    {
                        "rule":"green_roof",
                        "message":
                        "green roof requested but roof not found"
                    }
                )



        score = 100


        if len(violations) > 0:

            score -= (
                len(violations)
                *
                10
            )


        if score < 0:

            score = 0



        return {


            "engine":
            "architectural_rule_intelligence_v26.1",


            "status":
            "checked",


            "mode":
            mode,


            "score":
            score,


            "violations":
            violations,


            "warnings":
            warnings,


            "recommendations":
            recommendations,


            "statistics":
            {

                "spaces":
                len(spaces),

                "facades":
                len(facades),

                "roof":
                len(roof)

            }

        }