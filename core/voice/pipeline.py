# ==========================================================
# ArchitectOS Voice Pipeline v4
#
# Voice Input
#      |
#      v
# Runtime v38
#      |
#      v
# TTS
#
# Runtime owns Intelligence
# Voice is only Interface Layer
# ==========================================================


from core.voice.wake_word import WakeWordDetector

from core.voice.runtime_bridge import voice_runtime_bridge



class VoicePipeline:


    VERSION = "4.0"



    def __init__(
        self,
        stt=None,
        tts=None
    ):


        self.stt = stt

        self.tts = tts


        self.wake = WakeWordDetector()


        self.active = False


        print(
            "🎙️ VOICE PIPELINE v4 ONLINE"
        )



    # ======================================================
    # TEXT MODE
    # Used by VoiceManager / API
    # ======================================================


    def run_text(
        self,
        text
    ):


        try:


            if not text:

                return "empty input"



            print(
                "🎤 VOICE TEXT INPUT:",
                text
            )


            result = voice_runtime_bridge.execute(
                text
            )


            self._tts(
                result
            )


            return result



        except Exception as e:


            return (
                f"VOICE TEXT ERROR: {e}"
            )



    # ======================================================
    # MICROPHONE MODE
    # ======================================================


    def run_once(
        self
    ):


        try:


            if not self.stt:

                return "STT unavailable"



            text = self.stt.execute(
                None
            )



            if not text:

                return "silent"



            print(
                "🎤 VOICE INPUT:",
                text
            )



            # ------------------------------
            # Wake Word
            # ------------------------------


            if not self.active:


                if self.wake.detect(text):

                    self.active = True

                    return "Wake word detected"



                return "waiting for wake word"



            # ------------------------------
            # Runtime
            # ------------------------------


            result = voice_runtime_bridge.execute(
                text
            )


            self._tts(
                result
            )


            self.active = False


            return result



        except Exception as e:


            self.active = False


            return (
                f"VOICE PIPELINE ERROR: {e}"
            )



    # ======================================================
    # TTS HANDLER
    # ======================================================


    def _tts(
        self,
        result
    ):


        if not self.tts:

            return



        try:

            if isinstance(result, dict):

                output = (
                    result
                    .get("result", {})
                    .get("output")
                )


                if output:

                    self.tts.execute(
                        output
                    )

                    return



            self.tts.execute(
                str(result)
            )


        except Exception as e:


            print(
                "TTS ERROR:",
                e
            )