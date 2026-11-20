# ==========================================================
# ArchitectOS Space Curriculum v1
#
# PHASE 10 — PART 4 — TEACHING COMPATIBILITY
#
# Connects the space-type knowledge layer to the PHASE 09 teaching
# system.
#
# When the user offers to teach a SPACE:
#
#   "می خواهم آشپزخانه را به تو یاد بدهم"
#
# the system must NOT learn. It asks which ASPECT of that space is
# being taught, using the curriculum's five space aspects:
#
#   1. تعریف فضا
#   2. عملکرد
#   3. ارتباط با فضاهای دیگر
#   4. ابعاد و استانداردها
#   5. نمونه های طراحی
#
# Everything is stored as a CANDIDATE only. No promotion.
# ==========================================================


from __future__ import annotations


from core.curriculum.space_types_v1 import space_types
from core.curriculum.space_query_v1 import scan_spaces


CONTRACT = "SpaceCurriculumV1"
VERSION = "1.0"


# ----------------------------------------------------------
# SPACE TEACHING ASPECTS (PART 4)
# ----------------------------------------------------------

SPACE_TEACHING_ASPECTS = (
    (
        "space_definition",
        "\u062a\u0639\u0631\u06cc\u0641 \u0641\u0636\u0627",
        "space definition",
    ),
    (
        "function",
        "\u0639\u0645\u0644\u06a9\u0631\u062f",
        "function",
    ),
    (
        "relationship",
        "\u0627\u0631\u062a\u0628\u0627\u0637 \u0628\u0627 "
        "\u0641\u0636\u0627\u0647\u0627\u06cc \u062f\u06cc\u06af\u0631",
        "relationship to other spaces",
    ),
    (
        "dimensions",
        "\u0627\u0628\u0639\u0627\u062f \u0648 \u0627\u0633\u062a\u0627\u0646\u062f\u0627\u0631\u062f\u0647\u0627",
        "dimensions and standards",
    ),
    (
        "examples",
        "\u0646\u0645\u0648\u0646\u0647 \u0647\u0627\u06cc \u0637\u0631\u0627\u062d\u06cc",
        "design examples",
    ),
)


def space_aspects(language="fa"):

    index = 1 if str(language or "").startswith("fa") else 2

    return [
        {"key": item[0], "label": item[index]}
        for item in SPACE_TEACHING_ASPECTS
    ]


class SpaceCurriculumV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, registry=None):

        self.registry = registry or space_types

        print(
            "\U0001f3eb SPACE CURRICULUM v1.0 ONLINE "
            "(5 space aspects, candidate only)"
        )

    # ======================================================
    # TOPIC RESOLUTION
    # ======================================================

    def resolve_space_topic(self, text, language="fa"):

        """Resolve the space a teaching offer is about.

        Returns a dict or None. Uses the SAME alias table as the space
        query layer, so the topic and the reasoning layer always agree.
        """

        lang = "fa" if str(language or "").startswith("fa") else "en"

        mentions = scan_spaces(text)

        if not mentions:

            return None

        space_id = mentions[0][0]

        record = self.registry.space(space_id) or {}

        name = (record.get("name") or {}).get(lang) or space_id

        return {

            "space_id": space_id,

            "alias": mentions[0][1],

            "name": name,

            "category": record.get("category"),

            "privacy_level": record.get("privacy_level"),

            "language": lang,
        }

    # ======================================================

    def aspects_for_topic(self, topic, language="fa"):

        """The five space aspects when the topic is a known space."""

        if not topic:

            return None

        if isinstance(topic, str):

            resolved = self.resolve_space_topic(topic, language)

            if not resolved:

                return None

            return space_aspects(language)

        if isinstance(topic, dict) and topic.get("space_id"):

            return space_aspects(language)

        return None

    # ======================================================

    def aspect_set(self, language="fa"):

        return space_aspects(language)

    # ======================================================

    def report(self):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "aspect_count": len(SPACE_TEACHING_ASPECTS),

            "aspects": space_aspects("fa"),

            "aspects_en": space_aspects("en"),

            "candidate_only": True,
            "promotion_implemented": False,

            "space_count": self.registry.count(),
        }


space_curriculum = SpaceCurriculumV1()
