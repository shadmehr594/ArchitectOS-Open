class ArchitecturalReport:

    def __init__(self):

        print(
            "📄 Architectural Report Engine v21.1 ACTIVE"
        )


    def generate(
        self,
        plan,
        spatial,
        zoning,
        reasoning
    ):

        report = {

            "project": {
                "type":
                    plan.get(
                        "building_type",
                        "unknown"
                    ),

                "style":
                    plan.get(
                        "style",
                        "unknown"
                    ),

                "complexity":
                    plan.get(
                        "complexity",
                        "unknown"
                    )
            },


            "site": {

                "width":
                    plan.get(
                        "site",
                        {}
                    ).get(
                        "width"
                    ),

                "depth":
                    plan.get(
                        "site",
                        {}
                    ).get(
                        "depth"
                    ),

                "area":
                    plan.get(
                        "site",
                        {}
                    ).get(
                        "area"
                    )
            },


            "floors": [],


            "requirements":
                plan.get(
                    "requirements",
                    {}
                ),


            "design_intelligence":

                reasoning.get(
                    "design_intelligence",
                    None
                )

        }


        levels = plan.get(
            "levels",
            []
        )


        for level in levels:

            report["floors"].append(

                {

                "level":
                    level.get(
                        "level"
                    ),

                "type":
                    level.get(
                        "type"
                    ),

                "units":
                    level.get(
                        "units",
                        0
                    )

                }

            )


        return {

            "engine":
                "architectural_report_v21.1",

            "status":
                "generated",

            "report":
                report
        }