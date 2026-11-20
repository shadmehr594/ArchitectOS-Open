# ==========================================================
# ArchitectOS Chat Cognitive Bridge v67.8
# ChatOS -> Cognitive Router
# ==========================================================


from core.cognition.cognitive_router import router



class ChatCognitiveBridge:


    def __init__(self):

        print(
            "💬 Chat Cognitive Bridge v67.8 ACTIVE"
        )



    # ======================================================
    # HANDLE MESSAGE
    # ======================================================

    def process_message(
        self,
        message
    ):


        result = router.process(
            message
        )


        plan = result.get(
            "plan"
        )


        return {


            "type":
                "cognitive_response",


            "message":
                message,


            "intent":
                result.get(
                    "intent"
                ),


            "execution_plan":
                plan,


            "ready":
                True

        }



# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


chat_cognitive_bridge = ChatCognitiveBridge()