"""Canonical drawing-type vocabulary and provider drawing-type extraction.

THREE DIFFERENT FACTS are kept strictly separate:

  * the canonical, system-level ``image_type`` — decided only by evidence the
    system can stand behind,
  * the SOURCE MEDIUM — is this image a photograph, a rendering, or a drawing?
    (``canonical_medium``), and
  * the MODEL's drawing-type observation — an observation, recorded with its
    verification state, never authoritative.

The medium is a distinct fact, not a restatement of the family: a photograph and
a 3D rendering are BOTH ``architectural_render_or_photo``, and that family is
neutral about whether the scene is interior or exterior. Nothing here decides
geometry, orientation, plan structure or scene category, and nothing here
promotes a model observation to a fact.

The mapping from the observer's free text to the canonical vocabulary is
explicit, bounded, negation-aware and clause-scoped. There is no per-image or
per-vocabulary special case: a clause that is negated ("not a building floor
plan") contributes NO markers at all.
"""

import re

CANONICAL_TYPES = (
    "architectural_render_or_photo",
    "facade_or_elevation",
    "floor_plan_or_sketch",
    "site_diagram",
    "unknown",
)

# VISION_IMAGE_TYPE_AND_MEDIUM_HANDOFF_V1 — the SOURCE MEDIUM vocabulary.
#
# Deliberately disjoint from `CANONICAL_TYPES` (except the shared "unknown"), and
# deliberately disjoint from the architectural scene vocabulary
# (interior / exterior / mixed / plan / diagram / unknown) used by
# `architectural_observation_v1._refine_image_type`. A photograph is not a
# scene, an exterior is not a medium, and neither may be derived from the other.
CANONICAL_MEDIA = (
    "photograph",
    "rendering",
    "drawing",
    "unknown",
)

# Bounded, specific medium markers. "photo" is safe here because matching is
# whole-token: it does NOT match inside "photorealistic", which is a rendering.
MEDIUM_MARKERS = (
    ("rendering", (
        "render", "rendering", "rendered", "renderer",
        "photorealistic", "visualization", "visualisation",
        "3d", "3-d", "cgi", "computer-generated", "computer generated",
        "رندر", "سه بعدی", "سه‌بعدی",
    )),
    ("photograph", (
        "photograph", "photographic", "photographed", "photo", "camera",
        "عکس", "عکاسی",
    )),
    ("drawing", (
        "drawing", "sketch", "hand-drawn", "hand drawn", "linework",
        "line drawing", "diagram", "نقشه", "طرح دستی",
    )),
)

# A medium word may carry inflection — "two photographs", "several renderings",
# `عکس‌ها`. Same convention as the space-type vocabulary
# (`architectural_vision_interpreter_v1._TERM_TAIL`): an English plural or a
# Persian plural may continue the word; anything else is a different word.
_MEDIUM_TAIL = r"(?:s|es|\u200c?ها(?:ی|یی)?)?"


def _medium_token(clause, marker):
    return re.search(
        r"(?<!\w)" + re.escape(marker.lower()) + _MEDIUM_TAIL + r"(?!\w)",
        clause,
    ) is not None


# Priority used ONLY to break a tie between equally-supported families.
FAMILY_PRIORITY = (
    "site_diagram",
    "facade_or_elevation",
    "floor_plan_or_sketch",
    "architectural_render_or_photo",
)

# Deliberately specific markers. A bare "plan" is NOT a floor-plan marker,
# because "site plan" and "not a ... plan" must not be read as a floor plan.
FAMILY_MARKERS = (
    ("floor_plan_or_sketch", (
        "floor plan", "floorplan", "floor-plan", "ground plan", "layout drawing",
        "sketch plan", "plan of", "پلان معماری", "پلان طبقه", "پلان",
    )),
    ("site_diagram", (
        "cadastral", "land-survey", "land survey", "landsurvey", "kroki",
        "parcel", "plot plan", "site plan", "site diagram", "subdivision",
        "land-subdivision", "کروکی", "قطعه", "کاربری زمین",
    )),
    ("facade_or_elevation", (
        "facade", "façade", "elevation", "section", "نمای", "برش",
    )),
    ("architectural_render_or_photo", (
        "render", "rendering", "photorealistic", "photograph", "photo",
        "visualization", "visualisation", "3d",
    )),
)

NEGATION_MARKERS = (
    "not ", "not a", "no ", "never", "neither", "nor ", "without", "isn't",
    "is not", "are not", "rather than", "instead of",
    "نیست", "نمی‌باشد", "بدون", "نه ", "غیر",
)

# Clause boundaries. A comma is deliberately NOT a boundary, so
# "not a line drawing, plan, or section" stays one negated clause.
_CLAUSE_BOUNDARIES = (".", ";", "\n", "(", ")", "،")


def _clauses(text):
    value = str(text or "")
    for boundary in _CLAUSE_BOUNDARIES:
        value = value.replace(boundary, "\x00")
    return [part.strip() for part in value.split("\x00") if part.strip()]


def _is_negated(clause):
    lowered = clause.lower()
    return any(marker in lowered for marker in NEGATION_MARKERS)


def canonical_drawing_type(text):
    """Map a drawing-type observation to the canonical vocabulary, or "unknown".

    Only NON-NEGATED clauses contribute. A negated clause is discarded whole,
    so a correct negative ("not a building floor plan") can never be inverted
    into a positive type.
    """

    scores = {}
    for clause in _clauses(text):
        if _is_negated(clause):
            continue
        lowered = clause.lower()
        for family, markers in FAMILY_MARKERS:
            hits = sum(1 for marker in markers if marker in lowered)
            if hits:
                scores[family] = scores.get(family, 0) + hits
    if not scores:
        return "unknown"
    best = max(scores.values())
    for family in FAMILY_PRIORITY:
        if scores.get(family) == best:
            return family
    return "unknown"


def provider_drawing_type(understanding):
    """The MODEL's drawing-type observation, or None.

    Read from the verified provider candidates. Returns the raw text, the
    canonical mapping and the verification state; `verified` is False unless
    the candidate itself was independently confirmed.
    """

    if not isinstance(understanding, dict):
        return None
    for claim in understanding.get("provider_candidates") or []:
        if not isinstance(claim, dict):
            continue
        if claim.get("category") != "drawing_type":
            continue
        text = claim.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        return {
            "text": text,
            "canonical": canonical_drawing_type(text),
            "state": claim.get("state", "UNVERIFIED"),
            "verified": bool(claim.get("state") == "CONFIRMED" and claim.get("grounded")),
            "source": "MODEL_OBSERVED",
            "certainty": claim.get("certainty"),
            "candidate_id": claim.get("candidate_id"),
            "note": "model observation; not independently verified",
        }
    return None


def canonical_medium(text):
    """The SOURCE MEDIUM stated by a drawing-type observation.

    Returns ``{"medium", "basis", "evidence_clause"}``. `medium` is one of
    `CANONICAL_MEDIA`; it is never an architectural scene category and never a
    drawing family.

    Only NON-NEGATED clauses contribute, exactly as in `canonical_drawing_type`:
    the real facade-A text reads "This is a colour photograph of a built
    structure (not a drawing, plan, or section)", and the negated parenthetical
    must not turn a photograph into a drawing.

    A tie between two media is NOT resolved by preference — a description that
    offers alternatives ("a photograph, possibly a rendering") is reported as
    `CONFLICTING_MEDIUM_EVIDENCE` with medium "unknown". Guessing here would
    manufacture a fact the source did not state.
    """

    if not isinstance(text, str) or not text.strip():

        return {
            "medium": "unknown",
            "basis": "NO_DRAWING_TYPE_OBSERVATION",
            "evidence_clause": None,
        }

    scores = {}
    evidence = {}

    for clause in _clauses(text):

        if _is_negated(clause):

            continue

        lowered = clause.lower()

        for family, markers in MEDIUM_MARKERS:

            hits = [marker for marker in markers if _medium_token(lowered, marker)]

            if hits:

                scores[family] = scores.get(family, 0) + len(hits)

                evidence.setdefault(family, clause.strip())

    if not scores:

        return {
            "medium": "unknown",
            "basis": "NO_MEDIUM_EVIDENCE",
            "evidence_clause": None,
        }

    best = max(scores.values())

    winners = [family for family in CANONICAL_MEDIA if scores.get(family) == best]

    if len(winners) > 1:

        return {
            "medium": "unknown",
            "basis": "CONFLICTING_MEDIUM_EVIDENCE",
            "evidence_clause": None,
        }

    return {
        "medium": winners[0],
        "basis": "PROVIDER_STATED",
        "evidence_clause": evidence.get(winners[0]),
    }


__all__ = [
    "CANONICAL_TYPES", "FAMILY_PRIORITY", "FAMILY_MARKERS", "NEGATION_MARKERS",
    "canonical_drawing_type", "provider_drawing_type",
    "CANONICAL_MEDIA", "MEDIUM_MARKERS", "canonical_medium",
]
