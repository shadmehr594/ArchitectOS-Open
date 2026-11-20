class PromptContextAdapter:

    VERSION = "1.0"


    def __init__(self):

        print(
            "🧠 PROMPT CONTEXT ADAPTER v1.0 ONLINE"
        )


    def adapt(
        self,
        prompt_context
    ):


        architectural_context = (
            prompt_context.get(
                "architectural_context",
                {}
            )
        )


        return {

            "architectural_intent":
                architectural_context,


            "prompt":
                prompt_context.get(
                    "prompt_context",
                    ""
                ),


            "camera":
                prompt_context.get(
                    "camera"
                ),


            "mood":
                prompt_context.get(
                    "mood"
                ),


            "metadata":
            {

                "engine":
                    "PromptContextAdapter",


                "version":
                    self.VERSION

            }

        }