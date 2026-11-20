class OptimizationExecutor:


    def __init__(self):

        self.engine = (
            "ARCHITECTOS_OPTIMIZATION_EXECUTOR_V88"
        )


    def execute(
        self,
        model,
        decisions
    ):

        changes = []


        for decision in decisions:


            domain = decision.get(
                "domain"
            )


            if domain == "structure":

                result = (
                    self.optimize_structure(
                        model
                    )
                )


            elif domain == "mep":

                result = (
                    self.optimize_mep(
                        model
                    )
                )


            elif domain == "cost":

                result = (
                    self.optimize_cost(
                        model
                    )
                )


            else:

                result = {
                    "status":
                    "SKIPPED"
                }


            changes.append(result)



        return {

            "engine":
            self.engine,


            "changes":
            changes,


            "status":
            "EXECUTION_COMPLETED",


            "model":
            model

        }



    def optimize_structure(
        self,
        model
    ):


        structure = (
            model
            .get("engineering", {})
            .get("structure", {})
        )


        stats = (
            structure
            .get("statistics", {})
        )


        old_columns = stats.get(
            "column_count",
            0
        )


        # simulation of optimization

        new_columns = max(
            old_columns - 2,
            0
        )


        stats["column_count"] = (
            new_columns
        )


        return {

            "domain":
            "structure",


            "old_columns":
            old_columns,


            "new_columns":
            new_columns,


            "action":
            "column_reduction",


            "status":
            "STRUCTURE_UPDATED"

        }



    def optimize_mep(
        self,
        model
    ):


        return {

            "domain":
            "mep",


            "action":
            "routing_optimization",


            "status":
            "MEP_UPDATED"

        }



    def optimize_cost(
        self,
        model
    ):


        cost = (
            model
            .get("management", {})
            .get("cost", {})
            .get("cost_model", {})
        )


        old_cost = cost.get(
            "total_estimated_cost",
            0
        )


        new_cost = round(
            old_cost * 0.95,
            2
        )


        cost["total_estimated_cost"] = (
            new_cost
        )


        return {

            "domain":
            "cost",


            "old_cost":
            old_cost,


            "new_cost":
            new_cost,


            "status":
            "COST_UPDATED"

        }