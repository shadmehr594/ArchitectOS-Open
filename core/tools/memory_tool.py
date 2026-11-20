# ==========================================================
# ArchitectOS Memory Tool v3
# Unified Recall + Save Layer
# Compatible with GOD CORE v21.7
# ==========================================================


from core.tools.base import BaseTool



class MemoryTool(BaseTool):


    name = "memory"



    def __init__(
        self,
        memory
    ):

        self.memory = memory



    # ======================================================
    # EXECUTE
    # ======================================================

    def execute(
        self,
        text,
        context=None
    ):


        if context is None:
            context = {}



        # ----------------------------------------------
        # NORMALIZE INPUT
        # ----------------------------------------------

        if isinstance(
            text,
            dict
        ):

            query = (

                text.get("query")

                or

                text.get("text")

                or

                ""

            )


        else:

            query = text or ""



        query = str(query)



        lower = query.lower()



        # ==================================================
        # RECALL REQUEST DETECTION
        # ==================================================

        recall_words = [

            "یادته",

            "میدونی",

            "می‌دونی",

            "من کی هستم",

            "اطلاعات من",

            "remember",

            "recall",

            "who am i",

            "what do you know"

        ]



        if any(
            item in lower
            for item in recall_words
        ):


            result = self.memory.recall_everything(

                query

            )


            return {


                "type":

                    "memory",


                "operation":

                    "recall",


                "output":

                    result


            }



        # ==================================================
        # SAVE
        # ==================================================


        self.memory.save_conversation(

            query,

            "user"

        )


        return {


            "type":

                "memory",


            "operation":

                "save",


            "output":

                "memory saved"


        }