# ==========================================================
# ArchitectOS Pattern Curriculum v1
#
# CURRICULUM_FOUNDATION_FIX_02 — PART 3 — PATTERN CURRICULUM BOUNDARY
#
# The brief asks for three pattern families:
#
#   residential  |  commercial  |  mixed use
#
# Only RESIDENTIAL has a corpus. Commercial and mixed-use have none, so
# they must remain BLOCKED until their corpus exists.
#
# THIS MODULE HOLDS BOUNDARY METADATA ONLY:
#   * no patterns
#   * no lesson content
#   * no generated lessons
#
# Availability is DERIVED FROM EVIDENCE, never hardcoded: a family is
# AVAILABLE only if the Phase 09 read bridge actually exposes a corpus
# source for it with a positive pattern count. That way, registering a
# commercial pattern library in the bridge would make the family
# available with no change here — and until then it stays blocked and
# says why.
# ==========================================================


from __future__ import annotations


from core.conversation.knowledge_read_bridge_v1 import (
    knowledge_read_bridge,
)


CONTRACT = "PatternCurriculumV1"
VERSION = "1.0"


FAMILY_RESIDENTIAL = "residential"
FAMILY_COMMERCIAL = "commercial"
FAMILY_MIXED_USE = "mixed_use"


STATUS_AVAILABLE = "AVAILABLE"
STATUS_BLOCKED = "BLOCKED"


ALL_FAMILY_STATUSES = (STATUS_AVAILABLE, STATUS_BLOCKED)


# ----------------------------------------------------------
# THE THREE FAMILIES
#
# `source_hints` are substrings matched against the read bridge's source
# ids. A family with no matching source is BLOCKED — the reason is
# generated from that evidence, not asserted.
# ----------------------------------------------------------

PATTERN_FAMILIES = (

    {
        "key": FAMILY_RESIDENTIAL,
        "label_fa": "\u0627\u0644\u06af\u0648\u0647\u0627\u06cc "
                    "\u0645\u0633\u06a9\u0648\u0646\u06cc",
        "label_en": "residential patterns",
        # both the positive and the negative library — the negative one's
        # id is "residential_negative_pattern_library", which does NOT
        # contain the substring "residential_pattern"
        "source_hints": (
            "residential_pattern",
            "residential_negative_pattern",
        ),
        "reason_when_blocked_en": (
            "no residential pattern corpus is exposed by the read bridge"
        ),
        "reason_when_blocked_fa": (
            "\u0645\u062a\u0646 \u0627\u0644\u06af\u0648\u0647\u0627\u06cc "
            "\u0645\u0633\u06a9\u0648\u0646\u06cc \u062f\u0631 \u062f\u0633\u062a\u0631\u0633 "
            "\u0646\u06cc\u0633\u062a"
        ),
    },

    {
        "key": FAMILY_COMMERCIAL,
        "label_fa": "\u0627\u0644\u06af\u0648\u0647\u0627\u06cc \u062a\u062c\u0627\u0631\u06cc",
        "label_en": "commercial patterns",
        "source_hints": ("commercial_pattern",),
        "reason_when_blocked_en": (
            "no commercial pattern corpus exists; commercial patterns stay "
            "blocked until one is authored and audited"
        ),
        "reason_when_blocked_fa": (
            "\u0645\u062a\u0646 \u0627\u0644\u06af\u0648\u0647\u0627\u06cc "
            "\u062a\u062c\u0627\u0631\u06cc \u0648\u062c\u0648\u062f \u0646\u062f\u0627\u0631\u062f"
        ),
    },

    {
        "key": FAMILY_MIXED_USE,
        "label_fa": "\u0627\u0644\u06af\u0648\u0647\u0627\u06cc "
                    "\u062a\u0631\u06a9\u06cc\u0628\u06cc",
        "label_en": "mixed-use patterns",
        "source_hints": ("mixed_use_pattern", "mixed_pattern"),
        "reason_when_blocked_en": (
            "no mixed-use pattern corpus exists; mixed-use patterns stay "
            "blocked until one is authored and audited"
        ),
        "reason_when_blocked_fa": (
            "\u0645\u062a\u0646 \u0627\u0644\u06af\u0648\u0647\u0627\u06cc "
            "\u062a\u0631\u06a9\u06cc\u0628\u06cc \u0648\u062c\u0648\u062f \u0646\u062f\u0627\u0631\u062f"
        ),
    },
)


FAMILY_KEYS = tuple(family["key"] for family in PATTERN_FAMILIES)


# ----------------------------------------------------------
# PATTERN TEACHING ASPECTS
#
# An ELICITATION vocabulary — the set of question categories offered when
# a teacher wants to teach a pattern. It is NOT lesson content: there is
# no lesson text, no exercise and no worked example anywhere in this
# module. Same kind of artefact as the space / diagram / program aspect
# sets built in Phases 10-12.
# ----------------------------------------------------------

PATTERN_TEACHING_ASPECTS = (
    (
        "pattern_definition",
        "\u0645\u0641\u0647\u0648\u0645 \u0627\u0644\u06af\u0648",
        "what the pattern is",
    ),
    (
        "context",
        "\u0632\u0645\u06cc\u0646\u0647\u0654 \u06a9\u0627\u0631\u0628\u0631\u062f",
        "where the pattern applies",
    ),
    (
        "spatial_arrangement",
        "\u0686\u06cc\u062f\u0645\u0627\u0646 \u0641\u0636\u0627\u06cc\u06cc",
        "how the spaces are arranged",
    ),
    (
        "trade_offs",
        "\u0645\u0632\u0627\u06cc\u0627 \u0648 \u0645\u062d\u062f\u0648\u062f\u06cc\u062a\u200c\u0647\u0627",
        "what it costs and when not to use it",
    ),
    (
        "examples",
        "\u0646\u0645\u0648\u0646\u0647\u200c\u0647\u0627\u06cc \u0627\u062c\u0631\u0627\u0634\u062f\u0647",
        "built examples",
    ),
)


def pattern_aspects(language="fa"):

    index = 1 if str(language or "").startswith("fa") else 2

    return [
        {"key": item[0], "label": item[index]}
        for item in PATTERN_TEACHING_ASPECTS
    ]


# Patterns themselves are NOT here. The curriculum holds the BOUNDARY;
# the corpus holds the patterns.
PATTERNS = ()


class PatternCurriculumV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, read_bridge=None, families=None):

        self.read_bridge = read_bridge or knowledge_read_bridge

        self.families_spec = tuple(families or PATTERN_FAMILIES)

        print(
            "\U0001f9f5 PATTERN CURRICULUM v1.0 ONLINE "
            "(3 families, boundary only - no patterns)"
        )

    # ======================================================
    # EVIDENCE
    # ======================================================

    def _sources(self):

        report = self.read_bridge.read_report() or {}

        return report.get("sources") or []

    # ------------------------------------------------------

    def sources_for(self, key):

        """Read-bridge sources that back a family (by id substring)."""

        family = self.family_spec(key)

        if not family:

            return []

        hints = family.get("source_hints") or ()

        matched = []

        for source in self._sources():

            source_id = str(source.get("id") or "")

            if any(hint in source_id for hint in hints):

                matched.append(source)

        return matched

    # ------------------------------------------------------

    def count_for(self, key):

        """Total patterns across a family's sources."""

        total = 0

        for source in self.sources_for(key):

            counts = source.get("counts") or {}

            if isinstance(counts, dict):

                total += int(counts.get("patterns") or 0)

        return total

    # ======================================================
    # AVAILABILITY (derived, never hardcoded)
    # ======================================================

    def status_for(self, key):

        """AVAILABLE only when a real corpus source exists with patterns."""

        sources = self.sources_for(key)

        usable = [
            source for source in sources
            if source.get("exists") is True
            and int(
                (source.get("counts") or {}).get("patterns") or 0
            ) > 0
        ]

        return STATUS_AVAILABLE if usable else STATUS_BLOCKED

    # ------------------------------------------------------

    def family_spec(self, key):

        for family in self.families_spec:

            if family["key"] == key:

                return dict(family)

        return None

    # ------------------------------------------------------

    def families(self, language="en"):

        fa = str(language or "").startswith("fa")

        described = []

        for family in self.families_spec:

            key = family["key"]

            status = self.status_for(key)

            sources = self.sources_for(key)

            described.append(
                {
                    "key": key,
                    "label": (
                        family["label_fa"] if fa else family["label_en"]
                    ),
                    "status": status,
                    "available": status == STATUS_AVAILABLE,
                    "pattern_count": self.count_for(key),
                    "sources": [
                        source.get("id") for source in sources
                    ],
                    "blocked_reason": (
                        None if status == STATUS_AVAILABLE
                        else (
                            family["reason_when_blocked_fa"] if fa
                            else family["reason_when_blocked_en"]
                        )
                    ),
                }
            )

        return described

    # ------------------------------------------------------

    def available(self, language="en"):

        return [
            family for family in self.families(language)
            if family["available"]
        ]

    # ------------------------------------------------------

    def blocked(self, language="en"):

        return [
            family for family in self.families(language)
            if not family["available"]
        ]

    # ------------------------------------------------------

    def is_available(self, key):

        if key not in FAMILY_KEYS:

            return False

        return self.status_for(key) == STATUS_AVAILABLE

    # ------------------------------------------------------

    def coverage(self, language="en"):

        families = self.families(language)

        available = [f for f in families if f["available"]]

        blocked = [f for f in families if not f["available"]]

        return {

            "family_count": len(families),

            "available_count": len(available),
            "blocked_count": len(blocked),

            "available_families": [f["key"] for f in available],
            "blocked_families": [f["key"] for f in blocked],

            "pattern_count": sum(f["pattern_count"] for f in families),

            "families": families,

            "partial": bool(available) and bool(blocked),
        }

    # ------------------------------------------------------

    def report(self):

        coverage = self.coverage()

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "family_count": coverage["family_count"],
            "family_keys": list(FAMILY_KEYS),

            "available_families": coverage["available_families"],
            "blocked_families": coverage["blocked_families"],

            "availability_is_derived": True,
            "availability_source": (
                "core/conversation/knowledge_read_bridge_v1.py"
            ),

            "pattern_count": len(PATTERNS),
            "has_patterns": bool(PATTERNS),

            "aspect_count": len(PATTERN_TEACHING_ASPECTS),
            "aspects": pattern_aspects("fa"),
            "aspects_en": pattern_aspects("en"),

            "candidate_only": True,
            "promotion_implemented": False,

            "lesson_count": 0,
            "has_lessons": False,

            "permanent_learning": False,

            "contains_geometry": False,
            "contains_coordinates": False,

            "next_stage_not_started": (
                "commercial / mixed-use pattern corpus authoring "
                "(requires its own audit)"
            ),
        }


pattern_curriculum = PatternCurriculumV1()
