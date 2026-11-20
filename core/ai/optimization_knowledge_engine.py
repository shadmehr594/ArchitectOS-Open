class OptimizationKnowledgeEngine:


    def __init__(self):

        self.engine = (
            "ARCHITECTOS_OPTIMIZATION_KNOWLEDGE_ENGINE_V92"
        )

        self.knowledge = []



    # ==========================================
    # V92 ORIGINAL
    # ==========================================
    def extract(
        self,
        experiences
    ):


        for item in experiences:


            changes = item.get(
                "changes",
                []
            )


            if changes:

                knowledge_item = {

                    "pattern":
                    "successful_optimization",


                    "actions":
                    changes,


                    "confidence":
                    0.9

                }


                self.knowledge.append(
                    knowledge_item
                )



        return {

            "engine":
            self.engine,


            "knowledge_count":
            len(self.knowledge),


            "knowledge":
            self.knowledge,


            "status":
            "KNOWLEDGE_CREATED"

        }



    # ==========================================
    # V98 COMPATIBILITY API
    # create(learning_result)
    # ==========================================
    def create(
        self,
        learning_result
    ):


        if isinstance(
            learning_result,
            dict
        ):

            experiences = [

                {

                    "changes":
                    learning_result.get(
                        "recommendations",
                        []
                    )

                }

            ]

        else:

            experiences = []



        return self.extract(
            experiences
        )



    def query(self):

        return {

            "engine":
            self.engine,


            "knowledge":
            self.knowledge,


            "count":
            len(self.knowledge)

        }