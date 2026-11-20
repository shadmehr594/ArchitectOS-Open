# ==========================================================
# ArchitectOS Cognition Manager v1.2
# ==========================================================


from core.cognition.normalizer import normalizer
from core.cognition.intent_engine import intent_engine
from core.cognition.planner import planner



class CognitionManager:


    def __init__(self):

        print(
            "🧠 Cognition Manager v1.2 ACTIVE"
        )



    def analyze(
        self,
        message
    ):


        normalized = normalizer.normalize(
            message
        )


        intent = intent_engine.analyze(
            normalized
        )



        if intent.intent in [

            "chat",

            "image_generation"

        ]:


            return {

                "normalized":
                    normalized,

                "intent":
                    intent,

                "plan":
                    None

            }



        plan = planner.create_plan(
            intent
        )


        return {

            "normalized":
                normalized,

            "intent":
                intent,

            "plan":
                plan

        }



cognition_manager = CognitionManager()