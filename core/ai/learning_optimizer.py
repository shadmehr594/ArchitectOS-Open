class LearningOptimizer:


    def __init__(
        self,
        memory=None
    ):

        self.memory = memory

        self.engine = (
            "ARCHITECTOS_LEARNING_OPTIMIZER_V91"
        )



    def learn(
        self,
        model
    ):


        # ======================================
        # V98 MODE
        # learn(memory.recall())
        # ======================================
        if isinstance(model, dict):

            memories = model.get(
                "history",
                []
            )


        # ======================================
        # LEGACY MODE
        # learn(model)
        # ======================================
        elif self.memory:

            memories = (
                self.memory.recall()
                .get(
                    "history",
                    []
                )
            )

        else:

            memories = []



        recommendations = []



        for experience in memories:


            before = experience.get(
                "before",
                {}
            )


            after = experience.get(
                "after",
                {}
            )


            changes = experience.get(
                "changes",
                []
            )


            if changes:

                recommendations.extend(
                    changes
                )



        return {


            "engine":
            self.engine,


            "recommendations":
            list(
                set(
                    map(
                        str,
                        recommendations
                    )
                )
            ),


            "status":
            "LEARNING_COMPLETED"

        }