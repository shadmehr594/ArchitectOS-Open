# ==========================================================
# ArchitectOS Context Injector v26
# Memory -> Brain Cognitive Context Bridge
# Stable Runtime Integration
# ==========================================================


class ContextInjector:


    VERSION = "v26"



    def __init__(
        self,
        memory_manager
    ):

        self.memory = memory_manager


        print(
            "🧠 Context Injector v26 ACTIVE"
        )



    # ======================================================
    # BUILD CONTEXT
    # ======================================================

    def build(
        self,
        query
    ):


        history = []


        user_context = None



        try:

            user_context = (
                self.memory.recall_user()
            )

        except Exception:

            user_context = {}



        try:

            history = (
                self.memory.get_history(
                    10
                )
            )

        except Exception:

            history = []




        return {


            "query":

                query,



            "user":

                user_context,



            "history":

                history


        }



    # ======================================================
    # INJECT INTO BRAIN
    # ======================================================

    def inject(
        self,
        query
    ):


        context = self.build(
            query
        )


        return {


            "memory_context":

                context


        }



    # ======================================================
    # SIMPLE CONTEXT ACCESS
    # ======================================================

    def get(
        self,
        query
    ):


        return self.inject(
            query
        )