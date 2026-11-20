class TextToSpeechTool:

    def execute(self, text):

        try:
            print("🔊:", text)
            return True

        except Exception as e:
            print("TTS ERROR:", e)
            return False