# ==========================================================
# ArchitectOS Cognitive Router v67.7
# User Input -> Cognition Pipeline
# ==========================================================


from core.cognition.normalizer import normalizer
from core.cognition.intent_engine import intent_engine
from core.cognition.planner import planner
from core.cognition.runtime_dispatcher import runtime_dispatcher



class CognitiveRouter:


    def __init__(self):

        print(
            "🧠 Cognitive Router v67.7 ACTIVE"
        )



    # ======================================================
    # PROCESS USER REQUEST
    # ======================================================

    def process(
        self,
        user_input
    ):


        print(
            "👤 USER:",
            user_input
        )



        # -----------------------------------------------
        # Normalize
        # -----------------------------------------------

        normalized = normalizer.normalize(
            user_input
        )



        # -----------------------------------------------
        # Intent
        # -----------------------------------------------

        intent = intent_engine.analyze(
            normalized
        )



        # -----------------------------------------------
        # Plan
        # -----------------------------------------------

        plan = planner.create_plan(
            intent
        )



        return {

            "input":
                user_input,


            "normalized":
                normalized,


            "intent":
                intent,


            "plan":
                plan

        }



# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


router = CognitiveRouter()