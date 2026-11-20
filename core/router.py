# ==========================================================
# ArchitectOS Router v3
# Entry Gateway
# ==========================================================

from core.cognition.intent_engine import intent_engine


class Router:


    VERSION = "3.0"


    def __init__(self):

        print(
            "🧭 Router v3 ACTIVE"
        )


    def route(
        self,
        text,
        image=None,
        context=None
    ):


        result = intent_engine.analyze(
            {
                "text": text,
                "image": image,
                "context": context or {}
            }
        )


        return {

            "intent":
                result.intent,

            "confidence":
                result.confidence,

            "source":
                result.source

        }