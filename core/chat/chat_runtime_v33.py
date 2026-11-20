# ==========================================================
# ArchitectOS Chat Runtime v33
# Intent Router Integrated Runtime
# ==========================================================


from core.chat.chat_runtime_v32 import ChatRuntimeV32
from core.llm.llm_gateway_v30 import llm_gateway



class ChatRuntimeV33:


    VERSION = "33.0"



    def __init__(self):


        self.runtime = ChatRuntimeV32()


        print(
            "💬 CHAT RUNTIME v33 ONLINE"
        )



    # ======================================================
    # LLM CHAT
    # ======================================================


    def llm_chat(
        self,
        message
    ):


        response = llm_gateway.generate(

            message,

            "chat"

        )


        return response.get(

            "response",

            ""

        )



    # ======================================================
    # RUN
    # ======================================================


    def run(
        self,
        user,
        session_id=None,
        metadata=None
    ):

        return self.runtime.run(
            user,
            session_id,
            metadata
        )




chat_runtime = ChatRuntimeV33()