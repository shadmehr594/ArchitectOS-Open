# ==========================================================
# ArchitectOS Program Curriculum v1
#
# PHASE 12 - PART 5 - HUMAN TEACHING COMPATIBILITY
#
# Connects the floor-program stage to the Phase 09/10/11 teaching
# system.
#
#   "می خواهم برنامهٔ فضایی را یاد بدهم"
#     -> asks which aspect (five program aspects)
#     -> CANDIDATE ONLY, no permanent learning
#
# Aspect resolution is topic-aware and ordered:
#   a SPACE topic    -> Phase 10 space aspects
#   a DIAGRAM topic  -> Phase 11 diagram aspects
#   a PROGRAM topic  -> these aspects
#   anything else    -> the Phase 09 generic aspects
# ==========================================================


from __future__ import annotations


from core.conversation.turn_semantics_v1 import match_form


CONTRACT = "ProgramCurriculumV1"
VERSION = "1.0"


# ----------------------------------------------------------
# PROGRAM TEACHING ASPECTS (PART 5)
# ----------------------------------------------------------

PROGRAM_TEACHING_ASPECTS = (
    (
        "concept",
        "\u0645\u0641\u0647\u0648\u0645 \u0628\u0631\u0646\u0627\u0645\u0647\u0654 "
        "\u0641\u0636\u0627\u06cc\u06cc",
        "the concept of a floor program",
    ),
    (
        "requirements",
        "\u062a\u0639\u06cc\u06cc\u0646 \u0641\u0636\u0627\u0647\u0627\u06cc "
        "\u0636\u0631\u0648\u0631\u06cc \u0648 \u0627\u062e\u062a\u06cc\u0627\u0631\u06cc",
        "how required and optional spaces are decided",
    ),
    (
        "zoning",
        "\u0632\u0648\u0646\u200c\u0628\u0646\u062f\u06cc \u0628\u0631\u0646\u0627\u0645\u0647",
        "how the program divides into zones",
    ),
    (
        "priorities",
        "\u0627\u0648\u0644\u0648\u06cc\u062a \u0641\u0636\u0627\u0647\u0627",
        "which spaces matter most",
    ),
    (
        "constraints",
        "\u0645\u062d\u062f\u0648\u062f\u06cc\u062a\u200c\u0647\u0627\u06cc "
        "\u0628\u06cc\u0646 \u0641\u0636\u0627\u0647\u0627",
        "what must hold between spaces",
    ),
)


def program_aspects(language="fa"):

    index = 1 if str(language or "").startswith("fa") else 2

    return [
        {"key": item[0], "label": item[index]}
        for item in PROGRAM_TEACHING_ASPECTS
    ]


# ----------------------------------------------------------
# PROGRAM TOPIC MARKERS
#
# A topic is a PROGRAM topic when the user names the program itself,
# not one space and not the diagram.
#
# The bare Persian word "برنامه" is deliberately NOT a marker on its
# own: it is an extremely common word ("program"), and a bare marker
# would swallow unrelated teaching offers. The compound forms below
# are what actually name this layer.
# ----------------------------------------------------------

PROGRAM_TOPIC_MARKERS = (
    "\u0628\u0631\u0646\u0627\u0645\u0647\u0654 \u0641\u0636\u0627\u06cc\u06cc",  # برنامهٔ فضایی
    "\u0628\u0631\u0646\u0627\u0645\u0647 \u0641\u0636\u0627\u06cc\u06cc",  # برنامه فضایی
    "\u0628\u0631\u0646\u0627\u0645\u0647\u200c\u0631\u06cc\u0632\u06cc "
    "\u0641\u0636\u0627\u06cc\u06cc",  # برنامه‌ریزی فضایی
    "\u0628\u0631\u0646\u0627\u0645\u0647\u0654 \u0641\u0632\u0627",  # برنامهٔ فزا
    "\u0641\u0647\u0631\u0633\u062a \u0641\u0636\u0627\u0647\u0627",  # فهرست فضاها
    "\u062a\u0639\u062f\u0627\u062f \u0641\u0636\u0627\u0647\u0627",  # تعداد فضاها
    "floor program",
    "space program",
    "spatial program",
    "architectural program",
    "schedule of spaces",
    "schedule of accommodation",
    "program of spaces",
    "briefing",
)


class ProgramCurriculumV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self):

        print(
            "\U0001f4cb PROGRAM CURRICULUM v1.0 ONLINE "
            "(5 program aspects, candidate only)"
        )

    # ======================================================

    def is_program_topic(self, text):

        form = match_form(text)

        return any(
            marker in form for marker in PROGRAM_TOPIC_MARKERS
        )

    # ------------------------------------------------------

    def resolve_program_topic(self, text, language="fa"):

        if not self.is_program_topic(text):

            return None

        lang = "fa" if str(language or "").startswith("fa") else "en"

        return {

            "topic": "floor_program",

            "topic_label": (
                "\u0628\u0631\u0646\u0627\u0645\u0647\u0654 \u0641\u0636\u0627\u06cc\u06cc"
                if lang == "fa" else "floor program"
            ),

            "language": lang,

            # resolved here, where the raw text is still available
            "aspects": program_aspects(lang),
        }

    # ------------------------------------------------------

    def aspects_for_topic(self, text, language="fa"):

        if self.resolve_program_topic(text, language):

            return program_aspects(language)

        return None

    # ------------------------------------------------------

    def report(self):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "aspect_count": len(PROGRAM_TEACHING_ASPECTS),

            "aspects": program_aspects("fa"),
            "aspects_en": program_aspects("en"),

            "candidate_only": True,
            "promotion_implemented": False,

            "topic_markers": list(PROGRAM_TOPIC_MARKERS),

            "consumes": [
                "core/conversation/teaching_candidate_v1.py",
                "core/conversation/teaching_foundation_v1.py",
            ],
        }


program_curriculum = ProgramCurriculumV1()
