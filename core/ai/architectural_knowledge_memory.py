class ArchitecturalKnowledgeMemory:


    def __init__(self):

        print(
            "🧠 Architectural Knowledge Memory Engine v26.6 ACTIVE"
        )


        self.memory = []



    def learn(
        self,
        project
    ):


        record = {


            "site":
            project.get(
                "site"
            ),


            "floors":
            project.get(
                "floors"
            ),


            "strategy":
            project.get(
                "strategy"
            ),


            "winner":
            project.get(
                "winner"
            ),


            "score":
            project.get(
                "score",
                0
            )

        }


        self.memory.append(
            record
        )


        return {


            "engine":
            "architectural_memory_v26.6",


            "status":
            "learned",


            "stored":
            record,


            "memory_size":
            len(
                self.memory
            )

        }



    def recall(
        self,
        site=None,
        floors=None
    ):


        matches = []


        for item in self.memory:


            if site is not None:


                if item.get(
                    "site"
                ) != site:

                    continue



            if floors is not None:


                if item.get(
                    "floors"
                ) != floors:

                    continue



            matches.append(
                item
            )



        recommendation = None



        if matches:


            best = max(

                matches,

                key=lambda x:
                x.get(
                    "score",
                    0
                )

            )


            recommendation = {


                "strategy":
                best.get(
                    "strategy"
                ),


                "confidence":
                round(
                    best.get(
                        "score",
                        0
                    )
                    /
                    100,

                    2
                )

            }



        return {


            "engine":
            "architectural_memory_v26.6",


            "status":
            "recalled",


            "matches":
            matches,


            "recommendation":
            recommendation

        }