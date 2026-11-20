class DesignScenarioEvaluationEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 DESIGN SCENARIO EVALUATION ENGINE v1.0 ONLINE"
        )



    def evaluate(
        self,
        scenarios,
        intent,
        site_analysis
    ):


        evaluated = []



        requirements = intent.get(
            "requirements",
            []
        )


        site = intent.get(
            "site",
            {}
        )


        neighbors = site.get(
            "neighbors",
            {}
        )



        for scenario in scenarios:


            name = scenario.get(
                "name"
            )


            advantages = []

            limitations = []



            if name == "garden_relationship_strategy":


                if (
                    "garden" in requirements
                    or
                    "pool" in requirements
                ):


                    advantages.append(
                        "strong relationship between living spaces and outdoor landscape"
                    )


                advantages.append(
                    "creates meaningful semi_private outdoor space"
                )


                limitations.append(
                    "open edges require privacy control"
                )



            elif name == "central_courtyard_strategy":


                advantages.append(
                    "improves daylight through internal open space"
                )


                advantages.append(
                    "supports privacy in dense surroundings"
                )


                limitations.append(
                    "requires careful organization around central void"
                )



            elif name == "protected_compact_strategy":


                advantages.append(
                    "creates controlled and protected building volume"
                )


                if (
                    neighbors.get("east")
                    or
                    neighbors.get("west")
                ):


                    advantages.append(
                        "responds well to neighboring boundaries"
                    )


                limitations.append(
                    "outdoor relationship may become limited"
                )



            evaluated.append(

                {

                    "scenario":
                    scenario,


                    "architectural_evaluation":
                    {

                        "advantages":
                        advantages,


                        "limitations":
                        limitations

                    }

                }

            )



        return {


            "evaluated_scenarios":
            evaluated,


            "source":
            "architectural_reasoning"

        }