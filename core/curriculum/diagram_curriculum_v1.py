# ==========================================================
# ArchitectOS Diagram Curriculum v1
#
# PHASE 11 — PART 5 — HUMAN TEACHING COMPATIBILITY
#
# Connects the bubble-diagram stage to the Phase 09/10 teaching system.
#
#   "می خواهم دیاگرام فضایی را یاد بدهم"
#     -> asks which aspect (five diagram aspects)
#     -> CANDIDATE ONLY, no permanent learning
#
# The aspect set is topic-aware: a SPACE topic uses the Phase 10 space
# aspects, a DIAGRAM topic uses these, and anything else falls back to
# the Phase 09 generic aspects.
# ==========================================================


from __future__ import annotations


from core.conversation.turn_semantics_v1 import match_form


CONTRACT = "DiagramCurriculumV1"
VERSION = "1.0"


# ----------------------------------------------------------
# DIAGRAM TEACHING ASPECTS (PART 5)
# ----------------------------------------------------------

DIAGRAM_TEACHING_ASPECTS = (
    (
        "concept",
        "\u0645\u0641\u0647\u0648\u0645 \u062f\u06cc\u0627\u06af\u0631\u0627\u0645 "
        "\u0641\u0636\u0627\u06cc\u06cc",
        "the concept of a spatial diagram",
    ),
    (
        "relationships",
        "\u0646\u062d\u0648\u0647\u0654 \u0627\u0631\u062a\u0628\u0627\u0637 "
        "\u0641\u0636\u0627\u0647\u0627",
        "how spaces relate",
    ),
    (
        "zoning",
        "\u0632\u0648\u0646\u200c\u0628\u0646\u062f\u06cc",
        "zoning",
    ),
    (
        "examples",
        "\u0645\u062b\u0627\u0644\u200c\u0647\u0627\u06cc \u0645\u0639\u0645\u0627\u0631\u06cc",
        "architectural examples",
    ),
    (
        "mistakes",
        "\u0627\u0634\u062a\u0628\u0627\u0647\u0627\u062a \u0631\u0627\u06cc\u062c",
        "common mistakes",
    ),
)


def diagram_aspects(language="fa"):

    index = 1 if str(language or "").startswith("fa") else 2

    return [
        {"key": item[0], "label": item[index]}
        for item in DIAGRAM_TEACHING_ASPECTS
    ]


# ----------------------------------------------------------
# DIAGRAM TOPIC MARKERS
#
# A topic is a DIAGRAM topic when the user names the diagram, not a
# single space.
# ----------------------------------------------------------

DIAGRAM_TOPIC_MARKERS = (
    "\u062f\u06cc\u0627\u06af\u0631\u0627\u0645",              # دیاگرام
    "\u062f\u06cc\u0627\u06af\u0631\u0627\u0645 \u0641\u0636\u0627\u06cc\u06cc",  # دیاگرام فضایی
    "\u062d\u0628\u0627\u0628",                                # حباب
    "\u062f\u0627\u06cc\u0631\u0647 \u0647\u0627\u06cc \u0641\u0636\u0627\u06cc\u06cc",  # دایره‌های فضایی
    "\u0632\u0648\u0646\u200c\u0628\u0646\u062f\u06cc",        # زون‌بندی
    "\u062a\u0631\u06a9\u06cc\u0628 \u0641\u0636\u0627\u06cc\u06cc",  # ترکیب فضایی
    "\u0628\u0631\u0646\u0627\u0645\u0647\u0654 \u0641\u0636\u0627\u06cc\u06cc",  # برنامهٔ فضایی
    "bubble diagram",
    "bubble",
    "spatial diagram",
    "zoning",
    "space diagram",
)


class DiagramCurriculumV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self):

        print(
            "\U0001f5fa\ufe0f DIAGRAM CURRICULUM v1.0 ONLINE "
            "(5 diagram aspects, candidate only)"
        )

    # ======================================================

    def is_diagram_topic(self, text):

        form = match_form(text)

        return any(
            marker in form for marker in DIAGRAM_TOPIC_MARKERS
        )

    # ------------------------------------------------------

    def resolve_diagram_topic(self, text, language="fa"):

        if not self.is_diagram_topic(text):

            return None

        lang = "fa" if str(language or "").startswith("fa") else "en"

        return {

            "topic": "spatial_diagram",

            "topic_label": (
                "\u062f\u06cc\u0627\u06af\u0631\u0627\u0645 \u0641\u0636\u0627\u06cc\u06cc"
                if lang == "fa" else "spatial diagram"
            ),

            "language": lang,

            # resolved here, where the raw text is available
            "aspects": diagram_aspects(lang),
        }

    # ------------------------------------------------------

    def aspects_for_topic(self, text, language="fa"):

        if self.resolve_diagram_topic(text, language):

            return diagram_aspects(language)

        return None

    # ------------------------------------------------------

    def report(self):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "aspect_count": len(DIAGRAM_TEACHING_ASPECTS),

            "aspects": diagram_aspects("fa"),
            "aspects_en": diagram_aspects("en"),

            "candidate_only": True,
            "promotion_implemented": False,

            "topic_markers": list(DIAGRAM_TOPIC_MARKERS),
        }


diagram_curriculum = DiagramCurriculumV1()
