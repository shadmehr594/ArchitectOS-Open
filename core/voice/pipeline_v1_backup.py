from core.voice.wake_word import WakeWordDetector
from core.voice.voice_router import VoiceRouter


class VoicePipeline:

    def __init__(self, stt, brain, tts, registry):

        self.stt = stt
        self.tts = tts

        self.wake = WakeWordDetector()
        self.router = VoiceRouter(registry, brain)

        self.active = False

    def run_once(self):

        try:
            text = self.stt.execute(None)

            if not text:
                return "silent"

            # 🧠 WAKE WORD MODE
            if not self.active:

                if self.wake.detect(text):
                    self.active = True
                    return "🎤 Wake word detected"

                return "waiting for wake word"

            # 🧠 ACTIVE MODE
            result = self.router.route(text)

            self.tts.execute(str(result))

            # reset after command
            self.active = False

            return result

        except Exception as e:
            self.active = False
            return f"VOICE ERROR: {e}"