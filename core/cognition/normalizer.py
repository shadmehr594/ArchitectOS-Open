# ==========================================================
# ArchitectOS Normalizer Engine v67.3
# Input Cleaning Layer
#
# PHASE 2D-1: this module is now a thin compatibility adapter over the
# single canonical normalization implementation
# (core.cognition.persian_normalizer).  Its public contract is unchanged:
#
#   normalize(text) -> {"original", "normalized", "language", "tokens"}
#
# No normalization logic is duplicated here.
# ==========================================================


from core.cognition.persian_normalizer import (
    persian_normalizer,
)


class Normalizer:


    def __init__(self):

        print(
            "🧹 Normalizer Engine v67.3 ACTIVE (canonical delegate)"
        )


    # ======================================================
    # LANGUAGE DETECTION
    # ======================================================
    # Legacy contract: "fa" / "en".  Canonical detector may also return
    # "mixed" / "unknown"; those collapse to "fa" when Persian is present,
    # otherwise "en" (preserving the legacy two-value contract).
    # ======================================================

    def detect_language(
        self,
        text
    ):

        language = persian_normalizer.detect_language(
            text
        )

        if language in ("fa", "mixed"):

            return "fa"


        return "en"


    # ======================================================
    # CLEAN TEXT
    # ======================================================

    def clean(
        self,
        text
    ):

        return persian_normalizer.normalize(
            text
        )["normalized_text"]


    # ======================================================
    # TOKENIZE
    # ======================================================

    def tokenize(
        self,
        text
    ):


        return text.split()


    # ======================================================
    # NORMALIZE
    # ======================================================

    def normalize(
        self,
        text
    ):


        request = persian_normalizer.normalize(
            text
        )


        cleaned = request["normalized_text"]


        return {

            "original":
                request["raw_text"],


            "normalized":
                cleaned.lower(),


            "language":
                self.detect_language(
                    request["raw_text"]
                ),


            "tokens":
                self.tokenize(
                    cleaned
                )

        }


# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


normalizer = Normalizer()
