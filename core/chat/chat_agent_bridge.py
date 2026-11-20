# ==========================================================
# ArchitectOS Chat Agent Bridge v68.3
# Chat Interface -> Cognitive Agent
# ==========================================================


from core.agents.cognitive_agent import cognitive_agent



class ChatAgentBridge:


    def __init__(self):

        print(
            "💬 Chat Agent Bridge v68.3 ACTIVE"
        )



    # ======================================================
    # USER MESSAGE
    # ======================================================

    def process(
        self,
        message
    ):


        result = cognitive_agent.process(
            message
        )


        return {


            "type":
                "agent_response",


            "input":
                message,


            "agent":
                result

        }



    # ======================================================
    # USER CONFIRMATION
    # ======================================================

    def confirm(
        self,
        message
    ):


        result = cognitive_agent.confirm(
            message
        )


        return {


            "type":
                "execution_response",


            "result":
                result

        }




# ==========================================================
# INSTANCE
# ==========================================================


chat_agent_bridge = ChatAgentBridge()