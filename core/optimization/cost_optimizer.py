class CostOptimizer:


    def optimize(self, model):

        cost = (
            model
            .get("management", {})
            .get("cost", {})
            .get("cost_model", {})
        )


        total = cost.get(
            "total_estimated_cost",
            0
        )


        return {

            "engine":
            "COST_OPTIMIZER_V86",


            "current_cost":
            total,


            "recommendations":[

                "Reduce material waste",

                "Optimize construction cost"

            ],


            "status":
            "COST_ANALYZED"

        }