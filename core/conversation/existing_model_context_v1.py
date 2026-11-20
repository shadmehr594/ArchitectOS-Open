# ==========================================================
# EXISTING MODEL CONVERSATION CONTEXT V1
# ARCHITECTOS CONVERSATION BRIDGE
# ==========================================================


class ExistingModelConversationContextV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "💬 Existing Model Conversation Context v1.0 ACTIVE"
        )



    # ======================================================
    # BUILD CONVERSATION CONTEXT
    # ======================================================


    def build(
        self,
        architectural_context
    ):


        context = {


            "existing_model":

                True,


            "building_type":

                architectural_context.get(
                    "building_type"
                ),


            "architectural_intent":

                architectural_context.get(
                    "architectural_intent"
                ),


            "architectural_goal":

                architectural_context.get(
                    "architectural_goal"
                ),


            "target":

                architectural_context.get(
                    "target"
                ),


            "confidence":

                architectural_context.get(
                    "confidence",
                    0
                )

        }



        return {


            "engine":

                "EXISTING_MODEL_CONVERSATION_CONTEXT_V1",


            "version":

                self.VERSION,


            "conversation_context":

                context,


            "ready":

                True

        }