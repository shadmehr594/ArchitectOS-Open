# ==========================================================
# ArchitectOS API Adapter v27
# Runtime -> API Bridge
# ==========================================================


from core.chat.chat_runtime_v27 import chat_runtime



class APIAdapter:


    VERSION = "v27"



    def handle(
        self,
        payload
    ):


        user = payload.get(
            "message",
            ""
        )


        return chat_runtime.run(
            user
        )



api_adapter = APIAdapter()