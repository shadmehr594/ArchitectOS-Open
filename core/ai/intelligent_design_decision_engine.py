class IntelligentDesignDecisionEngine:


    def __init__(self):

        print(
            "🧠 Intelligent Design Decision Engine v26.5 ACTIVE"
        )


    def decide(
        self,
        comparison_result,
        optimization_result=None,
        rule_result=None,
        critic_result=None
    ):


        winner = comparison_result.get(
            "winner"
        )


        ranking = comparison_result.get(
            "ranking",
            []
        )


        confidence = 0.0


        reasoning = []


        alternative = None



        # -------------------------
        # Winner analysis
        # -------------------------

        if winner:


            best = next(

                (
                    item for item in ranking
                    if item.get("name") == winner
                ),

                None

            )


            if best:


                score = best.get(
                    "score",
                    0
                )


                confidence = score / 100



                strategy = best.get(
                    "strategy",
                    ""
                )



                if strategy == "thermal_efficiency":


                    reasoning.append(
                        "thermal performance is highest"
                    )


                    reasoning.append(
                        "green roof and envelope strategy supported"
                    )



                elif strategy == "maximum_daylight":


                    reasoning.append(
                        "natural daylight strategy prioritized"
                    )



                elif strategy == "maximum_privacy":


                    reasoning.append(
                        "privacy strategy prioritized"
                    )



        # -------------------------
        # Optimization feedback
        # -------------------------

        if optimization_result:


            items = optimization_result.get(
                "optimizations",
                []
            )


            for item in items:


                if item.get(
                    "reason"
                ):

                    reasoning.append(

                        item.get(
                            "reason"
                        )

                    )



        # -------------------------
        # Rules feedback
        # -------------------------

        if rule_result:


            if rule_result.get(
                "mode"
            ) == "advisory":


                reasoning.append(
                    "optional regulations evaluated"
                )



            if len(
                rule_result.get(
                    "violations",
                    []
                )
            ) == 0:


                reasoning.append(
                    "no critical regulation conflicts"
                )



        # -------------------------
        # Alternative design
        # -------------------------

        if len(ranking) > 1:


            alternative = ranking[1].get(
                "name"
            )



        return {


            "engine":
            "intelligent_design_decision_v26.5",


            "status":
            "decided",


            "decision":
            winner,


            "confidence":
            round(
                confidence,
                2
            ),


            "reasoning":
            reasoning,


            "alternative":
            alternative

        }