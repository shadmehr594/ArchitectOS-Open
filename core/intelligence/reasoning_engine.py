# ==========================================================
# ArchitectOS Architectural Reasoning Engine v39
# Analysis -> Recommendations -> Design Actions
# ==========================================================


from core.intelligence.decision_adapter import decision_adapter



class ReasoningEngine:


    VERSION = "39.0"



    def __init__(self):

        print(
            f"🤖 Architectural Reasoning Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # CLIMATE ANALYSIS
    # ==================================================

    def analyze_climate(
        self,
        project
    ):

        recommendations = []


        climate = project.get(
            "climate",
            ""
        )


        if climate == "hot":


            recommendations.append({

                "issue":
                "high_temperature_environment",


                "recommendation":
                "increase_solar_protection"

            })


        return recommendations



    # ==================================================
    # OPENING ANALYSIS
    # ==================================================

    def analyze_openings(
        self,
        facade
    ):


        recommendations = []


        south = facade.get(
            "south",
            {}
        )


        openings = south.get(
            "openings",
            []
        )


        for opening in openings:


            if opening.get(
                "type"
            ) == "window":


                width = opening.get(
                    "width",
                    0
                )


                if width >= 2:


                    recommendations.append({

                        "issue":
                        "large_south_opening",


                        "recommendation":
                        "add_horizontal_shading"

                    })



        return recommendations



    # ==================================================
    # ROOF ANALYSIS
    # ==================================================

    def analyze_roof(
        self,
        roof
    ):


        recommendations = []


        if roof.get(
            "green_roof"
        ):


            recommendations.append({

                "benefit":
                "thermal_buffer",


                "status":
                "positive"

            })



        return recommendations



    # ==================================================
    # DESIGN DECISION GENERATOR
    # ==================================================

    def generate_design_decisions(
        self,
        project
    ):


        decisions = []


        climate = project.get(
            "climate",
            ""
        )


        facade = project.get(
            "facade",
            {}
        )


        roof = project.get(
            "roof",
            {}
        )



        # ==============================================
        # CLIMATE DECISIONS
        # ==============================================

        if climate == "hot":


            decisions.append({

                "target":
                "facade",


                "action":
                "add_solar_protection",


                "reason":
                "hot climate requires shading strategy"

            })



            decisions.append({

                "target":
                "materials",


                "action":
                "prefer_thermal_materials",


                "reason":
                "reduce heat gain"

            })



        # ==============================================
        # FACADE DECISIONS
        # ==============================================

        if facade:


            openings = facade.get(
                "south",
                {}
            ).get(
                "openings",
                []
            )


            for opening in openings:


                if (

                    opening.get(
                        "type"
                    )
                    ==
                    "window"

                    and

                    opening.get(
                        "width",
                        0
                    )
                    >= 2

                ):


                    decisions.append({

                        "target":
                        "facade",


                        "action":
                        "add_horizontal_shading",


                        "reason":
                        "large south opening detected"

                    })



        # ==============================================
        # ROOF DECISIONS
        # ==============================================

        if roof.get(
            "green_roof"
        ):


            decisions.append({

                "target":
                "roof",


                "action":
                "preserve_green_roof",


                "reason":
                "thermal buffer improvement"

            })



        return decisions



    # ==================================================
    # MAIN PROCESS
    # ==================================================

    def process(
        self,
        project
    ):



        result = {


            "engine":
            f"reasoning_engine_v{self.VERSION}",


            "status":
            "completed",


            "analysis":
            [],


            "recommendations":
            [],


            "actions":
            []

        }



        result["analysis"].append(
            "architectural_quality_check"
        )



        # ==============================================
        # ANALYZE
        # ==============================================


        result["recommendations"].extend(

            self.analyze_climate(
                project
            )

        )



        result["recommendations"].extend(

            self.analyze_openings(

                project.get(
                    "facade",
                    {}
                )

            )

        )



        result["recommendations"].extend(

            self.analyze_roof(

                project.get(
                    "roof",
                    {}
                )

            )

        )



        # ==============================================
        # CONVERT TO ACTIONS
        # ==============================================


        result["actions"] = decision_adapter.convert(

            result["recommendations"]

        )



        return result