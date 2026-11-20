import time
from core.voice_pipeline import VoicePipeline


class VoiceAgent:

    def __init__(self, wake_word, pipeline):

        self.wake_word = wake_word.lower()
        self.pipeline = pipeline
        self.active = False

    def listen_loop(self):

        print("🎤 Voice Agent Started... Say wake word")

        while True:

            speech = self.pipeline.stt.execute(None)

            if "error" in speech:
                continue

            text = speech["text"].lower()
            print("👂 Heard:", text)

            # 🧠 Wake word detection
            if self.wake_word in text:
                self.active = True
                print("🔥 Wake word detected!")

                result = self.pipeline.run()

                print("🤖 Response ready:", result["output"])

                self.active = False

            time.sleep(0.5)