class OptimizationFeedbackEngine:


    def __init__(self):

        self.engine = (
            "ARCHITECTOS_OPTIMIZATION_FEEDBACK_ENGINE_V89"
        )


    def evaluate(
        self,
        before_model,
        after_model
    ):

        before = self.extract_metrics(
            before_model
        )


        after = self.extract_metrics(
            after_model
        )


        improvements = {}


        improvements["cost"] = (
            before["cost"]
            -
            after["cost"]
        )


        improvements["columns"] = (
            before["columns"]
            -
            after["columns"]
        )


        score = 0


        if improvements["cost"] > 0:

            score += 50


        if improvements["columns"] > 0:

            score += 25


        if score >= 50:

            status = (
                "IMPROVEMENT_ACCEPTED"
            )

        else:

            status = (
                "NO_SIGNIFICANT_IMPROVEMENT"
            )


        return {

            "engine":
            self.engine,


            "before":
            before,


            "after":
            after,


            "improvements":
            improvements,


            "score":
            score,


            "status":
            status

        }



    def extract_metrics(
        self,
        model
    ):


        columns = (

            model
            .get("engineering", {})
            .get("structure", {})
            .get("statistics", {})
            .get("column_count",0)

        )


        cost = (

            model
            .get("management", {})
            .get("cost", {})
            .get("cost_model", {})
            .get("total_estimated_cost",0)

        )


        return {

            "columns":
            columns,


            "cost":
            cost

        }