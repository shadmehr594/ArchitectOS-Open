class VoicePipeline:

    def __init__(self, stt_tool, brain, tts_tool):

        self.stt = stt_tool
        self.brain = brain
        self.tts = tts_tool

    def run(self):

        # 🎤 listen
        speech = self.stt.execute(None)

        if "error" in speech:
            return speech

        text = speech["text"]
        print("🧠 Input:", text)

        # 🤖 brain
        result = self.brain.run(text)

        # 🔊 output text
        output = self._extract_output(result)

        # speak
        self.tts.execute(output)

        return {
            "input": text,
            "output": output,
            "full": result
        }

    def _extract_output(self, result):

        if result.get("tool_result"):
            return str(result["tool_result"])

        if result.get("graph"):
            return "BIM design generated successfully"

        return "Done"