# ==========================================================
# ArchitectOS Design Intelligence v69.2
# Architectural Design Decision Engine
# ==========================================================

from core.ai.style_library import STYLE_LIBRARY
from core.ai.design_profile import DesignProfile


class DesignIntelligence:

    def __init__(self):

        print(
            "🏛️ Design Intelligence v69.2 ACTIVE"
        )

    # ======================================================
    # BUILD DESIGN PROFILE
    # ======================================================

    def build(
        self,
        intent,
        entities=None
    ):

        if entities is None:
            entities = {}

        # --------------------------------------------------
        # STYLE DETECTION
        # --------------------------------------------------

        style = entities.get(
            "style",
            "modern"
        )

        if style not in STYLE_LIBRARY:

            style = "modern"

        profile = STYLE_LIBRARY[style].copy()

        # --------------------------------------------------
        # CORE DATA
        # --------------------------------------------------

        profile["style"] = style

        profile["intent"] = intent

        # --------------------------------------------------
        # PRESERVATION RULES
        # --------------------------------------------------

        profile["preserve"] = [

            "building geometry",
            "floor count",
            "roof shape",
            "window positions",
            "balcony positions",
            "camera angle",
            "structural system"

        ]

        # --------------------------------------------------
        # EDITABLE ELEMENTS
        # --------------------------------------------------

        profile["editable"] = [

            "facade materials",
            "architectural details",
            "lighting",
            "textures",
            "railings",
            "frames",
            "entrance",
            "landscape"

        ]

        # --------------------------------------------------
        # RETURN OBJECT
        # --------------------------------------------------

        return DesignProfile(

            style=profile["style"],

            materials=profile["materials"],

            design_language=profile["design_language"],

            lighting=profile["lighting"],

            negative=profile["negative"],

            runtime=profile["runtime"],

            preserve=profile["preserve"],

            editable=profile["editable"]

        )


# ==========================================================
# GLOBAL INSTANCE
# ==========================================================

design_intelligence = DesignIntelligence()