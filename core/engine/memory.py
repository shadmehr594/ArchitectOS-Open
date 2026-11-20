# ==========================================================
# ArchitectOS Design Memory Engine v1.0
# Design Evolution Memory + Chat Compatibility
# ==========================================================


class DesignMemory:


    def __init__(self):

        self.memory = []

        self.chat_memory = []



    # ==================================================
    # DESIGN MEMORY
    # ==================================================

    def store(
        self,
        design,
        score
    ):

        self.memory.append({

            "design":
                design,

            "score":
                score

        })


        self.memory = self.memory[-20:]



    def recent(self):

        return self.memory[-5:]



    # ==================================================
    # CHAT MEMORY COMPATIBILITY
    # ==================================================

    def save(
        self,
        text,
        output
    ):

        self.chat_memory.append({

            "input":
                text,

            "output":
                output

        })


        self.chat_memory = self.chat_memory[-50:]



    def search(
        self,
        query
    ):

        query = (
            query
            or ""
        ).lower()


        results = []


        for item in self.chat_memory:


            if query in item.get(
                "input",
                ""
            ).lower():


                results.append(
                    item
                )


        return results