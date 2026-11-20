class DesignComparisonEngine:


    def __init__(self):

        print(
            "📊 Design Comparison Engine v26.4 ACTIVE"
        )


    def compare(
        self,
        variants,
        criteria=None
    ):


        if criteria is None:

            criteria = {

                "daylight":30,

                "energy":30,

                "privacy":20,

                "regulation":20

            }



        results = []


        for variant in variants:


            base_score = variant.get(
                "score",
                0
            )


            strategy = variant.get(
                "strategy",
                ""
            )


            bonus = 0


            # Strategy evaluation

            if strategy == "maximum_daylight":

                bonus += 2


            elif strategy == "maximum_privacy":

                bonus += 0


            elif strategy == "thermal_efficiency":

                bonus += 3



            final_score = (
                base_score
                +
                bonus
            )


            if final_score > 100:

                final_score = 100



            results.append(

                {

                    "name":
                    variant.get(
                        "name"
                    ),


                    "strategy":
                    strategy,


                    "score":
                    final_score

                }

            )



        ranking = sorted(

            results,

            key=lambda x:
            x["score"],

            reverse=True

        )



        for index, item in enumerate(
            ranking
        ):

            item["rank"] = index + 1



        return {


            "engine":
            "design_comparison_v26.4",


            "status":
            "compared",


            "criteria":
            criteria,


            "ranking":
            ranking,


            "winner":
            ranking[0]["name"]
            if ranking
            else None

        }