# ==========================================================
# ArchitectOS Program Classifier v1
#
# PHASE 12 - PART 1 - BUILDING PROGRAM UNDERSTANDING
#
# Reads a free-form requirement in Persian or English and decides:
#
#   * the BUILDING TYPE  - residential / commercial / mixed use
#                          (+ villa, parking, cinema, auditorium,
#                             amphitheater, which the frozen program
#                             corpus already knows)
#   * the OCCUPANCY      - household size, in people
#   * the BEDROOM COUNT  - DELEGATED to Phase 11's parser, never
#                          re-implemented here
#
# Deterministic. No LLM, no network. Persian and English only.
#
# The bedroom count is the one place where a second implementation
# would be actively dangerous: Phase 11 fixed a real bug there (a bare
# number word anywhere in the sentence was read as a bedroom count), so
# this module CALLS that parser instead of copying it.
# ==========================================================


from __future__ import annotations


import re


from core.conversation.turn_semantics_v1 import match_form, script_of

from core.curriculum.bubble_diagram_v1 import (
    bubble_diagram_builder,
    PERSIAN_NUMBERS,
    ENGLISH_NUMBERS,
)

from core.curriculum.program_model_v1 import (
    BUILDING_TYPE_RESIDENTIAL,
    BUILDING_TYPE_VILLA,
    BUILDING_TYPE_COMMERCIAL,
    BUILDING_TYPE_MIXED_USE,
    BUILDING_TYPE_PARKING,
    BUILDING_TYPE_CINEMA,
    BUILDING_TYPE_AUDITORIUM,
    BUILDING_TYPE_AMPHITHEATER,
    PRIMARY_BUILDING_TYPES,
    ALL_BUILDING_TYPES,
    building_type_display,
)


CONTRACT = "ProgramClassifierV1"
VERSION = "1.0"


# ----------------------------------------------------------
# BUILDING TYPE MARKERS
#
# Substring markers on the match form (lower-cased, punctuation
# stripped, Persian digits folded to ASCII). These are NOUNS, so
# substring matching is safe here - unlike the verb heuristics that
# burned earlier phases.
# ----------------------------------------------------------

RESIDENTIAL_MARKERS = (
    "\u062e\u0627\u0646\u0647",              # خانه
    "\u0645\u0633\u06a9\u0648\u0646\u06cc",  # مسکونی
    "\u0645\u0646\u0632\u0644",              # منزل
    "\u0622\u067e\u0627\u0631\u062a\u0645\u0627\u0646",  # آپارتمان
    "\u0648\u0627\u062d\u062f \u0645\u0633\u06a9\u0648\u0646\u06cc",  # واحد مسکونی
    "\u0633\u06a9\u0648\u0646\u062a\u06cc",  # سکونتی
    "house",
    "home",
    "residential",
    "apartment",
    "dwelling",
)

COMMERCIAL_MARKERS = (
    "\u062a\u062c\u0627\u0631\u06cc",        # تجاری
    "\u062a\u062c\u0627\u0631\u062a",        # تجارت
    "\u0641\u0631\u0648\u0634\u06af\u0627\u0647",  # فروشگاه
    "\u0645\u063a\u0627\u0632\u0647",        # مغازه
    "\u067e\u0627\u0633\u0627\u0698",        # پاساژ
    "\u0627\u062f\u0627\u0631\u06cc",        # اداری
    "\u0631\u0633\u062a\u0648\u0631\u0627\u0646",  # رستوران
    "\u06a9\u0627\u0641\u0647",              # کافه
    "commercial",
    "retail",
    "shop",
    "store",
    "office",
    "restaurant",
    "cafe",
)

MIXED_USE_MARKERS = (
    "\u062a\u0631\u06a9\u06cc\u0628\u06cc",  # ترکیبی
    "\u0645\u062e\u062a\u0644\u0637",        # مختلط
    "\u0686\u0646\u062f\u06a9\u0627\u0631\u0628\u0631\u06cc",  # چندکاربری
    "\u0686\u0646\u062f \u06a9\u0627\u0631\u0628\u0631\u06cc",  # چند کاربری
    "\u0686\u0646\u062f \u0645\u0646\u0637\u0648\u0631\u0647",  # چند منظوره
    "\u062a\u062c\u0627\u0631\u06cc \u0648 \u0645\u0633\u06a9\u0648\u0646\u06cc",
    "\u062a\u062c\u0627\u0631\u06cc-\u0645\u0633\u06a9\u0648\u0646\u06cc",
    "mixed use",
    "mixed-use",
    "mixeduse",
    "live work",
    "live-work",
)

VILLA_MARKERS = (
    "\u0648\u06cc\u0644\u0627",              # ویلا
    "villa",
)

PARKING_MARKERS = (
    "\u067e\u0627\u0631\u06a9\u06cc\u0646\u06af",  # پارکینگ
    "parking",
)

CINEMA_MARKERS = (
    "\u0633\u06cc\u0646\u0645\u0627",        # سینما
    "cinema",
)

AUDITORIUM_MARKERS = (
    "\u0633\u0627\u0644\u0646 \u0627\u062c\u062a\u0645\u0627\u0639\u0627\u062a",  # سالن اجتماعات
    "\u0627\u062c\u062a\u0645\u0627\u0639\u0627\u062a",
    "auditorium",
    "assembly hall",
)

AMPHITHEATER_MARKERS = (
    "\u0622\u0645\u0641\u06cc\u062a\u0626\u0627\u062a\u0631",  # آمفیتئاتر
    "\u0622\u0645\u0641\u06cc \u062a\u0626\u0627\u062a\u0631",
    "amphitheater",
    "amphitheatre",
)


TYPE_MARKERS = (
    (BUILDING_TYPE_RESIDENTIAL, RESIDENTIAL_MARKERS),
    (BUILDING_TYPE_COMMERCIAL, COMMERCIAL_MARKERS),
    (BUILDING_TYPE_MIXED_USE, MIXED_USE_MARKERS),
    (BUILDING_TYPE_VILLA, VILLA_MARKERS),
    (BUILDING_TYPE_PARKING, PARKING_MARKERS),
    (BUILDING_TYPE_CINEMA, CINEMA_MARKERS),
    (BUILDING_TYPE_AUDITORIUM, AUDITORIUM_MARKERS),
    (BUILDING_TYPE_AMPHITHEATER, AMPHITHEATER_MARKERS),
)


# ----------------------------------------------------------
# OCCUPANCY MARKERS
#
# A number only counts as an OCCUPANCY when it sits next to a person
# word. "چهار خوابه" is bedrooms; "چهار نفره" is people. This is the
# same adjacency discipline Phase 11's bedroom fix established.
# ----------------------------------------------------------

PERSON_TAIL = (
    "(?:\u0646\u0641\u0631|\u0646\u0641\u0631\u06cc|"
    "people|person|persons|member|members|occupants|occupant)"
)


FAMILY_HEAD = (
    "(?:\u062e\u0627\u0646\u0648\u0627\u062f\u0647|family|household)"
)


class ProgramClassifierV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self, builder=None):

        self.builder = builder or bubble_diagram_builder

        print(
            "\U0001f9e9 PROGRAM CLASSIFIER v1.0 ONLINE "
            "(residential / commercial / mixed use, fa + en)"
        )

    # ======================================================
    # BUILDING TYPE
    # ======================================================

    def _markers_present(self, form, markers):

        return [marker for marker in markers if marker in form]

    # ------------------------------------------------------

    def classify_building_type(self, text):

        """Building type + the evidence for it.

        Precedence, highest first:

          1. an explicit MIXED-USE marker
          2. BOTH residential and commercial markers -> mixed use
             (this is what "تجاری-مسکونی" means; neither word alone
              may win)
          3. a single specialty type (villa / parking / cinema /
             auditorium / amphitheater)
          4. a single residential or commercial marker
          5. default residential, flagged as a default
        """

        form = match_form(text)

        evidence = {
            building_type: self._markers_present(form, markers)
            for building_type, markers in TYPE_MARKERS
        }

        mixed = evidence[BUILDING_TYPE_MIXED_USE]

        residential = evidence[BUILDING_TYPE_RESIDENTIAL]

        commercial = evidence[BUILDING_TYPE_COMMERCIAL]

        # 1. explicit mixed-use marker
        if mixed:

            return {
                "building_type": BUILDING_TYPE_MIXED_USE,
                "building_type_label": building_type_display(
                    BUILDING_TYPE_MIXED_USE, "en"
                ),
                "source": "EXPLICIT_MIXED_USE_MARKER",
                "confidence": 0.95,
                "evidence": mixed,
                "components": [
                    BUILDING_TYPE_RESIDENTIAL,
                    BUILDING_TYPE_COMMERCIAL,
                ],
            }

        # 2. both fields named -> mixed use
        if residential and commercial:

            return {
                "building_type": BUILDING_TYPE_MIXED_USE,
                "building_type_label": building_type_display(
                    BUILDING_TYPE_MIXED_USE, "en"
                ),
                "source": "BOTH_RESIDENTIAL_AND_COMMERCIAL",
                "confidence": 0.9,
                "evidence": residential + commercial,
                "components": [
                    BUILDING_TYPE_RESIDENTIAL,
                    BUILDING_TYPE_COMMERCIAL,
                ],
            }

        # 3. specialty types
        for building_type in (
            BUILDING_TYPE_VILLA,
            BUILDING_TYPE_CINEMA,
            BUILDING_TYPE_AUDITORIUM,
            BUILDING_TYPE_AMPHITHEATER,
            BUILDING_TYPE_PARKING,
        ):

            if evidence[building_type]:

                return {
                    "building_type": building_type,
                    "building_type_label": building_type_display(
                        building_type, "en"
                    ),
                    "source": "EXPLICIT_TYPE_MARKER",
                    "confidence": 0.9,
                    "evidence": evidence[building_type],
                    "components": [building_type],
                }

        # 4. single field
        if residential:

            return {
                "building_type": BUILDING_TYPE_RESIDENTIAL,
                "building_type_label": building_type_display(
                    BUILDING_TYPE_RESIDENTIAL, "en"
                ),
                "source": "RESIDENTIAL_MARKER",
                "confidence": 0.9,
                "evidence": residential,
                "components": [BUILDING_TYPE_RESIDENTIAL],
            }

        if commercial:

            return {
                "building_type": BUILDING_TYPE_COMMERCIAL,
                "building_type_label": building_type_display(
                    BUILDING_TYPE_COMMERCIAL, "en"
                ),
                "source": "COMMERCIAL_MARKER",
                "confidence": 0.9,
                "evidence": commercial,
                "components": [BUILDING_TYPE_COMMERCIAL],
            }

        # 5. default
        return {
            "building_type": BUILDING_TYPE_RESIDENTIAL,
            "building_type_label": building_type_display(
                BUILDING_TYPE_RESIDENTIAL, "en"
            ),
            "source": "DEFAULT_RESIDENTIAL",
            "confidence": 0.5,
            "evidence": [],
            "components": [BUILDING_TYPE_RESIDENTIAL],
        }

    # ======================================================
    # OCCUPANCY
    # ======================================================

    def occupancy(self, text):

        """Household size, only when a number sits next to a person word."""

        raw = str(text or "")

        form = match_form(raw)

        people = None

        source = None

        # explicit digits
        match = re.search(r"(\d+)\s*" + PERSON_TAIL, form)

        if match:

            people = int(match.group(1))

            source = "DIGIT_ADJACENT_TO_PERSON_WORD"

        # Persian number words
        if people is None:

            for word, value in PERSIAN_NUMBERS.items():

                if re.search(re.escape(word) + r"\s*" + PERSON_TAIL, form):

                    people = value

                    source = "PERSIAN_NUMBER_WORD"

                    break

        # English number words
        if people is None:

            for word, value in ENGLISH_NUMBERS.items():

                if re.search(
                    r"\b" + word + r"\s*" + PERSON_TAIL, form
                ):

                    people = value

                    source = "ENGLISH_NUMBER_WORD"

                    break

        # "family of four" - the number follows the family head
        if people is None:

            match = re.search(
                FAMILY_HEAD + r"\s+(?:of\s+)?(\d+)", form
            )

            if match:

                people = int(match.group(1))

                source = "FAMILY_OF_DIGIT"

        if people is None:

            for word, value in ENGLISH_NUMBERS.items():

                if re.search(
                    FAMILY_HEAD + r"\s+(?:of\s+)?" + word + r"\b", form
                ):

                    people = value

                    source = "FAMILY_OF_NUMBER_WORD"

                    break

        if people is not None and people < 1:

            people = None

            source = None

        result = {
            "household_size": people,
            "source": source,
        }

        if people:

            result["confidence"] = 0.9

        else:

            result["confidence"] = 0.0

        return result

    # ======================================================
    # CLASSIFY
    # ======================================================

    def classify(self, text, language=None):

        raw = str(text or "")

        lang = (
            "fa" if str(language or "").startswith("fa")
            else "en" if str(language or "").startswith("en")
            else ("fa" if script_of(raw) == "persian" else "en")
        )

        building = self.classify_building_type(raw)

        occupancy = self.occupancy(raw)

        # ---- bedroom count: DELEGATED to Phase 11 ----
        parsed = self.builder.parse_program(raw)

        bedrooms = parsed.get("bedrooms")

        bedrooms_source = parsed.get("source")

        occupancy["bedrooms"] = bedrooms

        occupancy["bedrooms_source"] = (
            "PHASE_11_PROGRAM_PARSER" if bedrooms is not None else None
        )

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "raw_text": raw,
            "language": lang,

            "building_type": building["building_type"],
            "building_type_label": building_type_display(
                building["building_type"], lang
            ),
            "building_type_source": building["source"],
            "building_type_confidence": building["confidence"],
            "building_type_evidence": building["evidence"],
            "building_type_components": building["components"],

            "occupancy": occupancy,

            "is_primary_type": (
                building["building_type"] in PRIMARY_BUILDING_TYPES
            ),

            "deterministic": True,
            "llm_used": False,
            "network_used": False,
            "render_requested": False,
        }

    # ======================================================

    def report(self):

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "read_only": True,
            "writes_performed": 0,

            "building_types": list(ALL_BUILDING_TYPES),
            "primary_building_types": list(PRIMARY_BUILDING_TYPES),

            "marker_counts": {
                building_type: len(markers)
                for building_type, markers in TYPE_MARKERS
            },

            "occupancy_requires_adjacency": True,

            "bedroom_count_delegated_to": (
                "core/curriculum/bubble_diagram_v1.py"
            ),

            "deterministic": True,
            "llm_used": False,
            "network_used": False,
        }


program_classifier = ProgramClassifierV1()
