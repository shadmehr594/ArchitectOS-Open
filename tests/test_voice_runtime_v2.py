# ==========================================================
# ArchitectOS Voice Runtime v2 E2E Test
# ==========================================================


from core.voice.pipeline import VoicePipeline



class FakeSTT:


    def __init__(self, text):

        self.text = text


    def execute(self, _):

        return self.text



class FakeTTS:


    def execute(self, text):

        print(
            "🔊 TTS OUTPUT:",
            text
        )



def run_test(message):


    print(
        "\n🎙️ TEST INPUT:",
        message
    )


    pipeline = VoicePipeline(

        stt=FakeSTT(message),

        tts=FakeTTS()

    )


    # activate wake mode

    pipeline.active = True


    result = pipeline.run_once()


    print(
        "\n✅ RESULT:"
    )

    print(result)



if __name__ == "__main__":


    run_test(
        "اسم من چیه؟"
    )


    run_test(
        "یک ویلای مدرن طراحی کن"
    )