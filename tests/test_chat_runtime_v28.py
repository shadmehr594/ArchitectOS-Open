# ==========================================================
# ArchitectOS Chat Runtime v28
# Unified Runtime Wrapper
#
# Compatible:
# AppBoot v22
# Chat Runtime v27
# ChatArchitect v26+
# Response Guard v4
#
# Core Platform Release Layer
# ==========================================================


from core.chat.chat_runtime_v27 import ChatRuntimeV27
from core.app_boot import AppBoot

from core.chat.response_guard import response_guard
from core.chat.runtime_response import RuntimeResponse



class ChatRuntimeV28:


    VERSION = "28.0"



    def __init__(
        self,
        architect=None
    ):


        # ==================================================
        # CORE INSTANCE
        # ==================================================

        if architect is None:

            self.architect = AppBoot()

        else:

            self.architect = architect



        # ==================================================
        # RUNTIME CORE
        # ==================================================

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
        user,
        context=None,
        image=None
    ):


        try:


            # Forward full context
            # to lower runtime


            result = self.runtime.run(

                user,

                context=context,

                image=image

            )



        except TypeError:


            try:


                result = self.runtime.run(

                    user,

                    context=context

                )


            except TypeError:


                result = self.runtime.run(

                    user

                )



        except Exception as e:


            result = {


                "type":

                    "error",


                "engine":

                    "chat_runtime_v28",


                "result":

                    str(e),


                "status":

                    "error"


            }




        # ==================================================
        # RESPONSE NORMALIZATION
        # ==================================================

        if not isinstance(

            result,

            dict

        ):


            result = {


                "type":

                    "chat",


                "engine":

                    "chat_runtime_v28",


                "result":

                    result,


                "status":

                    "success"


            }




        # ==================================================
        # RESPONSE GUARD v4
        # ==================================================

        try:


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



        except Exception as e:


            result["guard"] = {


                "version":

                    response_guard.VERSION,


                "status":

                    "error",


                "error":

                    str(e)

            }




        # ==================================================
        # RESPONSE CONTRACT
        # ==================================================

        response = RuntimeResponse(


            response_type=result.get(

                "type",

                "chat"

            ),



            engine=result.get(

                "engine",

                "chat_runtime_v28"

            ),



            result=result.get(

                "result"

            ),



            metadata={


                "runtime_version":

                    self.VERSION,


                "intent":

                    result.get(

                        "intent"

                    ),



                "mode":

                    result.get(

                        "mode"

                    ),



                "guard":

                    result.get(

                        "guard"

                    )

            },



            status=result.get(

                "status",

                "success"

            )

        )



        return response.json()





# ==========================================================
# SINGLETON
# ==========================================================


chat_runtime = ChatRuntimeV28()

# ==========================================================
# CHAT RUNTIME v28 ROUTING TEST
# ==========================================================


messages = [

    "سلام",

    "یک ویلای مدرن طراحی کن",

    "استخر اضافه کن",

    "تصویر بساز",

    "یادته من کی هستم"

]


for msg in messages:


    print("\n")
    print("=" * 60)
    print("USER:", msg)
    print("=" * 60)



    try:


        result = chat_runtime.run(

            msg

        )


        print(
            result
        )


    except Exception as e:


        print(
            "TEST ERROR:",
            e
        )