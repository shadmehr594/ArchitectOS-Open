# ==========================================================
# ArchitectOS Chat Runtime v31
# LLM Connected Chat Layer
# Built on Chat Runtime v29
# ==========================================================


from core.chat.chat_runtime_v29 import ChatRuntimeV29
from core.llm.llm_gateway_v30 import llm_gateway
from config.chat_config import ChatConfig



class ChatRuntimeV31:


    VERSION = "31.0"



    def __init__(self):


        self.runtime = ChatRuntimeV29()


        print(
            "🧠 CHAT RUNTIME v31 ONLINE"
        )



    # ======================================================
    # LLM CHAT OVERRIDE
    # ======================================================


    def _llm_chat(
        self,
        message
    ):


        response = llm_gateway.generate(

            message,

            "chat"

        )


        return response.get(

            "response",

            ""

        )



    # ======================================================
    # RUN
    # ======================================================


    def run(
        self,
        user,
        session_id=None,
        metadata=None
    ):


        # ----------------------------------------------
        # NORMAL CHAT
        # ----------------------------------------------

        if self.is_chat(

            user

        ):


            return {


                "type":

                    "chat",


                "engine":

                    ChatConfig.from_env().model,


                "result":

                    self._llm_chat(

                        user

                    ),


                "metadata":

                    {

                        "runtime_version":

                            self.VERSION,


                        "llm":

                            ChatConfig.from_env().model

                    },


                "status":

                    "LLM_CHAT"

            }



        # ----------------------------------------------
        # DESIGN / IMAGE
        # PASS TO v29
        # ----------------------------------------------


        return self.runtime.run(

            user,

            session_id,

            metadata

        )



    # ======================================================
    # SIMPLE CHAT DETECTOR
    # ======================================================


    def is_chat(
        self,
        text
    ):


        keywords = [

            "سلام",
            "hello",
            "hi",
            "خوبی",
            "کی هستی",
            "اسمت"

        ]


        for k in keywords:

            if k in text.lower():

                return True


        return False





# ==========================================================
# SINGLETON
# ==========================================================


chat_runtime = ChatRuntimeV31()