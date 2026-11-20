# ==========================================================
# ArchitectOS Task Manager v4
# Task Orchestration Layer
# Memory + Context Separation
# ==========================================================


from core.managers.memory_manager import memory_manager
from core.managers.context_manager import context_manager



class TaskManager:


    def __init__(self):

        print(
            "📋 Task Manager v4 ACTIVE"
        )



    # ======================================================
    # PROCESS MESSAGE
    # ======================================================

    def process_message(
        self,
        message
    ):


        # ------------------------------
        # User Memory
        # ------------------------------

        user_memory = memory_manager.process(
            message
        )


        # ------------------------------
        # Conversation Context
        # ------------------------------

        context = context_manager.build(
            message
        )


        return {

            "status":
                "ok",


            "memory":
                user_memory,


            "context":
                context

        }



    # ======================================================
    # SAVE RESPONSE
    # ======================================================

    def save_response(
        self,
        message,
        response
    ):


        context_manager.save(
            message,
            response
        )



    # ======================================================
    # USER
    # ======================================================

    def get_user(
        self
    ):

        return memory_manager.get_user()



# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


task_manager = TaskManager()