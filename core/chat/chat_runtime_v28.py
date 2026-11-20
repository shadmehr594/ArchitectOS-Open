# ==========================================================
# ArchitectOS Chat Runtime v28
# Response Guard Integration Layer
# Unified Runtime Wrapper
# ==========================================================


from core.chat.chat_runtime_v27 import ChatRuntimeV27
from core.app_boot import AppBoot
from core.chat.response_guard import response_guard
from core.chat.runtime_response import RuntimeResponse



class ChatRuntimeV28:


    VERSION = "28.0"



    def __init__(self):


        self.architect = AppBoot()


        self.runtime = ChatRuntimeV27(

            self.architect

        )


        print(
            "💬 CHAT RUNTIME v28 ONLINE"
        )



    # ======================================================
    # RUN
    # ======================================================

    def run(
        self,
        user
    ):


        result = self.runtime.run(

            user

        )


        if not isinstance(

            result,

            dict

        ):


            result = {


                "type":

                    "chat",


                "engine":

                    "runtime",


                "result":

                    result,


                "status":

                    "success"


            }




        # ==================================================
        # RESPONSE GUARD v4
        # ONLY TEXT CHAT MODE
        # ==================================================

        if result.get(

            "type"

        ) == "chat":


            guarded = response_guard.apply(

                user,

                result.get(

                    "result",

                    ""

                )

            )


            result["result"] = guarded.get(

                "response",

                result.get(

                    "result"

                )

            )


            result["guard"] = {


                "version":

                    response_guard.VERSION,


                "status":

                    guarded.get(

                        "status",

                        "unknown"

                    ),


                "input_language":

                    guarded.get(

                        "input_language"

                    ),


                "output_language":

                    guarded.get(

                        "output_language"

                    )

            }



        else:


            # Design / Image / Tool responses

            result["guard"] = {


                "version":

                    response_guard.VERSION,


                "status":

                    "bypass_non_text",


                "input_language":

                    None,


                "output_language":

                    None

            }




        # ==================================================
        # RESPONSE CONTRACT
        # ==================================================

        return RuntimeResponse(


            response_type=result.get(

                "type",

                "chat"

            ),


            engine=result.get(

                "engine",

                "chat_runtime"

            ),


            result=result.get(

                "result"

            ),


            metadata={


                "runtime_version":

                    self.VERSION,


                "guard":

                    result.get(

                        "guard"

                    )


            },


            status=result.get(

                "status",

                "success"

            )

        ).json()





# ==========================================================
# SINGLETON
# ==========================================================


chat_runtime = ChatRuntimeV28()