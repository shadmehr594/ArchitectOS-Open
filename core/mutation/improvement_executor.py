class ImprovementExecutor:


    def __init__(self):

        print(
            "🛠️ Improvement Executor Engine v20.3 ACTIVE"
        )


    def apply(
        self,
        design,
        improvement_plan
    ):

        if not isinstance(design, dict):
            return design


        actions = improvement_plan.get(
            "actions",
            []
        )


        applied = []


        for action in actions:

            target = action.get(
                "target"
            )

            strategy = action.get(
                "strategy"
            )


            # ==========================
            # ROOF IMPROVEMENT
            # ==========================

            if target == "roof":

                self._improve_roof(
                    design,
                    strategy
                )

                applied.append(
                    {
                        "target": target,
                        "strategy": strategy,
                        "status": "applied"
                    }
                )


            # ==========================
            # UNKNOWN ACTION
            # ==========================

            else:

                applied.append(
                    {
                        "target": target,
                        "strategy": strategy,
                        "status": "ignored"
                    }
                )


        return {

            "design": design,

            "executor":
                "improvement_executor_v20.3",

            "applied":
                applied,

            "count":
                len(applied)

        }



    def _improve_roof(
        self,
        design,
        strategy
    ):


        if "ROOF" not in design:

            design["ROOF"] = {}


        roof = design["ROOF"]


        if strategy == "increase_green_design_integration":

            roof.update(
                {
                    "green_roof": True,
                    "vegetation_level": "high",
                    "water_retention": True,
                    "sustainability_score": 1.05
                }
            )