# ==========================================================
# ArchitectOS Voice TTS Adapter v1
# Runtime Response Cleaner
# ==========================================================


class TTSAdapter:


    VERSION = "1.0"


    def __init__(self, tts_engine=None):

        self.tts_engine = tts_engine

        print(
            "🔊 TTS ADAPTER v1 ONLINE"
        )


    def extract_text(self, result):


        if not result:

            return "متوجه نشدم."


        if isinstance(result, dict):


            if "result" in result:

                inner = result["result"]

                if isinstance(inner, dict):

                    if "output" in inner:

                        return str(
                            inner["output"]
                        )


            if "output" in result:

                return str(
                    result["output"]
                )


        return str(result)



    def execute(self, result):


        text = self.extract_text(
            result
        )


        print(
            "🔊 TTS:",
            text
        )


        if self.tts_engine:

            return self.tts_engine.execute(
                text
            )


        return text