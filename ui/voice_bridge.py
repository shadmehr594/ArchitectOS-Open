# ==========================================================
# ArchitectOS UI Voice Bridge v1
#
# UI -> Voice Gateway Adapter
#
# Runtime owns Intelligence
# ==========================================================


from core.voice.voice_manager import VoiceManager
from core.voice.pipeline import VoicePipeline
from core.voice.conversation_loop import VoiceConversationLoop
from core.voice.voice_gateway import VoiceGateway


class UIVoiceBridge:


    VERSION = "1.0"



    def __init__(self):


        pipeline = VoicePipeline()


        manager = VoiceManager(
            pipeline
        )


        loop = VoiceConversationLoop(
            manager
        )


        self.gateway = VoiceGateway(
            loop
        )


        print(
            "🌉 UI VOICE BRIDGE v1 ONLINE"
        )



    # ======================================================
    # CREATE
    # ======================================================


    def create_session(
        self
    ):


        return self.gateway.create_session()



    # ======================================================
    # MESSAGE
    # ======================================================


    def send(
        self,
        session_id,
        text
    ):


        return self.gateway.send(
            session_id,
            text
        )



    # ======================================================
    # CLOSE
    # ======================================================


    def close(
        self,
        session_id
    ):


        return self.gateway.close(
            session_id
        )