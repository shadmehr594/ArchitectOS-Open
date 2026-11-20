# ==========================================================
# ArchitectOS Chat Runtime v32
# Universal Runtime Pipeline Wrapper
# Built on v31 + v29 Core
#
# v32 Responsibilities:
# - Runtime compatibility layer
# - Preserve v29 output contract
# - Debug output visibility
# ==========================================================


from core.chat.chat_runtime_v29 import ChatRuntimeV29



class ChatRuntimeV32:


    VERSION = "32.0"



    def __init__(self):


        self.runtime = ChatRuntimeV29()


        print(
            "💬 CHAT RUNTIME v32 ONLINE"
        )



    # ======================================================
    # MAIN RUN
    # Runtime Bridge Only
    # ======================================================


    def run(
        self,
        user,
        session_id=None,
        metadata=None
    ):


        result = self.runtime.run(

            user,

            session_id,

            metadata

        )


        # ==================================================
        # DEBUG OUTPUT
        # Keep until render path is verified
        # ==================================================

        print(
            "🔥 CHAT RUNTIME v32 RESULT:"
        )

        print(
            result
        )


        return result





# ==========================================================
# SINGLETON
# ==========================================================


chat_runtime = ChatRuntimeV32()