# ==========================================================
# ArchitectOS Chat Input Adapter v1.2
# Context Image Support
# PHASE 2D-1: Deterministic Persian / Language Normalization Boundary
#
# Backward compatible:
#   normalize(message, context) still returns a dict exposing
#   "text" (now the canonical normalized form) and "image".
#
# Additive (new) fields on the returned NormalizedRequest:
#   raw_text, normalized_text, detected_language,
#   had_persian_chars, normalization_applied,
#   normalization_steps, normalization_metadata, version, contract
#
# The raw user text is NEVER destroyed.
# ==========================================================


from core.cognition.persian_normalizer import (
    NormalizedRequest,
    persian_normalizer,
)


class ChatInputAdapter:


    VERSION = "1.2"


    def __init__(self):

        print(
            "📥 CHAT INPUT ADAPTER v1.2 ONLINE"
        )


    def normalize(
        self,
        message,
        context=None
    ):


        text = ""
        image = None


        # ------------------------------
        # TEXT INPUT
        # ------------------------------

        if isinstance(
            message,
            str
        ):

            text = message


        elif isinstance(
            message,
            dict
        ):

            text = message.get(
                "text",
                ""
            )

            image = message.get(
                "image"
            )


        if text is None:

            text = ""


        # ------------------------------
        # CONTEXT IMAGE FALLBACK
        # ------------------------------

        if (
            image is None
            and
            isinstance(context, dict)
        ):

            if "path" in context:

                image = {

                    "path":
                        context["path"]

                }


            elif "image" in context:

                image = context["image"]


        # ------------------------------
        # DETERMINISTIC NORMALIZATION
        # ------------------------------

        request = persian_normalizer.normalize(
            text
        )


        # image reference is part of the request boundary
        request["image"] = image


        return request
