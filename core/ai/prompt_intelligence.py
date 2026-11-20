# ==========================================================
# ArchitectOS Prompt Intelligence v73
# Intent Understanding Layer
# Clean Prompt Separation Edition
# ==========================================================


class PromptIntelligence:


    def __init__(self):

        print(
            "🧠 Prompt Intelligence v73 ACTIVE"
        )



    # ======================================================
    # PROMPT ENHANCEMENT
    # ======================================================

    def enhance(
        self,
        user_prompt,
        intent=None,
        context=None
    ):


        # ==================================================
        # IMAGE GENERATION
        # ==================================================

        if intent == "image_generation":


            return {

                "intent": "new_build",

                "user_request":
                    user_prompt.strip(),

                "constraints": [

                    "new building",
                    "architectural visualization"

                ]

            }



        # ==================================================
        # FACADE EDIT
        # ==================================================

        elif intent == "facade_edit":


            return {

                "intent": "renovation",

                "user_request":
                    user_prompt.strip(),

                "constraints": [

                    "preserve geometry",
                    "preserve structure"

                ]

            }



        # ==================================================
        # FALLBACK
        # ==================================================

        return {


            "intent":

                "general",


            "user_request":

                user_prompt.strip()


        }





# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


prompt_intelligence = PromptIntelligence()