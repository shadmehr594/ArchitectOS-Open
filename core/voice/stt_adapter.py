# ==========================================================
# ArchitectOS STT Adapter v1
# Speech To Text Interface
# ==========================================================


class STTAdapter:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🎤 STT ADAPTER v1 ONLINE"
        )


    # ======================================================
    # EXECUTE
    # ======================================================

    def execute(
        self,
        audio=None
    ):


        """
        Future:
        - Whisper
        - Faster Whisper
        - OpenAI Whisper API
        - Local model
        """

        if audio is None:

            return None


        if isinstance(audio, str):

            return audio


        return None