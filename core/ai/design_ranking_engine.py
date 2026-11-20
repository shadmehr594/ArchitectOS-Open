class DesignRankingEngine:


    def __init__(self):

        self.engine = (
            "ARCHITECTOS_DESIGN_RANKING_ENGINE_V93"
        )



    # ==========================================
    # V93 ORIGINAL
    # ==========================================
    def evaluate(
        self,
        designs
    ):


        ranked = []


        for name, design in designs.items():


            cost = design.get(
                "cost",
                0
            )


            columns = design.get(
                "columns",
                0
            )


            score = 100


            if cost > 0:

                score -= (
                    cost / 100000
                ) * 20


            score -= (
                columns / 100
            ) * 10



            ranked.append(

                {

                    "design":
                    name,


                    "cost":
                    cost,


                    "columns":
                    columns,


                    "score":
                    round(
                        score,
                        2
                    )

                }

            )



        ranked.sort(

            key=lambda x:
            x["score"],

            reverse=True

        )


        return {


            "engine":
            self.engine,


            "ranking":
            ranked,


            "best_design":
            ranked[0]["design"]
            if ranked
            else None,


            "status":
            "RANKING_COMPLETED"

        }



    # ==========================================
    # V98 COMPATIBILITY API
    # rank(model, optimized_model)
    # ==========================================
    def rank(
        self,
        original_model,
        optimized_model
    ):


        designs = {


            "original":
            {

                "cost":
                original_model.get(
                    "management",
                    {}
                )
                .get(
                    "cost",
                    {}
                )
                .get(
                    "cost_model",
                    {}
                )
                .get(
                    "total_estimated_cost",
                    0
                ),


                "columns":
                original_model.get(
                    "engineering",
                    {}
                )
                .get(
                    "structure",
                    {})
                .get(
                    "statistics",
                    {}
                )
                .get(
                    "column_count",
                    0
                )

            },


            "optimized":
            {

                "cost":
                optimized_model.get(
                    "management",
                    {}
                )
                .get(
                    "cost",
                    {}
                )
                .get(
                    "cost_model",
                    {}
                )
                .get(
                    "total_estimated_cost",
                    0
                ),


                "columns":
                optimized_model.get(
                    "engineering",
                    {}
                )
                .get(
                    "structure",
                    {})
                .get(
                    "statistics",
                    {}
                )
                .get(
                    "column_count",
                    0
                )

            }

        }


        return self.evaluate(
            designs
        )