# ==========================================================
# ArchitectOS Voice Runtime Bridge v2
#
# Voice -> ChatArchitect Gateway
#
# Voice is Interface Only
# Intelligence stays in ChatArchitect
# ==========================================================


from core.app_boot import AppBoot
from core.chat.chat_architect import ChatArchitect



class VoiceRuntimeBridge:


    VERSION = "2.0"



    def __init__(self):


        self.boot = AppBoot()


        try:

            self.boot.boot()

        except Exception:

            pass



        brain = None


        try:

            brain = self.boot.get_brain()

        except Exception:

            pass



        self.chat = ChatArchitect(
            brain
        )


        print(
            "🎙️ VOICE RUNTIME BRIDGE v2 ONLINE -> ChatArchitect"
        )




    def execute(
        self,
        text
    ):


        try:


            result = self.chat.process(
                text
            )


            return result



        except Exception as e:


            return {

                "error":
                    str(e)

            }




voice_runtime_bridge = VoiceRuntimeBridge()