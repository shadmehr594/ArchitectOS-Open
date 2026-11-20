# ==========================================================
# ArchitectOS Context Recall Engine v25
# Unified Memory Query Intelligence
# ==========================================================



class ContextRecall:



    def __init__(
        self,
        memory_manager
    ):

        self.memory = memory_manager



    # ======================================================
    # MAIN RECALL
    # ======================================================

    def recall(
        self,
        text
    ):


        return self.memory.recall_everything(

            text

        )



# ==========================================================
# FACTORY
# ==========================================================


def create_context_recall(

    memory_manager

):


    return ContextRecall(

        memory_manager

    )