# ==========================================================
# ArchitectOS Intent Result v68
# Unified Intent Object
# ==========================================================


class IntentResult:


    def __init__(
        self,
        intent="unknown",
        confidence=0.0,
        source="unknown",
        metadata=None
    ):


        self.intent = intent

        self.confidence = confidence

        self.source = source

        self.metadata = metadata or {}



    def to_dict(
        self
    ):


        return {

            "intent":
                self.intent,

            "confidence":
                self.confidence,

            "source":
                self.source,

            "metadata":
                self.metadata

        }



    def __repr__(
        self
    ):


        return str(
            self.to_dict()
        )