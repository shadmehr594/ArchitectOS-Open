# ==========================================================
# ArchitectOS Voice Manager v2
#
# Voice Session Controller
#
# STT -> Voice Session -> Pipeline -> Runtime -> TTS
#
# Runtime owns Intelligence
# ==========================================================


from core.voice.voice_session import VoiceSession



class VoiceManager:


    VERSION = "2.0"



    def __init__(
        self,
        pipeline=None
    ):


        self.pipeline = pipeline


        self.session = VoiceSession()


        print(
            "🎙️ VOICE MANAGER v2 ONLINE"
        )



    # ======================================================
    # START SESSION
    # ======================================================


    def start_session(
        self
    ):


        return self.session.start()



    # ======================================================
    # PROCESS VOICE TEXT
    # ======================================================


    def process(
        self,
        text
    ):


        try:


            if not self.session.active:

                self.session.start()



            result = self.pipeline.run_text(
                text
            )


            state = self.session.update(
                text,
                result
            )


            return {

                "session": state,

                "result": result

            }



        except Exception as e:


            return {

                "error": str(e)

            }



    # ======================================================
    # SESSION STATE
    # ======================================================


    def get_state(
        self
    ):


        return self.session.state()



    # ======================================================
    # CLOSE
    # ======================================================


    def close_session(
        self
    ):


        return self.session.close()