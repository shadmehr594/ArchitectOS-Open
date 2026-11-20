# ==========================================================
# ArchitectOS Voice Conversation Loop v1
#
# Continuous Voice Interaction Layer
#
# STT -> VoiceManager -> Runtime v38 -> TTS
#
# Runtime owns Intelligence
# ==========================================================


class VoiceConversationLoop:


    VERSION = "1.0"



    def __init__(
        self,
        voice_manager,
        tts=None
    ):


        self.voice_manager = voice_manager
        self.tts = tts

        self.running = False


        print(
            "🔁 VOICE CONVERSATION LOOP v1 ONLINE"
        )



    # ======================================================
    # START LOOP
    # ======================================================


    def start(
        self
    ):


        self.running = True


        session = self.voice_manager.start_session()


        return {

            "status": "started",

            "session": session

        }



    # ======================================================
    # PROCESS SINGLE TURN
    # ======================================================


    def process(
        self,
        text
    ):


        if not self.running:

            return {

                "error": "voice loop inactive"

            }



        result = self.voice_manager.process(
            text
        )



        if self.tts:


            output = result.get(
                "result",
                result
            )


            self.tts.execute(
                str(output)
            )



        return result



    # ======================================================
    # STOP LOOP
    # ======================================================


    def stop(
        self
    ):


        self.running = False


        session = self.voice_manager.close_session()


        return {

            "status": "stopped",

            "session": session

        }