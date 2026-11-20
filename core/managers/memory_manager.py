# ==========================================================
# ArchitectOS Memory Manager v2
# User Memory + Conversation Context + Persistence
# ==========================================================


from core.memory.memory_extractor import memory_extractor
from core.memory.user_memory import user_memory

from memory.memory_brain import MemoryBrain



class MemoryManager:


    def __init__(self):

        print(
            "🧠 Memory Manager v2 ACTIVE"
        )


        self.chat_memory = MemoryBrain(
            path="memory/chat_context.json"
        )



    # ======================================================
    # PROCESS USER MESSAGE
    # ======================================================

    def process(
        self,
        message
    ):


        facts = memory_extractor.extract(
            message
        )


        if facts:

            user_memory.update(
                facts
            )


            print(
                "🧠 USER MEMORY UPDATED:",
                facts
            )


        return user_memory.all()



    # ======================================================
    # GET USER PROFILE
    # ======================================================

    def get_user(
        self
    ):


        return user_memory.all()



    # ======================================================
    # GET FULL MEMORY CONTEXT
    # ======================================================

    def get_memory_context(
        self,
        message
    ):


        return {

            "user":

                user_memory.all(),


            "conversation":

                self.chat_memory.build_context(
                    message
                )

        }



    # ======================================================
    # GET CHAT CONTEXT ONLY
    # ======================================================

    def get_context(
        self,
        message
    ):


        return self.chat_memory.build_context(
            message
        )



    # ======================================================
    # SAVE CHAT
    # ======================================================

    def save_chat(
        self,
        message,
        response
    ):


        self.chat_memory.save(
            message,
            response
        )



# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


memory_manager = MemoryManager()