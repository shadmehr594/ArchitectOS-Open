# ==========================================================
# ArchitectOS Prompt Specification v69.3
# Unified Prompt Object
# ==========================================================


class PromptSpecification:

    def __init__(

        self,

        positive,

        negative,

        runtime,

        engine="flux"

    ):

        self.positive = positive

        self.negative = negative

        self.runtime = runtime

        self.engine = engine

    # ======================================================

    def to_dict(self):

        return {

            "positive": self.positive,

            "negative": self.negative,

            "runtime": self.runtime,

            "engine": self.engine

        }

    # ======================================================

    def __repr__(self):

        return str(

            self.to_dict()

        )