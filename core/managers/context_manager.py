# ==========================================================
# ArchitectOS Context Manager v1
# Conversation Context Layer
# ==========================================================


from memory.memory_brain import MemoryBrain



class ContextManager:


    def __init__(self):

        print(
            "🧠 Context Manager v1 ACTIVE"
        )


        self.context = MemoryBrain(
            path="memory/chat_context.json"
        )



    # ======================================================
    # BUILD CONTEXT
    # ======================================================

    def build(
        self,
        message
    ):

        return self.context.build_context(
            message
        )



    # ======================================================
    # SAVE MESSAGE
    # ======================================================

    def save(
        self,
        message,
        response
    ):

        self.context.save(
            message,
            response
        )



# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


context_manager = ContextManager()