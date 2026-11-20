# -*- coding: utf-8 -*-
"""ARCHITECTURAL_OBSERVATION_V1

The architectural OBSERVATION contract.

WHAT IT IS
----------
A faithful, loss-free projection of what the vision model actually saw.

  Observation   = "what is visible"
  Interpretation = "what it may mean"

They are NEVER merged here: this contract carries observation only. It
contains no space classification, no function, no design intent and no
geometry.

THE THREE RULES
---------------
1. NEVER DROP. Every phrase the provider returned is preserved verbatim in
   `raw_observations`, and every phrase is also placed into at least one
   labelled bucket (or `unclassified_observations`). Nothing is silently
   discarded.
2. NEVER DEMOTE TO UNKNOWN. A visible material, room type or building type
   is reported as an observation with its own confidence and evidence
   phrase. It is NOT moved into "unknown" and NOT replaced with
   "unverified from image: ...".
3. UNKNOWN ONLY WHEN EVIDENCE IS TRULY ABSENT. An item lands in `unknowns`
   only when no visible evidence exists for it. If the provider expressed
   uncertainty about something it ALSO reported seeing, that uncertainty is
   recorded in `resolved_uncertainties` instead.

The contract is read-only, non-authoritative for geometry, and produces no
design. It never renders and never calls ComfyUI.
"""

from __future__ import annotations

import copy
import hashlib
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple


CONTRACT = "ArchitecturalObservationV1"
VERSION = "1.0"


# ----------------------------------------------------------
# image type (the brief's vocabulary)
# ----------------------------------------------------------

IMAGE_TYPES = (
    "interior",
    "exterior",
    "plan",
    "diagram",
    "mixed",
    "unknown",
)

# the upstream ImageUnderstandingV1 vocabulary -> this vocabulary
_UPSTREAM_IMAGE_TYPE = {
    "architectural_render_or_photo": "mixed",
    "facade_or_elevation": "exterior",
    "floor_plan_or_sketch": "plan",
    "site_diagram": "diagram",
    "unknown": "unknown",
}

_INTERIOR_MARKERS = (
    "interior", "indoor", "inside", "room", "ceiling", "sofa", "bed",
    "wardrobe", "closet", "kitchen", "bathroom", "furniture",
    "داخلی", "اتاق", "سقف", "مبل", "تخت", "کمد", "آشپزخانه", "حمام",
)

_EXTERIOR_MARKERS = (
    "facade", "elevation", "exterior", "outdoor", "outside", "roof",
    "balcony", "terrace", "walkway", "path", "greenery", "street",
    "نما", "بیرونی", "بام", "بالکن", "تراس", "محوطه", "خیابان",
)


# ==========================================================
# OPEN MARKER TABLES
#
# These LABEL a phrase; they never authorise dropping it. A phrase that
# matches nothing is kept in `unclassified_observations`.
# ==========================================================

ARCHITECTURAL_ELEMENT_MARKERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("wall", ("wall", "partition", "دیوار", "سطح قائم")),
    ("door", ("door", "doorway", "door symbol", "درب")),
    ("window", ("window", "glazing", "glazed", "پنجره", "شیشه")),
    ("opening", ("opening", "openings", "بازشو")),
    ("roof", ("roof", "roofline", "بام", "سقف بام")),
    # D6_NEGATIVE_EVIDENCE_BRIDGE_V1 — a dormer is a roof element with no label
    # of its own, so an explicit "no dormers" fell through to
    # `unclassified_observations`: it was reported neither as an element nor as
    # an absence. This is a directly supported architectural term and nothing
    # wider; it does not assert that a dormer exists anywhere.
    ("dormer", ("dormer", "dormers", "نورگیر بام")),
    ("facade", ("facade", "elevation", "نما", "پوسته بیرونی")),
    ("balcony", ("balcony", "terrace", "بالکن", "تراس", "ایوان")),
    ("stair", ("stair", "staircase", "steps", "پله", "راه پله", "راهپله")),
    ("column", ("column", "pillar", "ستون")),
    # V7 — a pilaster is a FLAT wall-attached pier, not a round column. The
    # two must never be collapsed: the V7 crop shows both, and the model
    # explicitly declined to call the flat piers columns. Substring matching
    # cannot confuse them because "pilaster" contains neither "column" nor
    # "pillar".
    ("pilaster", ("pilaster", "pilasters", "pilastered", "ستون‌نما", "نیم‌ستون")),
    ("capital", ("capital", "capitals", "سرستون")),
    ("cornice", ("cornice", "cornices", "قرنیز")),
    ("entablature", ("entablature", "entablatures", "فوق‌سرستون")),
    ("frieze", ("frieze", "friezes", "فریز")),
    ("moulding", ("moulding", "mouldings", "molding", "moldings", "قالب‌بندی")),
    ("pediment", ("pediment", "pediments", "pedimented", "سنتر")),
    ("keystone", ("keystone", "keystones", "سنگ کلید")),
    ("planter", ("planter", "planters", "گلدان")),
    # NOTE: deliberately NOT "wall light" — the bare marker "wall" is already
    # a kind and would double-label the phrase.
    ("light_fixture", ("sconce", "sconces", "lantern", "lanterns", "چراغ دیواری")),
    ("grille", ("grille", "grilles", "grillework", "ironwork", "شبکه فلزی")),
    # V7.4 — a PIER is a vertical support in its own right, wider and usually
    # flatter than a column. Without its own label a pier description that
    # mentions "a capital block" was being classified AS a capital, which
    # confuses a component with the subject. "pier" contains neither "column"
    # nor "pillar", so the labels stay disjoint.
    ("pier", ("pier", "piers")),
    # V7.4 — a GENERIC decorative horizontal band. This deliberately does NOT
    # assert a classical type: a carved band is not automatically a cornice, a
    # frieze or a floor division. Markers are multi-word to avoid matching a
    # bare "band".
    ("decorative_band", ("decorative band", "relief band", "carved band",
                         "band of carving", "band of relief")),
    # NOTE: no separate "balustrade" kind on purpose. The existing "railing"
    # markers already cover "balustrade", and a second label changed a legacy
    # space_type classification (test_1g). Balustrades and railings are one
    # family; reusing "railing" keeps the legacy semantics intact.
    ("beam", ("beam", "تیر")),
    ("ceiling", ("ceiling", "سقف")),
    ("floor", ("floor plane", "floor", "سطح کف", "کف")),
    # NOTE: a bare "arch" substring would match "architectural", and a
    # trailing space is stripped by _text(), so the markers are words.
    ("arch", ("arched", "archway", "arches", "قوس", "طاق")),
    ("railing", ("railing", "balustrade", "balustraded", "نرده")),
    ("louver", ("louver", "louvre", "slat", "slatted", "کرکره", "تیغه")),
    ("canopy", ("canopy", "overhang", "awning", "سایه‌بان", "پیش‌آمدگی")),
    ("corridor", ("corridor", "hallway", "passage", "راهرو", "دالان")),
    ("ramp", ("ramp", "شیب‌راه")),
    ("parapet", ("parapet", "جان‌پناه")),
    ("entrance", ("entrance", "entry", "entryway", "threshold", "ورودی", "آستانه")),
)

FURNITURE_MARKERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("bed", ("bed", "تخت")),
    ("sofa", ("sofa", "couch", "مبل")),
    ("chair", ("chair", "صندلی")),
    ("table", ("table", "میز")),
    ("desk", ("desk", "میز کار")),
    ("wardrobe", ("wardrobe", "closet", "کمد", "کلوزت", "رختکن")),
    ("cabinet", ("cabinet", "cupboard", "کابینت")),
    ("shelf", ("shelf", "shelving", "قفسه")),
    ("mirror", ("mirror", "آینه")),
    ("rug", ("rug", "carpet", "فرش", "قالی")),
    ("lamp", ("lamp", "light fixture", "چراغ")),
    ("sanitary", ("toilet", "wc", "sink", "basin", "bathtub", "shower",
                  "سرویس", "توالت", "دستشویی", "وان", "دوش")),
    ("counter", ("counter", "island", "کانتر")),
    ("screen", ("tv", "television", "screen", "تلویزیون")),
)

OBJECT_MARKERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    # NOTE: a bare "text" marker matches "texture" — the markers are words.
    ("text_label", ("text label", "text labels", "label", "caption",
                    "watermark", "url", "logo", "annotation",
                    "متن", "برچسب")),
    ("plant", ("plant", "tree", "greenery", "vegetation", "گیاه", "درخت")),
    ("walkway", ("walkway", "path", "pavement", "sidewalk", "مسیر",
                 "پیاده‌رو")),
    ("vehicle", ("car", "vehicle", "خودرو", "ماشین")),
    ("water_feature", ("pool", "fountain", "استخر", "آبنما")),
    ("fence", ("fence", "wall boundary", "حصار")),
    ("dimension_line", ("dimension line", "dimension lines", "خط اندازه")),
)

MATERIAL_MARKERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("concrete", ("concrete", "بتن")),
    ("glass", ("glass", "glazing", "curtain wall", "شیشه")),
    ("wood", ("wood", "wooden", "timber", "چوب")),
    ("stone", ("stone", "travertine", "marble", "granite", "سنگ", "مرمر")),
    # VISION_GENERIC_BRICK_IDENTITY_V1 — `آجر` alone is the noun, but Persian
    # describes a brick FACADE with the ADJECTIVAL form `آجری`, which the
    # word-bounded pattern could never match: `آجر` is followed by `ی`, a word
    # character, so the lookahead failed. `نمای آجری` is an alias the ontology
    # already declares, and the vision path never reached it. Both forms are
    # the same generic material; neither names a colour or a subtype.
    ("brick", ("brick", "آجر", "آجری")),
    # VISION_MATERIAL_SEMANTICS_V1 — the alloy is not the family.
    #
    # This entry used to read ("steel", ("steel","metal","aluminium",
    # "aluminum","فلز","فولاد")), so a generic material family, a DIFFERENT
    # metal and a Persian word for "metal" all became the specific alloy
    # `steel`. The ontology has no `steel` identity at all, so the observation
    # said `steel` while the knowledge block said `metal` — two contradictory
    # statements about the same phrase.
    #
    # `steel` now requires the word itself (English or فولاد). The family and
    # the other metal get their own identities.
    ("steel", ("steel", "فولاد")),
    ("metal", ("metal", "فلز")),
    ("aluminium", ("aluminium", "aluminum", "آلومینیوم", "آلومنیوم")),
    ("tile", ("tile", "tiled", "ceramic", "porcelain", "کاشی", "سرامیک")),
    ("plaster", ("plaster", "stucco", "render", "rendered", "گچ")),
    # VISION_MATERIAL_SEMANTICS_V1 — a panel is a product FORM, not a
    # material. "one prominent light/whitish ribbed panel" became `composite`
    # because "panel"/"panelling" were listed here; a panel can be stone,
    # marble, wood, aluminium or composite. Only the word itself now asserts
    # composite.
    ("composite", ("composite", "کامپوزیت")),
    ("masonry", ("masonry", "بنایی")),
)

TEXTURE_MARKERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("smooth", ("smooth", "polished", "صاف", "صیقلی")),
    ("rough", ("rough", "raw", "زبر")),
    ("textured", ("textured", "texture", "بافت‌دار")),
    ("ribbed", ("ribbed", "fluted", "شیاردار")),
    ("slatted", ("slatted", "louvered", "louver", "slat", "تیغه‌ای")),
    ("perforated", ("perforated", "مشبک")),
    ("matte", ("matte", "مات")),
    ("glossy", ("glossy", "reflective", "براق", "بازتابنده")),
    ("woven", ("woven", "بافت")),
)

COLOR_MARKERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("white", ("white", "سفید")),
    ("black", ("black", "سیاه")),
    ("grey", ("grey", "gray", "خاکستری", "طوسی")),
    ("beige", ("beige", "cream", "بژ", "کرم")),
    ("brown", ("brown", "قهوه‌ای")),
    ("red", ("red", "قرمز")),
    ("blue", ("blue", "آبی")),
    ("green", ("green", "سبز")),
    ("golden", ("gold", "golden", "brass", "طلایی", "برنجی")),
    ("dark", ("dark", "تیره")),
    ("light", ("light coloured", "light-colored", "روشن")),
)

# kind -> markers  (kind is the brief's style vocabulary)
STYLE_MARKERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("form", ("modern", "contemporary", "minimalist", "minimal", "organic",
              "parametric", "curved", "rectilinear", "boxy", "sculptural",
              "volume", "massing", "brutalist", "industrial",
              "مدرن", "مینیمال", "حجم", "فرم")),
    ("composition", ("composition", "symmetry", "symmetrical", "asymmetry",
                     "asymmetrical", "rhythm", "repetition", "grid", "axis",
                     "hierarchy", "balanced", "layered", "pattern",
                     "تقارن", "ریتم", "ترکیب", "شبکه", "محور")),
    ("proportion", ("proportion", "slender", "elongated", "horizontal",
                    "vertical", "wide", "narrow", "tall", "low-rise",
                    "تناسب", "افقی", "عمودی", "باریک", "بلند")),
    ("style_family", ("traditional", "classic", "classical", "vernacular",
                      "art deco", "islamic", "persian", "mediterranean",
                      "scandinavian", "japanese", "colonial",
                      "سنتی", "کلاسیک", "ایرانی", "اسلامی", "بومی")),
)

# floor-count detection
_FLOOR_WORDS = {
    "one": 1, "single": 1, "یک": 1,
    "two": 2, "double": 2, "دو": 2,
    "three": 3, "سه": 3,
    "four": 4, "چهار": 4,
    "five": 5, "پنج": 5,
    "six": 6, "شش": 6,
    "seven": 7, "هفت": 7,
    "eight": 8, "هشت": 8,
}

_FLOOR_NOUNS = (
    "story", "stories", "storey", "storeys", "floor", "floors",
    "level", "levels", "طبقه", "طبقات", "اشکوب",
)

_FLOOR_MULTI = (
    "multi-storey", "multi storey", "multi-story", "multi story",
    "multi-level", "multi level", "چند طبقه",
)

SPATIAL_CLUE_MARKERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("adjacency", ("adjacent", "next to", "beside", "connected to",
                   "attached", "adjoining", "neighbouring", "neighboring",
                   "side-by-side", "mirror-image",
                   "مجاور", "کنار", "چسبیده", "اتاق مجاور", "همجوار")),
    ("access", ("entrance", "entry", "door", "doorway", "access",
                "opening to", "leads to", "threshold",
                "ورودی", "دسترسی", "درب", "آستانه")),
    ("visibility", ("visible", "in view", "seen through", "transparent",
                    "glass partition", "open to", "overlook",
                    "قابل مشاهده", "شفاف", "دیده می‌شود", "پارتیشن شیشه‌ای")),
    ("circulation", ("corridor", "hallway", "passage", "stair", "staircase",
                     "walkway", "path", "ramp", "circulation",
                     "راهرو", "دالان", "پله", "مسیر", "گردش")),
)


# ----------------------------------------------------------
# helpers
# ----------------------------------------------------------

def _text(value: Any) -> str:

    if value is None:

        return ""

    if isinstance(value, str):

        return " ".join(value.split())

    return " ".join(str(value).split())


def _norm(value: Any) -> str:

    s = _text(value).lower()

    return (
        s.replace("\u200c", " ")
        .replace("\u064a", "\u06cc")
        .replace("\u0643", "\u06a9")
        .replace("_", " ")
    )


def _as_list(value: Any) -> List[str]:

    if value is None:

        return []

    if isinstance(value, str):

        text = _text(value)

        return [text] if text else []

    if isinstance(value, (list, tuple)):

        out: List[str] = []

        for item in value:

            text = _text(item)

            if text and text not in out:

                out.append(text)

        return out

    text = _text(value)

    return [text] if text else []


def _as_list_keep_duplicates(value: Any) -> List[str]:

    """`_as_list`, but EVERY occurrence is kept.

    ARCHITECTURAL_VISION_LABEL_COMPLETENESS_V1 — the read labels are a
    TRANSCRIPTION. Two identical room labels in a plan are two rooms, so
    de-duplicating here would silently collapse a real instance.
    """

    if value is None:

        return []

    if isinstance(value, str):

        text = _text(value)

        return [text] if text else []

    if isinstance(value, (list, tuple)):

        out: List[str] = []

        for item in value:

            text = _text(item)

            if text:

                out.append(text)

        return out

    text = _text(value)

    return [text] if text else []


# ----------------------------------------------------------
# VISION_CLASSIFICATION_SAFETY_V1 — marker matching
#
# `marker in phrase` was an unanchored substring test, so incidental word
# fragments became architectural evidence:
#
#   "through"  -> rough      ("t-ROUGH")
#   "rendered" -> red        ("RED-ered")
#   "street"   -> plant      ("s-TREE-t")
#   "drawing"  -> rough      ("d-RAW-ing")
#
# A marker now has to sit on WORD BOUNDARIES. Boundaries alone would lose
# real evidence, because the tables store singular forms ("wall", "window")
# while observers write plurals, so a plain plural suffix is allowed. Nothing
# else is: "rendered" must still not match "red".
#
# Boundaries are still NOT sufficient for hyphenated modifiers, which are
# handled by `_compound_modifier_suppresses` below.
# ----------------------------------------------------------

#: Every character the observer uses as a hyphen. The live evidence contains
#: U+2011 (non-breaking hyphen) and U+2014 (em dash) as well as ASCII '-'.
_HYPHEN_CHARS = "-\u2010\u2011\u2012\u2013\u2014\u2212"

_HYPHEN_CLASS = re.compile("[%s]" % re.escape(_HYPHEN_CHARS))

#: Characters that count as part of a word for boundary purposes.
_WORD_CLASS = "0-9A-Za-z\u0600-\u06FF"

#: Suffixes that make a compound modifier non-assertive about its head noun.
#: Deliberately narrow — see `_compound_modifier_suppresses`.
_NON_ASSERTIVE_TAILS = frozenset({"mounted", "like", "style", "type"})


def _match_text(value: Any) -> str:
    """Lower-cased text with hyphen variants folded, length-preserving.

    Character offsets stay valid against the original phrase, which the
    negation spans and the verbatim fragments both depend on. Every
    replacement here is 1:1.
    """

    s = _text(value).lower()

    for char in _HYPHEN_CHARS:

        if char != "-":

            s = s.replace(char, "-")

    return (
        s.replace("\u200c", " ")
        .replace("\u064a", "\u06cc")
        .replace("\u0643", "\u06a9")
        .replace("_", " ")
    )


@lru_cache(maxsize=1024)
def _marker_pattern(marker: str):
    """Word-bounded pattern for one marker, tolerant of English plurals.

    V1 appended the plural suffix to the WHOLE marker, so "balcony" produced
    "balconyies" and "balconies" matched nothing at all. The consonant+y rule
    needs the STEM: balcon+ies, canop+ies, entr+ies.

    A plural that matches nothing is worse than a mis-scoped one: it leaves
    BOTH buckets empty, so "No balconies are visible" lost its absence
    classification entirely instead of misfiling it.
    """

    base = _match_text(marker)

    forms = [base]

    if base.isascii() and base.replace(" ", "").isalpha():

        forms.append(base + "s")

        forms.append(base + "es")

        # consonant + y -> ies ("balcony" -> "balconies"), but a vowel + y
        # keeps the plain "s" ("grey" -> "greys", never "greies").
        if (base.endswith("y") and len(base) > 1
                and base[-2] not in "aeiou"):

            forms.append(base[:-1] + "ies")

    alternation = "|".join(
        re.escape(form) for form in sorted(set(forms), key=len, reverse=True))

    return re.compile(
        r"(?<![%s])(?:%s)(?![%s])" % (_WORD_CLASS, alternation, _WORD_CLASS)
    )


def _compound_modifier_suppresses(compound: str) -> bool:
    """True when a hyphenated compound uses its head as a MODIFIER.

    Only three constructions are treated as non-assertive, because only these
    were shown to invent elements:

      * extent range      "floor-to-ceiling"  -> not a floor AND a ceiling
      * attachment        "wall-mounted"      -> a fixture, not a wall
      * similarity        "parapet-like"      -> like a parapet, not one

    Everything else stays POSITIVE on purpose. `arched-top`, `dark-glazed`,
    `ground-floor` and `upper-floor` genuinely assert their element, and
    suppressing them would destroy real evidence.
    """

    parts = [part for part in _HYPHEN_CLASS.split(compound) if part]

    if len(parts) < 2:

        return False

    # "X-to-Y" — a range describing extent, not two observed elements.
    if len(parts) >= 3 and parts[1].lower() == "to":

        return True

    return parts[-1].lower() in _NON_ASSERTIVE_TAILS


def _compound_at(text: str, start: int, end: int) -> Tuple[int, int]:
    """Widen [start, end) to the whole hyphen-joined compound around it."""

    left, right = start, end

    while left >= 2 and text[left - 1] == "-" and re.match(
            "[%s]" % _WORD_CLASS, text[left - 2]):

        left -= 1

        probe = left - 1

        while probe >= 0 and re.match("[%s]" % _WORD_CLASS, text[probe]):

            probe -= 1

        left = probe + 1

    while right + 1 < len(text) and text[right] == "-" and re.match(
            "[%s]" % _WORD_CLASS, text[right + 1]):

        probe = right + 1

        while probe < len(text) and re.match("[%s]" % _WORD_CLASS, text[probe]):

            probe += 1

        right = probe

    return left, right


def _labels(phrase: str, table, *, suppress_compound_modifiers: bool = False) -> List[str]:
    """Every label the phrase carries. Empty list = unclassified (kept)."""

    text = _match_text(phrase)

    found: List[str] = []

    for label, markers in table:

        for marker in markers:

            pattern = _marker_pattern(marker)

            matched = False

            for match in pattern.finditer(text):

                if suppress_compound_modifiers:

                    left, right = _compound_at(text, match.start(), match.end())

                    if (left, right) != (match.start(), match.end()):

                        compound = text[left:right]

                        if _compound_modifier_suppresses(compound):

                            continue

                matched = True

                break

            if matched:

                if label not in found:

                    found.append(label)

                break

    return found


# ----------------------------------------------------------
# negation scope
#
# R2_NEGATION_MATERIAL_INTEGRITY_V1
#
# `_labels()` matches a marker anywhere in a phrase, which turned
# "no pitched roof" into a visible roof and "no plaster or cladding" into a
# present plaster. A marker only asserts PRESENCE when it sits outside every
# negation scope, so scopes are computed per phrase and each occurrence is
# tested against them.
#
# The vocabulary is deliberately small and existing: no new ontology, no new
# material table, no new status value on the established element list.
# ----------------------------------------------------------

#: Cues that put what FOLLOWS them into a negative scope. Word-bounded, so
#: "north" and "notation" never match. "unfinished" is deliberately excluded:
#: an unfinished concrete wall still HAS concrete.
_NEGATION_CUE = re.compile(
    r"\b(?:no|not|none|without|absent|cannot|isn't|aren't|wasn't|weren't|"
    r"doesn't|don't|didn't)\b",
    re.IGNORECASE,
)

#: Where a negative scope stops. A clause boundary ends it, and so does a
#: positive exception ("other than", "except"), which re-opens positive scope —
#: "no visible columns other than the piers" leaves the piers real.
_SCOPE_END = re.compile(
    r"[.;:,()\[\]]|\bother than\b|\bexcept\b|\bapart from\b|\bbut\b|\bhowever\b",
    re.IGNORECASE,
)

#: VISION_CLASSIFICATION_SAFETY_V1 — the same boundary set WITHOUT the comma.
#: A comma is not always a clause boundary: in "No doors, windows, stairs, or
#: vertical-circulation elements are clearly distinguishable" it separates the
#: members of ONE negated enumeration, and treating it as a clause boundary
#: left only "door" negated while `window` and `stair` were promoted to
#: VISIBLE architecture. That is the defect this constant exists to fix.
_STRONG_SCOPE_END = re.compile(
    r"[.;:()\[\]]|\bother than\b|\bexcept\b|\bapart from\b|\bbut\b|\bhowever\b",
    re.IGNORECASE,
)

#: Conjunctions that can join the members of ONE coordinated list. V1 only
#: accepted `or`/`nor`, so "No doors, windows, and stairs are visible" still
#: negated only `door`. `and` is admitted here only as EVIDENCE OF A LIST —
#: never as a licence to cross into an independent clause (see rule 1 in
#: `_forward_scope_end`).
_LIST_CONJUNCTION = re.compile(r"\b(?:and|or|nor)\b", re.IGNORECASE)


#: The predicate that ends a coordinated list. "No stairs, lifts, or other
#: vertical circulation elements are visible ON THE FACADE" negates the three
#: list members, not the facade they are absent from — so the scope stops where
#: the predicate starts and the facade is neither asserted nor denied.
_LIST_PREDICATE = re.compile(
    r"\b(?:is|are|was|were|be|been|being|appears?|seems?|remains?)\b",
    re.IGNORECASE,
)

#: VISION_MATERIAL_SEMANTICS_V1 — a LOCATIVE adjunct ends the negated noun
#: phrase. "No plaster on the brick wall" states the absence of plaster, not
#: of the wall it is absent from: the wall is the LOCATION. Without this the
#: forward scope ran to the end of the string, so the brick — and every other
#: material mentioned after the preposition — was recorded absent too.
#:
#: Only genuine locative prepositions are listed. "of", "with" and "from"
#: are deliberately absent: they do not introduce an adjunct, so they must
#: not be allowed to cut a negation short.
_LOCATIVE_END = re.compile(
    r"\b(?:on|in|at|along|across|behind|above|below|beneath|under|near|over|"
    r"within|against|throughout|around)\b",
    re.IGNORECASE,
)

#: VISION_NEGATION_CLAUSE_BOUNDARY_V1 — a determiner that may open a NEW noun
#: phrase:
#:
#:   "No columns, a balcony and windows are visible"
#:       -> `column` absent; `balcony` and `window` are separately ASSERTED
#:
#: Without this, the comma-plus-`and` shape looked identical in both cases and
#: a visible balcony, window, wall or facade became an absent element.
#:
#: VISION_NEGATION_COORDINATED_DETERMINER_V1 — a determiner is NOT by itself
#: proof of a new clause. A singular countable noun cannot appear bare inside a
#: coordination, so English FORCES the article there:
#:
#:   "No doors, windows, or a balcony are visible"   -> still ONE list
#:
#: `_determiner_opens_clause()` decides clausehood from four syntactic
#: conditions. The optional conjunction is captured so that a determiner
#: introduced by ", or" / ", and" can be recognised as a list member.
#:
#: Numerals are deliberately EXCLUDED: "two windows are visible" is common
#: inside one clause, and "No doors, windows, and two stairs" is still a list.
#: That residual is documented rather than guessed at.
_NEW_CLAUSE_DETERMINER = re.compile(
    r"\s*(?:(?P<conjunction>and|or|nor)\s+)?"
    r"(?P<determiner>a|an|the|this|that|these|those|its|their|his|her|our|my)\b",
    re.IGNORECASE,
)

#: Determiners that force a SINGULAR noun phrase. Used only by the
#: subject-predicate agreement test; "the", "these", "those", "their" and
#: "our" are deliberately absent because their number is not fixed by the
#: determiner alone.
_SINGULAR_DETERMINERS = frozenset({
    "a", "an", "this", "that", "its", "his", "her", "my",
})

#: Plural-agreeing predicates. A SINGULAR determiner phrase cannot be their
#: subject, so a number mismatch proves the phrase is a list member rather
#: than the subject of a clause: "a balcony are visible".
_PLURAL_PREDICATE = frozenset({"are", "were"})


def _determiner_opens_clause(text: str, comma: int, strong_end: int,
                             has_earlier_comma: bool) -> bool:
    """Does the determiner after ``comma`` open an INDEPENDENT clause?

    VISION_NEGATION_CLAUSE_BOUNDARY_V1 assumed it always did. That was a
    regression: the determiner is grammatically OBLIGATORY on a singular
    countable noun inside a negated coordination —

        "No doors, windows, or a balcony are visible"

    `balcony` cannot appear bare in that position, so the article carries no
    information about clausehood. Four syntactic conditions decide it, and a
    clause is accepted only when ALL of them hold. Anything genuinely
    ambiguous resolves to "list member": the absence is kept and no visible
    architecture is manufactured.

      1. A predicate must follow. Without one there is no clause at all:
         "The photograph shows no doors, windows, or a balcony".
      2. No comma may sit between the determiner phrase and that predicate.
         A comma means the coordination continues past this member:
         "No windows, a door, or balconies are visible".
      3. The determiner must not be introduced by a conjunction that already
         follows an earlier comma. ``, or a X`` / ``, and a X`` in that
         position is the FINAL member of a three-or-more member coordination:
         "No doors, windows, or a balcony are visible".
      4. A singular determiner phrase must agree with the predicate. With no
         coordination in between, "a balcony are visible" is not a clause.
    """

    match = _NEW_CLAUSE_DETERMINER.match(text, comma + 1)

    if not match:

        return False

    determiner = (match.group("determiner") or "").lower()

    conjunction = match.group("conjunction")

    after = match.end()

    # 1 — a clause needs a predicate.
    predicate = _LIST_PREDICATE.search(text, after, strong_end)

    if not predicate:

        return False

    between = text[after:predicate.start()]

    # 2 — a comma before the predicate means the list continues.
    if "," in between:

        return False

    # 3 — ", or a X" after an earlier comma is the final list member.
    if conjunction and has_earlier_comma:

        return False

    # 4 — number agreement, meaningful only for a bare singular phrase.
    if (determiner in _SINGULAR_DETERMINERS
            and not _LIST_CONJUNCTION.search(between)
            and predicate.group(0).lower() in _PLURAL_PREDICATE):

        return False

    return True


def _forward_scope_end(text: str, after: int) -> int:
    """Where a negative scope opened before ``after`` stops.

    A comma continues a negation only when it separates list MEMBERS, not
    clauses. The signals decide it, in order:

      0.  A comma followed by a FRESH negation cue ends this span (the next
          cue opens its own), and so does a comma followed by a DETERMINER
          that actually opens a new clause — decided by
          `_determiner_opens_clause()`, not by the determiner alone:
          "No columns, a balcony and windows are visible" negates `column`
          only, while "No doors, windows, or a balcony are visible" negates
          all three.
      1. If a predicate already appears BEFORE the first comma, that comma
         joins two clauses — "No columns are visible, and the facade is
         plain" must not negate the facade. This is why `and` cannot simply
         be added to a disjunction test.
      2. Otherwise the clause is a list. An explicit conjunction
         (and / or / nor) anywhere in it confirms that, and a bare
         enumeration of three or more members (two or more commas) is
         accepted too.
      3. A single comma with no conjunction is a clause boundary, so
         "No columns, the facade is plain" keeps the facade affirmative.

    The scope then stops at the predicate that FOLLOWS the list, so a trailing
    location ("... are visible on the facade") is not dragged into the
    negation.

    A locative adjunct is NOT a boundary here. "no windows or openings above
    the top window row" states an absence that is RESTRICTED to a region, and
    D6 requires that qualifier to survive. The substrate case — "no plaster on
    the brick wall" — is a MATERIAL distinction and is handled in
    `_material_negated()`, so elements and fragments keep this contract.
    """

    strong = _STRONG_SCOPE_END.search(text, after)

    strong_end = strong.start() if strong else len(text)

    commas = [index for index in range(after, strong_end) if text[index] == ","]

    predicate = _LIST_PREDICATE.search(text, after, strong_end)

    if not commas:

        return predicate.start() if predicate else strong_end

    # Rule 0 — a comma followed by a FRESH negation cue starts a new absence
    # statement, not a list member. "no pitched roof, no visible roof terrace,
    # no dormers" is three separate negatives; merging them into one span
    # destroys each one's verbatim fragment. The following cue opens its own
    # span, so this one must end here.
    #
    # Rule 0b — a comma followed by a DETERMINER MAY open a new noun phrase, so
    # the negation stops there. This is the discriminator that separates
    #   "No doors, windows, and stairs are visible"      (list: all bare)
    # from
    #   "No columns, a balcony and windows are visible"  (new subject)
    # which the comma-plus-conjunction shape alone could not distinguish.
    #
    # A determiner alone is NOT sufficient — see `_determiner_opens_clause()`.
    # "No doors, windows, or a balcony are visible" keeps the article because
    # `balcony` is singular countable, and the whole coordination stays negated.
    for index, comma in enumerate(commas):

        probe = comma + 1

        while probe < strong_end and text[probe] == " ":

            probe += 1

        if _NEGATION_CUE.match(text, probe):

            return comma

        if _determiner_opens_clause(text, comma, strong_end, index > 0):

            return comma

    # Rule 1 — the first comma already follows a complete clause.
    if predicate and predicate.start() < commas[0]:

        return commas[0]

    # Rule 3 — one comma and no conjunction is a clause boundary.
    if (not _LIST_CONJUNCTION.search(text, after, strong_end)
            and len(commas) < 2):

        return commas[0]

    # Rule 2 — a coordinated list: run to the predicate that follows it.
    return predicate.start() if predicate else strong_end

#: A restrictive qualifier RESTRICTS the negation it follows; it does not end
#: it. `_SCOPE_END` deliberately stops there so that the exception stays a
#: POSITIVE element ("no visible columns other than the piers" must not negate
#: `pier`). The DISPLAY fragment, however, must carry the qualifier, or the
#: user is shown an absolute claim the observer never made:
#:
#:   observed : no visible columns other than the ground-floor piers
#:   rendered : "no visible columns"        <-- inverts the meaning
#:
#: VISION_FIRST_FACADE_GROUNDING_V1 — extend the FRAGMENT only; the span used
#: for label classification is untouched, so no element changes its polarity.
_RESTRICTIVE_QUALIFIER = re.compile(
    r"\s*\b(?:other than|except(?:\s+for)?|apart from|besides|save for|"
    r"excluding)\b",
    re.IGNORECASE,
)


def _extend_over_restriction(text: str, end: int) -> int:
    """Extend a display span over the restrictive qualifier it stops at."""

    match = _RESTRICTIVE_QUALIFIER.match(text, end)

    if not match:

        return end

    stop = _SCOPE_END.search(text, match.end())

    return stop.start() if stop else len(text)

#: "X not visible" negates X, which PRECEDES the cue. Only predicative cues can
#: look backwards; "no visible X" and "none visible" always look forwards.
_BACKWARD_CUES = frozenset({
    "not", "isn't", "aren't", "wasn't", "weren't", "cannot",
    "doesn't", "don't", "didn't",
})

_POSTFIX_VISIBILITY = re.compile(
    r"\s*(?:be\s+|clearly\s+|directly\s+|actually\s+|readily\s+)?"
    r"(?:visible|seen|shown|present|observable|detectable|confirmable|legible|apparent)\b",
    re.IGNORECASE,
)


def _negation_spans(text: str) -> List[Tuple[int, int]]:
    """Half-open [start, end) ranges of ``text`` that state absence."""

    spans: List[Tuple[int, int]] = []

    for cue in _NEGATION_CUE.finditer(text):

        # "Pitched roof not visible" — the cue follows what it negates.
        if (cue.group(0).lower() in _BACKWARD_CUES
                and _POSTFIX_VISIBILITY.match(text, cue.end())):

            clause_start = 0

            for boundary in _SCOPE_END.finditer(text, 0, cue.start()):

                clause_start = boundary.end()

            spans.append((clause_start, cue.end()))

            continue

        end = _forward_scope_end(text, cue.end())

        if end > cue.start():

            spans.append((cue.start(), end))

    return spans


def _is_negated(spans: List[Tuple[int, int]], position: int) -> bool:

    return any(start <= position < end for start, end in spans)


# ----------------------------------------------------------
# VISION_SPATIAL_CLUE_POLARITY_SAFETY_V1 — the negation's own predicate
#
# `_forward_scope_end` deliberately stops a negative scope AT the predicate:
#
#     "No stairs, lifts, or other vertical circulation elements are visible
#      on the facade"     -> negates the three elements, not the facade
#
# For an ELEMENT that is exactly right — the element is the NOUN inside the
# scope, and the predicate is where a trailing locative begins.
#
# A SPATIAL CLUE is a different question. Its markers are RELATIONS, and one
# of them is the predicate itself (`visibility` matches "visible"). Stopping
# at the predicate therefore leaves the marker permanently outside the scope,
# so polarity alone cannot see the negation:
#
#     "No corridor is visible."   -> "visible" outside  -> visibility CLUE
#
# which publishes an affirmative visual relationship from a sentence that
# reports the corridor as absent. The same asymmetry exists backwards, where
# `_negation_spans` already puts the cue last ("pitched roof not visible")
# and `_POSTFIX_VISIBILITY` decides the cue's direction but does not extend
# the span over the predicate.
#
# This helper closes that gap FOR SPATIAL CLUES ONLY. The shared
# `_negation_spans` is untouched, so element, material and floor fragments —
# accepted behaviour, and deliberately truncated at the predicate — do not
# move.
# ----------------------------------------------------------

#: A negation's own verb phrase in the FORWARD direction: copula, an optional
#: adverb, then the visibility word. The copula is required here: without it a
#: bare adjective after an unrelated clause could be swallowed.
_CLUE_COPULA_VISIBILITY = re.compile(
    r"\s*(?:is|are|was|were)\s+"
    r"(?:clearly\s+|directly\s+|actually\s+|readily\s+|plainly\s+)?"
    r"(?:visible|seen|shown|present|observable|detectable|confirmable|"
    r"legible|apparent)\b",
    re.IGNORECASE,
)


def _clue_negation_spans(phrase: str) -> List[Tuple[int, int]]:
    """Negation spans used to decide SPATIAL CLUE polarity only.

    Identical to `_negation_spans()` except that each span is extended over
    the negation's OWN postfix visibility predicate, so "no corridor is
    visible" denies the visibility relation as well as the corridor.

    The extension is anchored: it only continues a span that the shared
    matcher has ALREADY placed immediately before the predicate. A clause
    boundary (comma, "but", "however") has therefore already ended the span,
    and no affirmative clause can be dragged into a negation.
    """

    text = _match_text(phrase)

    spans: List[Tuple[int, int]] = []

    for start, end in _negation_spans(text):

        predicate = _CLUE_COPULA_VISIBILITY.match(text, end)

        if not predicate:

            # Backward cue: the span already ends after "not", and the
            # predicate follows it directly.
            predicate = _POSTFIX_VISIBILITY.match(text, end)

        if predicate:

            end = predicate.end()

        spans.append((start, end))

    return spans


def _label_hits(phrase: str, table, *,
                suppress_compound_modifiers: bool = False) -> List[Tuple[str, int]]:
    """Every (label, character offset) occurrence of every marker."""

    text = _match_text(phrase)

    hits: List[Tuple[str, int]] = []

    for label, markers in table:

        for marker in markers:

            for match in _marker_pattern(marker).finditer(text):

                if suppress_compound_modifiers:

                    left, right = _compound_at(text, match.start(), match.end())

                    if (left, right) != (match.start(), match.end()):
                        if _compound_modifier_suppresses(text[left:right]):

                            continue

                hits.append((label, match.start()))

    return hits


def _positive_labels(phrase: str, table, *,
                     suppress_compound_modifiers: bool = False,
                     spans: Optional[List[Tuple[int, int]]] = None,
                     ) -> Tuple[List[str], List[str]]:
    """Split a phrase's labels into (asserted present, asserted absent).

    A label is present when it has at least one occurrence outside every
    negation scope. It is absent only when EVERY occurrence is negated, so a
    mixed sentence keeps its independent clauses.

    ``spans`` — VISION_SPATIAL_CLUE_POLARITY_SAFETY_V1 — an OPTIONAL override
    of the negation spans. The default (`None`) is the shared
    `_negation_spans()` and preserves every existing caller byte for byte. It
    exists for the one caller whose marker can BE the negated predicate; see
    `_clue_negation_spans()`. It is not a general licence to reshape scope.
    """

    if spans is None:

        spans = _negation_spans(_match_text(phrase))

    positive: List[str] = []
    negative: List[str] = []

    for label, start in _label_hits(
            phrase, table,
            suppress_compound_modifiers=suppress_compound_modifiers):

        bucket = negative if _is_negated(spans, start) else positive

        if label not in bucket:

            bucket.append(label)

    present = set(positive)

    return positive, [label for label in negative if label not in present]


# ----------------------------------------------------------
# VISION_MATERIAL_SEMANTICS_V1 — alternatives and hedges
#
# `_positive_labels()` answers "which material terms appear in this phrase?".
# That is not the same question as "which materials does the observer ASSERT?".
# In
#
#     "beige/tan veined stone or marble panels"
#
# the observer named two materials and chose neither. Recording both as
# present turns a decision the observer did NOT make into two architectural
# facts. Recording one would be worse — it invents a choice.
#
# The disjunctive coordinator is the signal. `and` / `with` assert both,
# `/` is genuinely undecided and is left alone, and `or` / `nor` make the
# terms ALTERNATIVES: preserved verbatim, asserted by nobody.
# ----------------------------------------------------------

#: Coordinators that make material terms ALTERNATIVES rather than assertions.
#: `and` is deliberately absent — "brick masonry with stone trim" and "glass
#: windows and steel columns" really do assert both.
_MATERIAL_DISJUNCTION = re.compile(r"\b(?:or|nor)\b", re.IGNORECASE)

#: Separators that continue ONE alternative: whitespace only. "rendered
#: masonry" is one construction (substrate + finish), not two assertions.
_ALT_CONTIGUOUS = re.compile(r"^[\s\-]*$")

#: Separators that continue the same COORDINATION: whitespace and commas. A
#: comma cannot join two independent clauses here, so "stone, marble, or
#: granite" is one alternative set.
_ALT_CHAIN = re.compile(r"^[\s,]*$")


def _material_occurrences(phrase: str) -> List[Tuple[str, int, int]]:
    """Every material marker occurrence as ``(label, start, end)``."""

    text = _match_text(phrase)

    found: List[Tuple[str, int, int]] = []

    for label, markers in MATERIAL_MARKERS:

        for marker in markers:

            for match in _marker_pattern(marker).finditer(text):

                found.append((label, match.start(), match.end()))

    found.sort(key=lambda item: (item[1], item[2]))

    return found


def _alternative_groups(text: str, occurrences):
    """Group material occurrences that a disjunction makes alternatives.

    Returns a list of groups; each group is a list of ALTERNATIVES, and each
    alternative is a list of the occurrences that spell it. Occurrences that
    are not alternatives appear in no group.

    The disjunction is the pivot: the nearest material term on each side is
    anchored to it, then each side is extended over commas and whitespace
    only. That extension is what keeps

        "brick wall with stone or marble cladding"

    from swallowing `brick` — the separator there is " wall with ", not a
    comma — while still collecting

        "stone, marble, or granite"

    into one three-way alternative set.
    """

    if len(occurrences) < 2:

        return []

    groups: List[List[List[Tuple[str, int, int]]]] = []

    for pivot in _MATERIAL_DISJUNCTION.finditer(text):

        left = [item for item in occurrences if item[2] <= pivot.start()]

        right = [item for item in occurrences if item[1] >= pivot.end()]

        if not left or not right:

            continue

        anchor_left = left[-1]

        anchor_right = right[0]

        members = [anchor_left, anchor_right]

        # Extend each side over commas / whitespace only.
        index = occurrences.index(anchor_left)

        while index > 0 and _ALT_CHAIN.match(
                text[occurrences[index - 1][2]:occurrences[index][1]]):

            index -= 1

            members.insert(0, occurrences[index])

        index = occurrences.index(anchor_right)

        while index + 1 < len(occurrences) and _ALT_CHAIN.match(
                text[occurrences[index][2]:occurrences[index + 1][1]]):

            index += 1

            members.append(occurrences[index])

        # Split the group into alternatives at every non-contiguous separator.
        alternatives: List[List[Tuple[str, int, int]]] = [[members[0]]]

        for previous, current in zip(members, members[1:]):

            if _ALT_CONTIGUOUS.match(text[previous[2]:current[1]]):

                alternatives[-1].append(current)

            else:

                alternatives.append([current])

        groups.append(alternatives)

    return groups


def _material_negated(text: str, spans, occurrences, start: int) -> bool:
    """Is this MATERIAL occurrence inside an absence statement?

    `_negation_spans()` is deliberately unchanged. Elements, fragments and the
    D6 scoped-negative contract keep the scope they already have, because
    "no windows or openings above the top window row" is an absence
    RESTRICTED to a region — cutting it at "above" would widen the claim and
    lose the qualifier.

    A MATERIAL is different. When a locative follows a material that is
    already negated, it introduces the SUBSTRATE the material is absent from,
    not a second absence:

        "No plaster on the brick wall"   -> plaster absent, brick VISIBLE
        "no windows or openings above the top window row"
                                         -> no material precedes "above",
                                            so nothing changes here

    This is why the rule lives in the material channel instead of in the
    shared scope computation.
    """

    for span_start, span_end in spans:

        if not (span_start <= start < span_end):

            continue

        earlier = [item[1] for item in occurrences
                   if span_start <= item[1] < start]

        if earlier:

            locative = _LOCATIVE_END.search(text, max(earlier), start)

            if locative:

                return False

        return True

    return False


def _material_semantics(phrase: str):
    """``(asserted, alternatives, absent, hedged)`` for one phrase.

    ``asserted`` keeps the meaning `_positive_labels` already gave it — the
    materials this observation reports — but a term whose every occurrence is
    one side of a disjunction is no longer asserted. It moves to
    ``alternatives`` as verbatim source text, so nothing is lost and nothing
    is invented.

    A label that also occurs OUTSIDE a disjunction stays asserted, exactly as
    `_positive_labels` keeps a label that occurs outside a negation.
    """

    text = _match_text(phrase)

    spans = _negation_spans(text)

    occurrences = _material_occurrences(phrase)

    positive_occurrences = []

    negative_labels: List[str] = []

    for item in occurrences:

        if _material_negated(text, spans, occurrences, item[1]):

            if item[0] not in negative_labels:

                negative_labels.append(item[0])

        else:

            positive_occurrences.append(item)

    asserted: List[str] = []

    for label, _, _ in positive_occurrences:

        if label not in asserted:

            asserted.append(label)

    absent = [label for label in negative_labels if label not in asserted]

    hedged = _material_hedged(phrase)

    if not asserted:

        return asserted, [], absent, hedged

    groups = _alternative_groups(text, positive_occurrences)

    if not groups:

        return asserted, [], absent, hedged

    grouped = {item for group in groups for alt in group for item in alt}

    # A label survives when at least one of its occurrences sits outside every
    # disjunction — "stone balustrade and stone or marble cladding" still
    # asserts stone.
    outside = {item[0] for item in positive_occurrences if item not in grouped}

    kept = [label for label in asserted if label in outside]

    alternatives = [
        [text[alt[0][1]:alt[-1][2]].strip() for alt in group]
        for group in groups
    ]

    return kept, alternatives, absent, hedged


def _material_hedged(phrase: str) -> bool:
    """True when the descriptor hedges the material rather than stating it.

    Reuses the existing hedge vocabulary — no new words. "Possibly marble"
    still names marble; what it does not do is commit to it.
    """

    low = _norm(phrase)

    return any(_norm(term) in low for term in _UNCERTAIN_TERMS)


# ----------------------------------------------------------
# image type
# ----------------------------------------------------------

def _refine_image_type(raw_type: str, evidence: str) -> str:

    # NOTE: the upstream vocabulary uses underscores, and `_norm` folds
    # underscores to spaces — so the lookup key is normalised HERE.
    key = _text(raw_type).lower().replace(" ", "_")

    mapped = _UPSTREAM_IMAGE_TYPE.get(key) or _UPSTREAM_IMAGE_TYPE.get(
        _norm(raw_type), "unknown"
    )

    if mapped in ("plan", "diagram", "unknown"):

        return mapped

    low = _norm(evidence)

    interior = any(_norm(m) in low for m in _INTERIOR_MARKERS)

    exterior = any(_norm(m) in low for m in _EXTERIOR_MARKERS)

    if interior and not exterior:

        return "interior"

    if exterior and not interior:

        return "exterior"

    if interior and exterior:

        return "mixed"

    return mapped


# ----------------------------------------------------------
# visible floors
# ----------------------------------------------------------

# ARCHITECTURAL_EYE_FLOOR_OBSERVATION_V1
#
# A storey count is only usable for architectural acceptance when the
# contract can say WHICH levels it counted and WHETHER they were countable
# at all. The previous implementation returned a single integer and had two
# defects that produced confidently wrong counts:
#
#   * substring matching — "stone facade with three storeys" matched the
#     word "one" inside "stone" and returned 1;
#   * first-digit matching — "42 Oak Street has 3 storeys" returned 42.
#
# Both are fixed by requiring a number token ADJACENT to a floor noun.
# The contract is extended (never replaced) so a consumer can separate a
# ground floor from upper floors, exclude a roof parapet, record a hedged
# reading, and refuse to call a count "countable" when the building is
# cropped. Existing keys keep their meaning.

#: A ground floor IS a real storey and counts, but it is stated separately
#: from upper storeys and must never be dropped from the total.
_GROUND_TERMS = (
    "ground floor", "ground-floor", "ground floor level", "ground storey",
    "ground story", "ground level", "street level", "at grade",
    "همکف", "طبقه همکف", "هم کف",
)

#: "two upper floors" means two storeys ABOVE ground, i.e. three in total.
_UPPER_TERMS = (
    "upper floor", "upper floors", "upper storey", "upper storeys",
    "upper story", "upper stories", "upper level", "upper levels",
    "طبقات بالا", "طبقه بالا", "طبقات فوقانی",
)

#: A parapet, roof terrace or attic is NOT an occupiable storey.
_ROOF_BAND_TERMS = (
    "parapet", "roof terrace", "roof deck", "roof garden", "roof band",
    "roof-level", "roof level", "roof gable", "roof dormer", "attic",
    "جان پناه", "جان‌پناه", "تراس بام", "شیروانی",
)

#: Hedged wording is reported, but at LOW confidence with an explicit
#: uncertainty record — never silently promoted to a firm count.
_UNCERTAIN_TERMS = (
    "apparent", "apparently", "appears", "appear to", "possibly",
    "probably", "maybe", "perhaps", "ambiguous", "unclear", "uncertain",
    "hard to tell", "difficult to tell", "approximately", "roughly",
    "نامشخص", "شاید", "احتمالا", "تقریبا", "مبهم",
)

#: Whole-building visibility. V1/V2 asserted counts on cropped images; a
#: count that cannot be seen in full is not a countable count.
_FRAMING_COMPLETE_TERMS = (
    "complete building", "whole building", "entire building", "full building",
    "building is fully", "fully visible", "fully in frame", "complete facade",
    "entire facade", "full height visible",
    "کل ساختمان", "ساختمان کامل", "تمام ساختمان", "کامل در کادر", "نمای کامل",
)

_FRAMING_CROPPED_TERMS = (
    "cropped", "cut off", "truncated", "partially visible", "partly visible",
    "extends beyond", "beyond the frame", "out of frame", "not fully visible",
    "partly cropped", "incomplete",
    "بریده", "کامل نیست", "خارج از کادر",
)


def _floor_tokens(text: str) -> List[str]:
    """Word and digit tokens. Hyphens and ZWNJ split, so "three-storey"
    and "سه‌طبقه" both yield a number token adjacent to a noun token."""

    flat = (
        text.replace("-", " ")
        .replace("\u2010", " ")
        .replace("\u2011", " ")
        .replace("\u200c", " ")
    )

    return re.findall(r"[0-9]+|[^\W\d_]+", flat)


def _count_near(tokens: List[str], index: int, nouns: set, window: int = 3) -> Optional[int]:
    """The nearest number within ``window`` tokens BEFORE ``index``.

    Stops at any other floor noun, so the search can never cross a noun
    boundary and grab an unrelated number.

    This is adjacency-with-qualifiers. It lets the two real phrasings read —
    "two upper floors" and "four apparent storeys", where a qualifier sits
    between the number and the noun — while still refusing the defect case
    "42 Oak Street has 3 storeys" -> 42, because the walk stops at "3".
    """

    for back in range(1, window + 1):

        position = index - back

        if position < 0:

            break

        token = tokens[position]

        if token in nouns:

            break

        if token.isdigit():

            return int(token)

        if token in _FLOOR_WORDS:

            return _FLOOR_WORDS[token]

    return None


def _floor_defaults(reading: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill the extended keys on a reading the provider supplied itself,
    without ever overwriting what the provider actually said."""

    reading.setdefault("count_scope", "TOTAL" if reading.get("count") is not None
                       else "MULTI_STOREY_UNDETERMINED")
    reading.setdefault("count_is_total", reading.get("count") is not None)
    reading.setdefault("ground_floor_included", None)
    reading.setdefault("upper_floors", None)
    reading.setdefault("roof_band_excluded", [])
    reading.setdefault("uncertain_bands", [])
    reading.setdefault("whole_building_visible", None)
    reading.setdefault("countable", None)

    return reading


def _read_floor_phrase(phrase: str) -> Optional[Dict[str, Any]]:
    """Read ONE provider phrase. Returns None when it makes no floor claim."""

    low = _norm(phrase)

    flat = (
        low.replace("-", " ")
        .replace("\u2010", " ")
        .replace("\u2011", " ")
        .replace("\u200c", " ")
    )

    tokens = _floor_tokens(low)

    nouns = {_norm(noun) for noun in _FLOOR_NOUNS}

    multi = any(_norm(marker) in flat for marker in _FLOOR_MULTI)

    if not any(token in nouns for token in tokens) and not multi:

        return None

    ground = any(term in flat for term in _GROUND_TERMS)
    upper = any(term in flat for term in _UPPER_TERMS)
    roof_bands = [term for term in _ROOF_BAND_TERMS if term in flat]
    uncertain = any(term in flat for term in _UNCERTAIN_TERMS)

    # ---- a number attached to a floor noun, by adjacency only ----
    stated = None
    upper_stated = None

    for index, token in enumerate(tokens):

        if token not in nouns:

            continue

        number = _count_near(tokens, index, nouns)

        if number is None:

            continue

        # "two UPPER floors" — the upper marker sits between number and noun
        window = " ".join(tokens[max(0, index - 3):index])

        if any(marker in window for marker in ("upper", "بالا", "فوقانی")):

            if upper_stated is None:

                upper_stated = number

        if stated is None:

            stated = number

    # ---- ground + N upper floors: the ground floor must be added ----
    if ground and upper_stated is not None:

        count = upper_stated + 1
        count_scope = "TOTAL"
        ground_included: Optional[bool] = True
        upper_floors: Optional[int] = upper_stated
        rule = "ground_floor_plus_upper_floors"

    elif stated is not None:

        count = stated

        if upper and not ground:

            count_scope = "UPPER_ONLY"
            ground_included = False
            upper_floors = stated

        else:

            count_scope = "TOTAL"
            ground_included = None
            upper_floors = None

        rule = "number_adjacent_to_floor_noun"

    elif multi:

        count = None
        count_scope = "MULTI_STOREY_UNDETERMINED"
        ground_included = None
        upper_floors = None
        rule = "multi_storey_descriptor"

    else:

        return None

    # ---- whole-building visibility is applied by the caller ----
    # It is a property of the IMAGE, not of the count sentence, and the
    # evidence for it usually arrives in a DIFFERENT phrase ("complete
    # building", "cropped"). `detect_visible_floors` aggregates it across
    # every phrase and applies it here, so a count read from one sentence
    # still knows whether the building was fully in frame.
    uncertain_bands: List[Dict[str, Any]] = []

    if uncertain:

        uncertain_bands.append({
            "kind": "hedged_count",
            "count_as_stated": count,
            "reason": "the provider hedged this reading; it is not a firm count",
            "evidence_phrase": phrase,
        })

    reading: Dict[str, Any] = {
        "count": count,
        "evidence_phrase": phrase,
        "confidence": "LOW" if uncertain else "MEDIUM",
        "count_scope": count_scope,
        "count_is_total": count_scope == "TOTAL",
        "ground_floor_included": ground_included,
        "upper_floors": upper_floors,
        "roof_band_excluded": roof_bands,
        "uncertain_bands": uncertain_bands,
        "whole_building_visible": None,
        "countable": None,
        "provenance": {
            "source": "provider_phrase",
            "phrase": phrase,
            "rule": rule,
        },
    }

    if count is None:

        reading["descriptor"] = "multi-storey"

    return reading


def _whole_building_visibility(phrases: List[str]) -> Optional[bool]:
    """True when the provider said the whole building is in frame, False
    when it said the image is cropped, None when it said neither.

    Cropped wins over complete: if any phrase reports cropping, the count is
    not trustworthy regardless of what another phrase claims.
    """

    seen_complete = False

    for phrase in phrases:

        flat = _norm(phrase).replace("-", " ")

        if any(term in flat for term in _FRAMING_CROPPED_TERMS):

            return False

        if any(term in flat for term in _FRAMING_COMPLETE_TERMS):

            seen_complete = True

    return True if seen_complete else None


def _apply_framing(reading: Dict[str, Any], visible: Optional[bool]) -> Dict[str, Any]:
    """Attach image-level framing to a count reading and settle `countable`.

    A count that cannot be seen in full is not a countable count — that is
    the V1/V2 lesson, where a count was asserted on a cropped render.
    """

    reading["whole_building_visible"] = visible

    if reading.get("count") is None:

        reading["countable"] = False

    elif visible is False:

        reading["countable"] = False

    elif visible is True:

        reading["countable"] = True

    else:

        reading["countable"] = None

    return reading


def detect_visible_floors(phrases: List[str]) -> Optional[Dict[str, Any]]:

    """The visible floor count, ONLY when the provider actually stated it."""

    visible = _whole_building_visibility(phrases)

    for phrase in phrases:

        reading = _read_floor_phrase(phrase)

        if reading is not None:

            return _apply_framing(reading, visible)

    return None


def _provider_floors(extras: Dict[str, Any]) -> Optional[Dict[str, Any]]:

    """The provider's OWN visible_floors statement, when it made one."""

    value = extras.get("visible_floors")

    if isinstance(value, bool) or value is None:

        return None

    if isinstance(value, (int, float)):

        return _floor_defaults({
            "count": int(value),
            "evidence_phrase": str(value),
            "confidence": "MEDIUM",
        })

    if isinstance(value, dict):

        # The provider may supply its own per-level reading. Its values are
        # authoritative and are never overwritten; only the extended keys it
        # did not state are backfilled.
        return _floor_defaults(dict(value))

    text = _text(value)

    if not text or _norm(text) in ("null", "none", "unknown", "n/a"):

        return None

    return detect_visible_floors([text]) or _floor_defaults({
        "count": None,
        "descriptor": text,
        "evidence_phrase": text,
        "confidence": "MEDIUM",
    })


# ----------------------------------------------------------
# VISION_FLOOR_SUPERSESSION_TRUTH_V1 — what "verified" must mean here
#
# `visible_floors_observation.superseded_by_verified` claimed that a VERIFIED
# replacement had displaced the provider's observation. It was computed as
# `bool(_verified_floors)`, and `_verified_floors` is
#
#     _provider_floors(extras) or detect_visible_floors(visible_phrases)
#
# — BOTH read the PROVIDER's own statement. A reported count is not a verified
# count, so the flag asserted verification whenever ANY reading existed. In
# facade C it asserted it while `visible_floors.count` was null: nothing had
# been replaced, and nothing had been verified.
#
# The flag is now true only when the primary reading carries an explicit
# verification record that is not the provider's own claim:
#
#   * a count actually exists — a null count supersedes nothing;
#   * `verification` is exactly "VERIFIED";
#   * `authoritative` is true;
#   * a `provenance` block names a source, and that source is not the
#     provider-phrase path.
#
# V1.1 CORRECTION: those four conditions are necessary but NOT sufficient, and
# on their own they were not a trust boundary at all — see
# `_FLOOR_INDEPENDENT_PRODUCERS` below. The reading must additionally come
# from an authorized producer, and no such producer exists today.
#
# NO PRODUCER IN THIS PIPELINE SATISFIES THESE CONDITIONS TODAY. There is no
# independent floor-count verification step: `local_evidence_trust_v1` verifies
# OCR text and plan structure, not storeys, and `architectural_vision_
# interpreter_v1` records that a photograph carries no independent local storey
# evidence. The flag therefore stays false for every current input, and a future
# verification producer can set it without redefining the field. Inventing a
# verification source merely to make the flag true is explicitly not permitted.
# ----------------------------------------------------------

_FLOOR_PROVIDER_SOURCES = ("provider_phrase", "provider_statement")

# VISION_FLOOR_VERIFICATION_TRUST_BOUNDARY_V1_1 -------------------------
#
# V1 above checked the CONTENT of the reading: it rejected two provenance
# strings. But `_provider_floors()` returns `_floor_defaults(dict(value))`,
# which preserves EVERY field the provider supplied — `verification`,
# `authoritative` and `provenance` included. So a provider-controlled payload
# could simply declare itself verified and pass that check:
#
#     {"visible_floors": {"count": 3, "verification": "VERIFIED",
#                         "authoritative": True,
#                         "provenance": {"source": "local_raster_geometry"}}}
#
# A source name is a CLAIM about provenance, not proof of provenance. No
# allowlist of trusted-looking strings can fix that: `local_raster_geometry`,
# `local_plan_sheet_v1` and `local_raster_symbol_topology` are real internal
# names, so trusting the string is precisely what makes the spoof work.
#
# Verification is therefore decided by WHO PRODUCED the reading, and the
# producer identity is supplied by the CALLER — never read out of the payload.
# The registry of producers authorized to assert an independent floor count is
# EMPTY, because this pipeline has none: `local_evidence_trust_v1` verifies OCR
# text and plan structure, not storeys, and the vision interpreter records that
# a photograph carries no independent local storey evidence. Both branches of
# `_verified_floors` — `_provider_floors()` and `detect_visible_floors()` — read
# the provider's own statement, so both are provider-derived and neither can
# supersede anything.
#
# A future real verification source needs its own authorized integration
# contract and an entry in `_FLOOR_INDEPENDENT_PRODUCERS`. It must NOT be
# simulated by adding self-declared metadata to provider input.
# ----------------------------------------------------------------------

_FLOOR_INDEPENDENT_PRODUCERS: Tuple[str, ...] = ()

# The identity passed for readings the builder derived from provider text.
_FLOOR_PROVIDER_DERIVED = "provider_derived"


def _floor_count_is_valid(count: Any) -> bool:
    """A storey count is a POSITIVE INTEGER.

    A non-null value is not necessarily a count. `True` is an `int` in Python,
    "3" is a string, 0 and -1 count no storeys, and 2.7 is not a whole number
    of them. None of these may establish a verified replacement.
    """

    return isinstance(count, int) and not isinstance(count, bool) and count > 0


def _floor_reading_is_verified(
    reading: Any,
    *,
    producer: Optional[str] = None,
) -> bool:
    """True only for an INDEPENDENTLY verified floor count.

    Trust is decided by `producer`, which the CALLER supplies and the payload
    cannot set. See the note above `_FLOOR_INDEPENDENT_PRODUCERS`: no producer
    is authorized today, so this returns False for every current input. A
    populated dict, a plausible source name and a self-declared `VERIFIED` are
    all insufficient — a fabricated reading cannot satisfy the check merely by
    carrying the right keys.
    """

    if producer not in _FLOOR_INDEPENDENT_PRODUCERS:

        return False

    if not isinstance(reading, dict):

        return False

    if not _floor_count_is_valid(reading.get("count")):

        return False

    if reading.get("verification") != "VERIFIED":

        return False

    if reading.get("authoritative") is not True:

        return False

    provenance = reading.get("provenance")

    if not isinstance(provenance, dict):

        return False

    source = provenance.get("source")

    if not isinstance(source, str) or not source:

        return False

    return source not in _FLOOR_PROVIDER_SOURCES


# ----------------------------------------------------------
# the builder
# ----------------------------------------------------------

def _absence_phrases(raw: Any) -> List[str]:
    """The model-reported absence phrases forwarded by the vision bridge.

    D6_NEGATIVE_EVIDENCE_BRIDGE_V1 — these are claims the verifier refused as
    verified absence (`negative_claim_requires_explicit_local_absence`) and
    that the attributed band therefore excluded. They are carried here so the
    absence is still RECORDED, never so it is asserted as fact. Accepts the
    bridge's structured entries or plain strings, de-duplicated, in order.
    """

    values = raw.get("absence_attributed") if isinstance(raw, dict) else None

    out: List[str] = []

    for entry in values or []:

        text = entry.get("text") if isinstance(entry, dict) else entry

        text = _norm(text) if isinstance(text, str) else ""

        if text and text not in out:

            out.append(text)

    return out


def build_architectural_observation(
    raw: Any,
    *,
    provider: str = "none",
    model: str = "none",
    prompt_version: Optional[str] = None,
    image_id: Optional[str] = None,
    source_type: str = "other",
    elapsed_s: Optional[float] = None,
    upstream_understanding: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    """Build the loss-free architectural observation from the RAW output."""

    if not isinstance(raw, dict):

        raw = {}

    # ---- RULE 3: the raw output is preserved verbatim -------------------
    raw_observations = copy.deepcopy(raw)

    observed = _as_list(raw.get("observed"))
    inferred = _as_list(raw.get("inferred"))
    elements_in = _as_list(raw.get("architectural_elements"))
    labels = _as_list(raw.get("text_labels_if_visible"))

    local_plan_reading = raw.get("local_plan_reading")

    if not isinstance(local_plan_reading, dict):

        local_plan_reading = None

    local_labels = (
        local_plan_reading.get("labels") or []
        if local_plan_reading
        and local_plan_reading.get("status") == "grounded"
        else []
    )

    local_owns_plan = bool(
        local_plan_reading and (
            local_plan_reading.get("status") == "grounded"
            or local_plan_reading.get("symbol_analysis_status") == "analyzed"
        )
    )

    low_trust_local = []
    stable_local = []
    independent_texts = set()

    if local_owns_plan:

        # VISION_RETENTION_FIX_V2 — three fail-closed OCR trust tiers. Only an
        # INDEPENDENTLY verified label may act as a GROUNDED source label. A
        # STABLE label (several passes of ONE engine over ONE image) is
        # reportable AS OCR but never architectural truth, and a lexicon
        # substitution is audit-only. Nothing is deleted: raw OCR, box,
        # correction and match score are preserved for every tier.
        from core.vision.local_evidence_trust_v1 import (
            INDEPENDENTLY_VERIFIED_OCR, STABLE_LOCAL_OCR,
            independently_verified_ocr_texts, low_trust_record, ocr_trust_state,
            stable_local_record,
        )

        independent_texts = independently_verified_ocr_texts(raw)

        trusted_local = []

        for entry in local_labels:

            if not isinstance(entry, dict):

                continue

            state = ocr_trust_state(entry, independent_texts)

            if state == INDEPENDENTLY_VERIFIED_OCR:

                trusted_local.append(entry)

            elif state == STABLE_LOCAL_OCR:

                stable_local.append(stable_local_record(entry))

            else:

                low_trust_local.append(low_trust_record(entry, independent_texts))

        # Grounded source text is authoritative for transcription.  The
        # provider version remains untouched in `raw_observations` for audit,
        # but cannot rename, add or remove published source labels.
        labels = [
            _text(entry.get("text"))
            for entry in trusted_local
            if isinstance(entry, dict) and _text(entry.get("text"))
        ]

    # ARCHITECTURAL_VISION_LABEL_COMPLETENESS_V1 — the VERBATIM
    # transcription, multiplicity preserved. `labels` above stays
    # de-duplicated for the existing consumers.
    labels_verbatim = _as_list_keep_duplicates(
        labels if local_owns_plan else raw.get("text_labels_if_visible")
    )

    # LOCAL_PLAN_READING_V1 — when the grounded local reader supplied the
    # source labels, the provider's OWN list is kept as a separate,
    # explicitly provider-only claim record so the precedence stays
    # auditable instead of being hidden in `raw_observations`.
    provider_labels = (
        _as_list_keep_duplicates(raw.get("text_labels_if_visible"))
        if local_owns_plan
        else []
    )
    model_unresolved = _as_list(raw.get("unresolved"))

    # ARCHITECTURAL_OBSERVATION_V1 — the v3 provider categories, carried
    # through the understanding contract as `observation_extras`.
    extras = raw.get("observation_extras")

    if not isinstance(extras, dict):

        # the RAW provider output carries them at the TOP LEVEL; the
        # understanding contract carries them under `observation_extras`.
        extras = {
            key: raw.get(key)
            for key in (
                "visible_floors",
                # ARCHITECTURAL_EYE_EVIDENCE_TIER_HANDOFF_V1 — lower-trust
                # storey reading. Deliberately a DIFFERENT key from
                # `visible_floors`: this one never reaches an authoritative
                # consumer.
                "visible_floors_observation",
                "material_observations",
                "texture_color_observations",
                "style_indicators",
                "spatial_clues",
                "furniture_elements",
                "object_elements",
            )
            if raw.get(key) not in (None, [], "", {})
        }

    extra_groups: List[List[str]] = []

    for key in (
        "visible_floors",
        "material_observations",
        "texture_color_observations",
        "style_indicators",
        "spatial_clues",
        "furniture_elements",
        "object_elements",
    ):

        value = extras.get(key)

        if isinstance(value, str):

            extra_groups.append([value])

        else:

            extra_groups.append(_as_list(value))

    # every phrase the provider returned, in order, de-duplicated
    all_phrases: List[str] = []

    for group in [observed, inferred, elements_in, labels] + extra_groups:

        for phrase in group:

            if phrase not in all_phrases:

                all_phrases.append(phrase)

    # A floor count is "visible" ONLY when the provider stated it as an
    # OBSERVATION (or in its explicit v3 `visible_floors` key). An
    # `inferred` guess is not visible evidence and never becomes a count.
    visible_phrases: List[str] = []

    for group in [observed, elements_in] + extra_groups:

        for phrase in group:

            if phrase not in visible_phrases:

                visible_phrases.append(phrase)

    # ---- RULE 1: every phrase is LABELLED, never dropped ----------------
    architectural_elements: List[Dict[str, Any]] = []
    furniture_elements: List[Dict[str, Any]] = []
    object_elements: List[Dict[str, Any]] = []
    unclassified: List[Dict[str, Any]] = []
    #: R2_NEGATION_MATERIAL_INTEGRITY_V1 — elements or materials that the text
    #: names ONLY inside a negation. They are evidence of ABSENCE and must never
    #: be reported as visible. Preserved verbatim, never discarded.
    #:
    #: R2_USER_FACING_EYE_HANDOFF_V1 — a MIXED sentence ("Exposed masonry …,
    #: no plaster or cladding") is no longer treated as wholly present or
    #: wholly absent: its positive part stays visible AND its negated part is
    #: recorded here. One entry per phrase, merged across kind and material.
    negative_observations: List[Dict[str, Any]] = []
    placed_positive: set = set()

    def _negated_fragments(phrase):
        """The verbatim sub-spans of `phrase` that actually state absence.

        Each fragment is a contiguous slice of the original wording — never a
        reconstruction — so the report can name only the negative clause of a
        mixed sentence ("no plaster or cladding") instead of reprinting the
        whole sentence.
        """

        fragments = []

        for start, end in _negation_spans(phrase.lower()):

            # Keep a restrictive qualifier with the negation it restricts; see
            # `_RESTRICTIVE_QUALIFIER`. Display only — the span that decides
            # which elements are positive is computed above and unchanged.
            end = _extend_over_restriction(phrase.lower(), end)

            fragment = phrase[start:end].strip(" ,;:()[]")

            if fragment and fragment not in fragments:

                fragments.append(fragment)

        return fragments

    def _record_negative(phrase, kinds=None, materials=None):
        """Record (or merge) the negated part of one phrase."""

        for existing in negative_observations:

            if existing.get("evidence_phrase") == phrase:

                if kinds:
                    for label in kinds:
                        if label not in existing.setdefault("kind", []):
                            existing["kind"].append(label)

                if materials:
                    for material in materials:
                        if material not in existing.setdefault("materials", []):
                            existing["materials"].append(material)

                return

        record = {
            "evidence_phrase": phrase,
            "status": "absent",
            "confidence": _phrase_confidence(phrase, observed),
        }

        if kinds:

            record["kind"] = list(kinds)

        if materials:

            record["materials"] = list(materials)

        fragments = _negated_fragments(phrase)

        if fragments:

            record["negated_texts"] = fragments

        negative_observations.append(record)

    for phrase in all_phrases:

        arch, arch_absent = _positive_labels(
            phrase, ARCHITECTURAL_ELEMENT_MARKERS,
            suppress_compound_modifiers=True)
        furn, furn_absent = _positive_labels(phrase, FURNITURE_MARKERS)
        obj, obj_absent = _positive_labels(phrase, OBJECT_MARKERS)

        entry = {
            "evidence_phrase": phrase,
            "status": "visible",
            "confidence": _phrase_confidence(phrase, observed),
        }

        placed = False

        if arch:

            architectural_elements.append(dict(entry, kind=arch))

            placed = True

        if furn:

            furniture_elements.append(dict(entry, kind=furn))

            placed = True

        if obj:

            object_elements.append(dict(entry, kind=obj))

            placed = True

        if placed:

            placed_positive.add(phrase)

        absent_kinds: List[str] = []

        for group in (arch_absent, furn_absent, obj_absent):

            for label in group:

                if label not in absent_kinds:

                    absent_kinds.append(label)

        # A MIXED sentence keeps both halves: the positive kinds stay in
        # `architectural_elements`, the negated kinds are recorded as absence.
        if absent_kinds:

            _record_negative(phrase, kinds=absent_kinds)

        if not placed and not absent_kinds:

            unclassified.append(entry)

    # ==================================================
    # D6_NEGATIVE_EVIDENCE_BRIDGE_V1 — MODEL-REPORTED ABSENCE
    #
    # A negative claim whose subject is a RECOGNISED element kind never
    # reaches `all_phrases`: the verifier marks it
    # `negative_claim_requires_explicit_local_absence` and the bridge's
    # attributed band admits only `no_applicable_independent_corroboration`.
    # The absence then disappeared entirely — lost precisely BECAUSE its
    # subject was an element.
    #
    # The bridge now forwards those claims in `absence_attributed`, and this
    # pass records them as ABSENCE ONLY:
    #   * `_record_negative` writes an absence record, never an element;
    #   * nothing is appended to `architectural_elements`;
    #   * a phrase already placed as a POSITIVE is skipped, so a negative can
    #     never erase positive evidence;
    #   * the verbatim scope is kept, so "no windows above the top row" never
    #     becomes "no windows";
    #   * the record is still an absence OBSERVATION, not proof that the
    #     element cannot exist.
    # ==================================================

    for phrase in _absence_phrases(raw):

        if phrase in placed_positive:

            continue

        absent_labels: List[str] = []

        for markers in (
            ARCHITECTURAL_ELEMENT_MARKERS,
            FURNITURE_MARKERS,
            OBJECT_MARKERS,
        ):

            for label in _positive_labels(phrase, markers)[1]:

                if label not in absent_labels:

                    absent_labels.append(label)

        # Recorded even when no vocabulary label matches, so an explicit
        # absence about an unrecognised roof element is preserved verbatim
        # instead of being silently dropped.
        _record_negative(phrase, kinds=absent_labels or None)

    # Local symbol observations have item-local provenance. Provider phrases
    # remain verbatim in raw_observations but are not asserted as local objects.
    from core.vision.local_plan_symbols_v1 import grounded_plan_items
    from core.vision.local_plan_elements_v1 import grounded_plan_elements

    local_furniture = grounded_plan_items(local_plan_reading)
    local_elements = grounded_plan_elements(local_plan_reading)
    if local_plan_reading and local_plan_reading.get("element_analysis_status") == "analyzed":
        target_types = {"window", "door", "opening", "stair", "duct", "column", "axis", "level"}
        for entry in architectural_elements:
            if target_types.intersection(entry.get("kind") or []):
                entry["status"] = "provider_only"
                entry["source"] = "provider_only"
        architectural_elements.extend(
            dict(item, kind=[item["type"]], evidence_phrase=item["evidence"])
            for item in local_elements
        )
    if local_plan_reading and local_plan_reading.get("status") == "grounded":
        for entry in furniture_elements:
            entry["status"] = "provider_only"
            entry["source"] = "provider_only"
        furniture_elements = [
            dict(item, evidence_phrase=item["name"], kind=[item["class"]])
            for item in local_furniture
        ]

    # ---- materials / texture / colour -----------------------------------
    material_observations: List[Dict[str, Any]] = []
    texture_color: List[Dict[str, Any]] = []

    for phrase in all_phrases:

        # VISION_MATERIAL_SEMANTICS_V1 — `materials` is what the observer
        # ASSERTED. A term offered only as one side of an "or" is preserved
        # verbatim in `material_alternatives` and asserted by nobody.
        materials, material_alternatives, materials_absent, hedged = (
            _material_semantics(phrase))
        textures = _labels(phrase, TEXTURE_MARKERS)
        colours = _labels(phrase, COLOR_MARKERS)

        if materials or material_alternatives:

            entry = {
                "descriptor": phrase,
                "materials": materials,
                "evidence_phrase": phrase,
                "confidence": _phrase_confidence(phrase, observed),
            }

            if material_alternatives:

                entry["material_alternatives"] = material_alternatives

            if hedged:

                entry["hedged"] = True

            material_observations.append(entry)

        # R2_USER_FACING_EYE_HANDOFF_V1 — a mixed material sentence keeps its
        # positive materials AND records the negated ones. "Exposed masonry …,
        # no plaster or cladding" is masonry present, plaster absent — never a
        # whole-sentence verdict in either direction.
        if materials_absent:

            _record_negative(phrase, materials=materials_absent)

        if textures or colours:

            texture_color.append({
                "descriptor": phrase,
                "textures": textures,
                "colours": colours,
                "evidence_phrase": phrase,
                "confidence": _phrase_confidence(phrase, observed),
            })

    # ---- style indicators -----------------------------------------------
    style_indicators: List[Dict[str, Any]] = []

    for phrase in all_phrases:

        present_kinds, _ = _positive_labels(phrase, STYLE_MARKERS)

        for kind, markers in STYLE_MARKERS:

            if kind in present_kinds:

                style_indicators.append({
                    "kind": kind,
                    "descriptor": phrase,
                    "evidence_phrase": phrase,
                    "confidence": "LOW",
                })

                break

    # ---- spatial clues ---------------------------------------------------
    #
    # VISION_SPATIAL_CLUE_POLARITY_SAFETY_V1 — a spatial clue is an ASSERTED
    # relationship, and the clue contract has no way to say "absent": its four
    # kinds map to affirmative relationship kinds only (adjacency,
    # circulation_path, visibility) and the record carries no polarity field.
    # Publishing one from a negated clause therefore states a relationship the
    # observer denied:
    #
    #     "No adjacent entrance is visible."  -> adjacency
    #
    # The previous rule was the same polarity-blind substring test that
    # `style_indicators` carried before VISION_STYLE_INDICATOR_POLARITY_SAFETY_V1:
    #
    #     if any(_norm(m) in _norm(phrase) for m in markers):
    #
    # A clue now requires a marker occurrence OUTSIDE every negation scope, via
    # the project's existing `_positive_labels()`. A mixed sentence keeps its
    # independently supported clause, exactly as elements and materials do.
    #
    # `_clue_negation_spans()` — not `_negation_spans()` — because the
    # `visibility` marker is the predicate itself ("is visible"), which the
    # shared scope deliberately leaves outside.
    #
    # Absence is not lost: it stays in `negative_observations`, where it was
    # already recorded. Nothing is promoted and nothing is invented.
    spatial_clues: List[Dict[str, Any]] = []

    for phrase in all_phrases:

        present_clue_kinds, _ = _positive_labels(
            phrase, SPATIAL_CLUE_MARKERS, spans=_clue_negation_spans(phrase))

        for kind, markers in SPATIAL_CLUE_MARKERS:

            if kind in present_clue_kinds:

                spatial_clues.append({
                    "kind": kind,
                    "between": [],
                    "evidence_phrase": phrase,
                    "confidence": "LOW",
                })

                break

    # ---- RULE 2: unknown ONLY when evidence is truly absent -------------
    evidence_text = _norm(" ".join(all_phrases))

    category_evidence = {
        "material": bool(material_observations),
        "texture": bool(texture_color),
        "colour": bool(texture_color),
        "floor": bool(detect_visible_floors(visible_phrases)),
        "furniture": bool(furniture_elements),
        "window": any("window" in e.get("kind", []) for e in architectural_elements),
        "door": any("door" in e.get("kind", []) for e in architectural_elements),
        "wall": any("wall" in e.get("kind", []) for e in architectural_elements),
        "balcony": any("balcony" in e.get("kind", []) for e in architectural_elements),
        "room": any("room" in _norm(p) for p in all_phrases),
    }

    unknowns: List[Dict[str, Any]] = []
    resolved_uncertainties: List[Dict[str, Any]] = []

    for phrase in model_unresolved:

        low = _norm(phrase)

        answered = any(
            key in low and present
            for key, present in category_evidence.items()
        )

        if answered:

            resolved_uncertainties.append({
                "model_phrase": phrase,
                "reason": "the provider also reported visible evidence for this",
            })

        else:

            unknowns.append({
                "name": phrase,
                "status": "no visible evidence",
                "confidence": "UNKNOWN",
            })

    # ---- ARCHITECTURAL_EYE_EVIDENCE_TIER_HANDOFF_V1 ---------------------
    #
    # Two tiers, two keys, never merged:
    #   visible_floors              -> verified / derived count (unchanged)
    #   visible_floors_observation  -> provider's stated count, UNVERIFIED
    #
    # Keeping them apart is what lets an observation survive without being
    # mistaken for a fact. The verified tier is computed exactly as before,
    # so every existing consumer sees byte-identical behaviour.
    _verified_floors = _provider_floors(extras) or detect_visible_floors(visible_phrases)

    def _floor_observation_slot(_extras, _verified):
        """Project the lower-trust reading, forcing its tier invariants."""

        reading = _extras.get("visible_floors_observation")

        if not isinstance(reading, dict):

            return None

        out = copy.deepcopy(reading)

        # These three are non-negotiable regardless of what arrived.
        out["trust_tier"] = "PROVIDER_OBSERVATION"
        out["verification"] = "UNVERIFIED"
        out["authoritative"] = False
        out["confidence"] = "LOW"

        # Verified evidence always takes precedence; this only records that
        # the observation exists, not that it was adopted.
        #
        # VISION_FLOOR_SUPERSESSION_TRUTH_V1 — a true value now requires a REAL
        # verified replacement. `_verified` is a provider-derived reading, so
        # `bool(_verified)` asserted verification for every populated count.
        #
        # VISION_FLOOR_VERIFICATION_TRUST_BOUNDARY_V1_1 — `_verified` is
        # ALWAYS provider-derived: both `_provider_floors()` and
        # `detect_visible_floors()` read the provider's own statement, and
        # `_provider_floors()` forwards the provider's dict verbatim, so any
        # `verification` / `authoritative` / `provenance` inside it is the
        # provider's claim about itself. The producer identity is therefore
        # stated here, by the caller, and no producer is authorized to assert
        # an independent floor count today.
        out["superseded_by_verified"] = _floor_reading_is_verified(
            _verified, producer=_FLOOR_PROVIDER_DERIVED
        )

        return out

    # ---- the contract ----------------------------------------------------
    observation = {
        "contract": CONTRACT,
        "version": VERSION,

        "image_id": image_id,
        "source_type": source_type,

        # ---- 1. image type ----
        "image_type": _refine_image_type(raw.get("image_type"), evidence_text),

        # ---- 2. visible floors (VERIFIED / derived only) ----
        "visible_floors": _verified_floors,

        # ---- 2b. lower-trust storey OBSERVATION ----
        #
        # ARCHITECTURAL_EYE_EVIDENCE_TIER_HANDOFF_V1. A provider's stated
        # storey count that nothing could independently corroborate. It is
        # kept in its OWN key, never merged into `visible_floors`, because
        # that key is treated as authoritative by
        # `architectural_vision_interpreter_v1` (it deletes floor unknowns)
        # and `design_constraint_fidelity_v1` (it verifies a requested count
        # and can yield a render PASS). An unverified reading in that key
        # would erase an honest uncertainty and could manufacture acceptance.
        "visible_floors_observation": _floor_observation_slot(
            extras, _verified_floors
        ),

        # ---- 3. architectural elements ----
        "architectural_elements": architectural_elements,
        "grounded_element_evidence": copy.deepcopy(local_elements),

        # ---- 4. furniture / objects ----
        "furniture_elements": furniture_elements,
        "grounded_furniture_evidence": copy.deepcopy(local_furniture),
        "object_elements": object_elements,
        "unclassified_observations": unclassified,

        # ---- 4b. ABSENCE evidence (never a visible element) ----
        #
        # R2_NEGATION_MATERIAL_INTEGRITY_V1. A phrase that names an element or
        # material ONLY inside a negation is evidence of absence. It is kept
        # verbatim here so nothing is lost, and deliberately kept OUT of
        # `architectural_elements` / `material_observations`, which assert
        # presence. Additive key: every existing consumer is unaffected.
        "negative_observations": negative_observations,

        # ---- 5. spatial clues ----
        "spatial_clues": spatial_clues,

        # ---- 6. material observations ----
        "material_observations": material_observations,

        # ---- 7. texture / colour observations ----
        "texture_color_observations": texture_color,

        # ---- 8. style indicators ----
        "style_indicators": style_indicators,

        # ---- 9. confidence ----
        "confidence": _text(raw.get("confidence")).upper() or "LOW",

        # ---- 10. evidence provenance ----
        "provenance": {
            "provider": provider,
            "model": model,
            "prompt_version": prompt_version,
            "image_id": image_id,
            "source_type": source_type,
            "elapsed_s": elapsed_s,
            "raw_preserved": True,
        },

        # ---- RULE 3: the verbatim provider output ----
        "raw_observations": raw_observations,

        # ---- what the provider said it could not determine ----
        "model_unresolved": model_unresolved,
        "unknowns": unknowns,
        "resolved_uncertainties": resolved_uncertainties,

        # ---- text actually readable in the image ----
        "text_labels_if_visible": labels,

        # ARCHITECTURAL_VISION_LABEL_COMPLETENESS_V1 — the same list with
        # EVERY occurrence kept, so instance count survives.
        "text_labels_verbatim": labels_verbatim,

        # LOCAL_PLAN_READING_V1 — the provider's own label claims. Never
        # authoritative when local evidence is grounded.
        "provider_labels": provider_labels,

        # VISION_END_TO_END_RETENTION_FIX_V1 — local OCR that is NOT an exact,
        # independently verified transcription. Preserved for audit with its
        # raw OCR and provenance; it carries no semantic function and no zone,
        # so it can never name or classify a space.
        "low_trust_ocr_labels": low_trust_local,

        # VISION_RETENTION_FIX_V2 — stable-but-not-independent OCR, reportable
        # as OCR only.
        "stable_local_ocr_labels": stable_local,

        # VISION_RETENTION_FIX_V2 — the texts an INDEPENDENT source corroborated.
        # Read by the interpreter's label gate and by the conflict trust gate.
        "independently_verified_ocr_texts": sorted(independent_texts),

        # LOCAL_PLAN_READING_V1 — structured OCR and raster provenance stays
        # separate from both source text and semantic interpretation.
        "local_plan_reading": copy.deepcopy(local_plan_reading),
        "sheet_structure": copy.deepcopy((local_plan_reading or {}).get("sheet_structure")),

        # ---- observation, NOT interpretation ----
        "observation_only": True,
        "interpretation_merged": False,
        "space_classification": None,
        "possible_function": [],
        "design_reasoning": [],
        "geometry_authoritative": False,
        "design_generated": False,
        "render_requested": False,
        "comfy_invoked": False,
        "read_only": True,
    }

    return observation


def _phrase_confidence(phrase: str, observed: List[str]) -> str:

    """A phrase the provider placed in `observed` is stated as visible."""

    return "MEDIUM" if phrase in observed else "LOW"


# ----------------------------------------------------------
# pass-through for the interpreter (requirement 4)
# ----------------------------------------------------------

def visible_observations_passthrough(
    understanding: Any,
    observation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    """The visible evidence, preserved BEFORE any interpretation.

    The interpreter calls this first, so no visible observation can be lost
    by the interpretation vocabulary.
    """

    raw = understanding if isinstance(understanding, dict) else {}

    if isinstance(observation, dict) and observation.get("contract") == CONTRACT:

        return {
            "contract": CONTRACT + ".Passthrough",
            "image_type": observation.get("image_type"),
            "phrases": [
                entry.get("evidence_phrase")
                for entry in (
                    (observation.get("architectural_elements") or [])
                    + (observation.get("furniture_elements") or [])
                    + (observation.get("object_elements") or [])
                    + (observation.get("unclassified_observations") or [])
                )
                if entry.get("evidence_phrase")
            ],
            "visible_floors": observation.get("visible_floors"),
            "spatial_clues": observation.get("spatial_clues") or [],
            "material_observations": observation.get("material_observations") or [],
            "style_indicators": observation.get("style_indicators") or [],
            "texture_color_observations": observation.get("texture_color_observations") or [],
            "interpretation_applied": False,
        }

    # no observation object: fall back to the raw understanding, still lossless
    phrases: List[str] = []

    visible_phrases: List[str] = []

    for key in ("observed", "inferred", "architectural_elements", "text_labels_if_visible"):

        for phrase in _as_list(raw.get(key)):

            if phrase not in phrases:

                phrases.append(phrase)

            if key in ("observed", "architectural_elements") and phrase not in visible_phrases:

                visible_phrases.append(phrase)

    return {
        "contract": CONTRACT + ".Passthrough",
        "image_type": _refine_image_type(raw.get("image_type"), _norm(" ".join(phrases))),
        "phrases": phrases,
        "visible_floors": detect_visible_floors(visible_phrases),
        "spatial_clues": [],
        "material_observations": [],
        "style_indicators": [],
        "texture_color_observations": [],
        "interpretation_applied": False,
    }


# ==========================================================
# THE CLASS (mirrors the other vision layers)
# ==========================================================

class ArchitecturalObservationV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    INTERPRETS = False
    GENERATES_DESIGN = False
    GENERATES_GEOMETRY = False
    RENDERS = False
    DROPS_OBSERVATIONS = False
    DEMOTES_TO_UNKNOWN = False

    def build(self, raw, **kwargs):

        return build_architectural_observation(raw, **kwargs)

    def passthrough(self, understanding, observation=None):

        return visible_observations_passthrough(understanding, observation)


architectural_observation_v1 = ArchitecturalObservationV1()


# ==========================================================
# V7 — grounded facade-element evidence (additive)
# ==========================================================

ELEMENT_EVIDENCE_CONTRACT = "FacadeElementEvidenceV1"

#: A record is only ever one of these. Anything else fails SAFE to UNVERIFIED
#: rather than being promoted into an assertion.
#:
#: V7.1 adds the two classes that keep provenance honest end-to-end:
#:   MODEL_REPORTED          — the observer said it; NOT pixel-verified here.
#:   MANUALLY_PIXEL_CHECKED  — a human compared it against the pixels.
#: `OBSERVED` remains the pixel-grounded class and is the only one allowed to
#: carry a confidence number, so a model's self-reported confidence can never
#: masquerade as visual verification.
EVIDENCE_CLASSES = (
    "OBSERVED",
    "MODEL_REPORTED",
    "MANUALLY_PIXEL_CHECKED",
    "INTERPRETED",
    "UNVERIFIED",
)

#: Keys that would assert a fact the pixels cannot establish. They are dropped
#: rather than stored: a light stone appearance is not a species, and a visible
#: shaft does not establish load-bearing function.
_REFUSED_ELEMENT_KEYS = (
    "species", "stone_species", "material_species", "material_type_verified",
    "load_bearing", "is_structural", "structural_function", "bim_class",
)


def _fraction_pair(value: Any) -> Optional[Dict[str, List[float]]]:

    """Accept only a real fractional x/y extent; never invent one."""

    if not isinstance(value, dict):

        return None

    out: Dict[str, List[float]] = {}

    for axis in ("x", "y"):

        pair = value.get(axis)

        if not (isinstance(pair, (list, tuple)) and len(pair) == 2):

            return None

        try:

            low, high = float(pair[0]), float(pair[1])

        except (TypeError, ValueError):

            return None

        if low > high or not (0.0 <= low <= 1.0) or not (0.0 <= high <= 1.0):

            return None

        out[axis] = [round(low, 4), round(high, 4)]

    return out


def _clean_element_evidence(item: Any) -> Optional[Dict[str, Any]]:

    """One grounded element record, or None when it cannot be grounded."""

    if not isinstance(item, dict):

        return None

    element = _text(item.get("element"))

    if not element:

        return None

    evidence = _text(item.get("evidence"))

    klass = _text(item.get("evidence_class")).upper()

    if klass not in EVIDENCE_CLASSES:

        klass = "UNVERIFIED"

    kinds = [kind for kind in _as_list(item.get("kind")) if kind]

    # Confidence is only meaningful for a directly observed element that
    # actually carries visible evidence. An interpretation, an unresolved
    # classification, or an evidence-free claim may not carry a number that
    # would outrank its own uncertainty.
    confidence = None

    if klass == "OBSERVED" and evidence:

        raw_confidence = item.get("confidence")

        if isinstance(raw_confidence, (int, float)) and not isinstance(
                raw_confidence, bool):

            confidence = round(max(0.0, min(1.0, float(raw_confidence))), 4)

    relations: List[Dict[str, str]] = []

    source_quote = _text(item.get("source_quote"))

    for relation in item.get("relations") or []:

        if not isinstance(relation, dict):

            continue

        relation_name = _norm(relation.get("relation")).replace(" ", "_")

        target_kind = _norm(relation.get("target_kind")).replace(" ", "_")

        relation_quote = _text(relation.get("source_quote"))

        if relation_name != "mounted_on" or target_kind != "wall" \
                or not relation_quote:

            continue

        if relation_quote not in (source_quote, evidence):

            continue

        cleaned_relation = {
            "relation": relation_name,
            "target_kind": target_kind,
            "source_quote": relation_quote,
        }

        if cleaned_relation not in relations:

            relations.append(cleaned_relation)

    return {
        "element": element,
        "kind": kinds,
        "evidence": evidence,
        "evidence_class": klass,
        "position": _fraction_pair(item.get("position")),
        "uncertainty": _text(item.get("uncertainty")) or None,
        "confidence": confidence,
        # V7.1 — traceability back to the saved observation text. Absent for
        # hand-grounded records, present for source-anchored ones.
        "source_quote": source_quote or None,
        "source_quote_method": _text(item.get("source_quote_method")) or None,
        "model_reported_count": (
            int(item["model_reported_count"])
            if isinstance(item.get("model_reported_count"), int)
            and not isinstance(item.get("model_reported_count"), bool)
            else None
        ),
        "claim_category": _text(item.get("claim_category")) or None,
        # V7.2 — the label the normalizer declared, kept even when it was a
        # meta-kind and the carried kinds came from the quote instead.
        "declared_kind": _text(item.get("declared_kind")) or None,
        # V7.3 — True when the record came from a stage-C recovery (valid quote,
        # non-verbatim summary label).
        "recovered": bool(item.get("recovered")),
        # V7.4 — how the carried identity was established, and which quote-
        # supported kinds were deliberately NOT chosen as the subject.
        "kind_basis": _text(item.get("kind_basis")) or None,
        "context_kinds": [kind for kind in _as_list(item.get("context_kinds")) if kind],
        # V7.4 — a typed edge is present only when its predicate is explicit in
        # the same anchored quote. Context words alone never create a relation.
        "relations": relations,
    }


def attach_element_evidence(
    observation: Any,
    elements: Any,
    *,
    source_image: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Attach grounded facade-element evidence to an observation.

    V7 — this is the smallest additive carrier for evidence that no existing
    field could hold. `ArchitecturalObservationV1` had no position, no
    evidence class, no per-element uncertainty and no crop provenance, while
    `architectural_elements[].confidence` is lexical (`_phrase_confidence`).

    Deliberately NOT a text parser: it accepts element records that a caller
    has ALREADY grounded, validates them, and refuses to invent anything. Free
    model prose is never converted into asserted structure here.

    `architectural_elements` entry shapes are left completely untouched, so the
    many existing consumers (BIM bridge, IFC validator, chat result, render and
    edit prompt builders, resolved facade knowledge) see no change.
    """

    result = dict(observation) if isinstance(observation, dict) else {}

    cleaned: List[Dict[str, Any]] = []

    for item in elements or []:

        if isinstance(item, dict):

            item = {key: value for key, value in item.items()
                    if key not in _REFUSED_ELEMENT_KEYS}

        record = _clean_element_evidence(item)

        if record is not None:

            cleaned.append(record)

    result["element_evidence"] = {
        "contract": ELEMENT_EVIDENCE_CONTRACT,
        "source_image": copy.deepcopy(source_image)
        if isinstance(source_image, dict) else None,
        "elements": cleaned,
    }

    return result


#: The EXISTING normalizer's certainty vocabulary maps to an evidence class.
#: An observer's ASSERTED statement is MODEL_REPORTED — never OBSERVED, because
#: nothing here compares it against the pixels.
_CERTAINTY_TO_EVIDENCE_CLASS = {
    "ASSERTED": "MODEL_REPORTED",
    "AMBIGUOUS": "UNVERIFIED",
    "UNKNOWN": "UNVERIFIED",
}


#: Phrases that state ABSENCE. A claim carrying one of these is not evidence
#: that the element exists, even when the surrounding quote names its kind.
_ABSENCE_MARKERS = (
    "none visible",
    "none reported",
    "nothing visible",
    "no visible",
    "not visible",
    "cannot be seen",
    "absent",
    "not present",
    "isn't visible",
    "are not visible",
)


def _states_absence(text: str) -> bool:
    """True when the claim itself asserts that something is NOT there."""

    low = _norm(text)

    if not low:

        return False

    if low.startswith("none") or low.startswith("no "):

        return True

    if _any_word(low, ("there is no ", "there are no ", "shows no ",
                       "contains no ", "without any ")):

        return True

    return any(marker in low for marker in _ABSENCE_MARKERS)


#: V7.4 — narrowly constrained appearance-to-kind interpretation.
#:
#: This exists because a concise architectural label does not always appear in a
#: visually descriptive sentence. It is deliberately NOT a paraphrase engine: it
#: fires only on a conjunction of concrete visual predicates, and it can produce
#: only the two generic kinds below.
_RECEPTACLE_WORDS = ("bowl", "receptacle", "container", "vessel", "trough",
                     "basket", "urn", "planter box", "window box")

_PLANT_WORDS = ("flower", "bloom", "plant", "foliage", "shrub", "greenery")

_CONTAINMENT_WORDS = ("filled with", "containing", "holding", "planted with",
                      "growing in", "growing from")

_MOUNTED_WORDS = ("mounted on the wall", "mounted to the wall",
                  "wall-mounted", "wall‑mounted", "affixed to the wall",
                  "attached to the wall", "fixed to the wall",
                  "hanging on the wall")

_CARVED_WORDS = ("carv", "relief", "raised")

_HORIZONTAL_WORDS = ("horizontal", "across the top", "along the top")


def _appearance_kind(quote: Any) -> Optional[str]:
    """A generic architectural kind that the DESCRIPTION itself supports.

    Returns ``"planter"`` when the quote describes a wall-mounted receptacle
    holding plants, and ``"decorative_band"`` when it describes a horizontal
    carved band. Returns ``None`` otherwise — including for a plain bowl with no
    plants, for plants mentioned beside an unrelated object, and for a bowl that
    is not wall-mounted.

    A ``decorative_band`` is deliberately generic: the rule never asserts a
    cornice, a frieze or a floor division.
    """

    low = _norm(quote)

    if not low:

        return None

    if (_any_word(low, _RECEPTACLE_WORDS)
            and _any_word(low, _PLANT_WORDS)
            and _any_word(low, _CONTAINMENT_WORDS)
            and _any_word(low, _MOUNTED_WORDS)):

        return "planter"

    if ("band" in low
            and _any_word(low, _CARVED_WORDS)
            and _any_word(low, _HORIZONTAL_WORDS)):

        return "decorative_band"

    return None


def _any_word(low: str, words) -> bool:
    return any(word in low for word in words)


def _explicit_element_relations(
    quote: str,
    kinds: List[str],
    supported_kinds: List[str],
) -> List[Dict[str, str]]:
    """Return only relations whose predicate and target are explicit.

    V7.4 intentionally starts with one reusable relation: ``mounted_on`` a
    wall. A wall word by itself is context, not a relation. Likewise, a
    negated mounting phrase never creates a positive edge.
    """

    low = _norm(quote)

    if not low or "wall" not in supported_kinds or not kinds or "wall" in kinds:

        return []

    if _any_word(low, ("not mounted", "not affixed", "not attached",
                       "not fixed", "not hanging")):

        return []

    if not _any_word(low, _MOUNTED_WORDS):

        return []

    return [{
        "relation": "mounted_on",
        "target_kind": "wall",
        "source_quote": quote,
    }]


def element_evidence_from_claims(
    observation: Any,
    claims: Any,
    source_text: str,
    *,
    source_image: Optional[Dict[str, Any]] = None,
    raw_claim_count: Optional[int] = None,
    normalizer_accepted_count: Optional[int] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Anchor EXISTING normalizer claims to their source text as element evidence.

    V7.1 — this consumes the normalizer's own claim shape
    (`structured-visual-observation-v1.2`: text / source_quote / kind /
    certainty / count). It does NOT parse free text and it does NOT discover
    elements: the claims come from the existing normalizer. This function only
    decides whether each claim may be carried, using the existing
    `resolve_source_quote` semantics.

    Returns ``(observation, report)``. The report lists every rejected claim
    with a machine-readable reason so a caller can never mistake "rejected" for
    "not reported".

    Invariants enforced here:
      * a claim whose `source_quote` is not a verbatim substring of the saved
        text is REJECTED (no invented evidence);
      * a claim whose `text` is not inside its own quote is REJECTED;
      * a declared `kind` must be supported by the anchored quote itself,
        otherwise the claim is REJECTED (no invented classification);
      * an undeclared `kind` becomes only what the quote supports, never more;
      * a `count` survives only when the digit appears in the anchored quote;
      * `certainty` maps to an evidence class and hedges are retained verbatim;
      * no position is produced, because the normalizer schema has no position
        field — positions cannot be smuggled in through text.
    """

    from core.vision.observation_normalizer_v1 import resolve_source_quote

    source_text = source_text if isinstance(source_text, str) else ""

    if raw_claim_count is None:

        raw_claim_count = len(list(claims or []))

    if normalizer_accepted_count is None:

        normalizer_accepted_count = raw_claim_count

    accepted: List[Dict[str, Any]] = []

    rejected: List[Dict[str, Any]] = []

    for index, claim in enumerate(claims or []):

        if not isinstance(claim, dict):

            rejected.append({"index": index, "reason": "claim_is_not_an_object"})

            continue

        quote_raw = _text(claim.get("source_quote"))

        quote, quote_method = resolve_source_quote(quote_raw, source_text)

        if quote is None:

            rejected.append({
                "index": index,
                "reason": "source_quote_not_found_in_saved_text",
                "source_quote": quote_raw[:160],
            })

            continue

        text_raw = _text(claim.get("text"))

        # V7.3 — a stage-C claim carries a concise element LABEL rather than a
        # verbatim span. The quote is still required to be real (checked above);
        # only the summary-text containment check is waived, and the label is
        # kept verbatim for provenance.
        if claim.get("text_is_model_label"):

            anchored_text = text_raw

            text_method = "model_label"

        else:

            anchored_text, text_method = resolve_source_quote(text_raw, quote)

        if anchored_text is None:

            rejected.append({
                "index": index,
                "reason": "claim_text_not_inside_its_own_quote",
                "text": text_raw[:160],
            })

            continue

        supported_kinds = _labels(
            quote, ARCHITECTURAL_ELEMENT_MARKERS,
            suppress_compound_modifiers=True)

        declared_kind = _norm(claim.get("kind")).replace(" ", "_")

        vocabulary = {label for label, _ in ARCHITECTURAL_ELEMENT_MARKERS}

        appearance_kind = _appearance_kind(quote)

        # V7.2 — a NEGATED claim is not an element. A live API probe produced
        # records like element="none visible" carrying kinds ["wall","opening",
        # "stair"] purely because those words appeared in the surrounding quote.
        # Absence must never be carried as presence.
        if _states_absence(anchored_text) or _states_absence(quote):

            rejected.append({
                "index": index,
                "reason": "claim_states_absence",
                "text": anchored_text[:160],
            })

            continue

        # V7.4 — SUBJECT FIRST. The carried `kind` is the identity of the thing
        # being described, never every architectural word that happens to appear
        # in its description. A wall-mounted lantern is a light_fixture whose
        # mounting context is a wall; a pier that mentions "a capital block" is
        # still a pier.
        kind_basis = None

        if declared_kind and declared_kind in vocabulary:

            if declared_kind in supported_kinds:

                kinds = [declared_kind]

                kind_basis = "model_declared"

            elif appearance_kind == declared_kind:

                # The description itself supports the declared kind even though
                # the label word is absent from it.
                kinds = [declared_kind]

                kind_basis = "appearance_rule"

            elif appearance_kind:

                # The description supports a MORE GENERAL category than the
                # model's naming. Carry the general one and keep the model's
                # naming as `declared_kind`.
                kinds = [appearance_kind]

                kind_basis = "appearance_rule"

            else:

                rejected.append({
                    "index": index,
                    "reason": "declared_kind_not_supported_by_its_quote",
                    "kind": declared_kind,
                    "supported_by_quote": supported_kinds,
                })

                continue

        else:

            # A meta-kind ("interpretation", "unknown", "fixture") or a label
            # outside the vocabulary. The LABEL names the subject, so try it
            # before falling back to the whole quote.
            label_kinds = _labels(
                anchored_text, ARCHITECTURAL_ELEMENT_MARKERS,
                suppress_compound_modifiers=True)

            if label_kinds:

                kinds = label_kinds

                kind_basis = "label"

            elif appearance_kind:

                kinds = [appearance_kind]

                kind_basis = "appearance_rule"

            else:

                # Nothing architectural in the label OR the quote. Fallback must
                # never become invention.
                rejected.append({
                    "index": index,
                    "reason": "no_architectural_kind_supported_by_quote",
                    "kind": declared_kind or None,
                    "source_quote": quote[:160],
                })

                continue

        # Everything the quote supports that is NOT the subject is preserved as
        # context rather than promoted to identity.
        context_kinds = [kind for kind in supported_kinds if kind not in kinds]

        relations = _explicit_element_relations(quote, kinds, supported_kinds)

        certainty = _text(claim.get("certainty")).upper()

        evidence_class = _CERTAINTY_TO_EVIDENCE_CLASS.get(certainty, "UNVERIFIED")

        uncertainty = None

        if certainty == "AMBIGUOUS":

            uncertainty = "observer hedged: " + anchored_text

        elif certainty == "UNKNOWN":

            uncertainty = "observer could not determine: " + anchored_text

        # V7.4 — a generic appearance category is NOT a classical type. The
        # physical observation stands; the naming stays explicitly open.
        if kind_basis == "appearance_rule" and "decorative_band" in kinds \
                and not uncertainty:

            uncertainty = (
                "the description supports a generic decorative band only; "
                "the precise classical type (cornice, frieze, entablature) and "
                "any floor-division role are not established"
            )

        raw_count = claim.get("count")

        model_reported_count = None

        if isinstance(raw_count, int) and not isinstance(raw_count, bool):

            # A count is only carried when the digit is actually in the quote.
            if str(raw_count) in quote:

                model_reported_count = raw_count

        accepted.append({
            "element": anchored_text,
            "kind": kinds,
            "evidence": quote,
            "evidence_class": evidence_class,
            "position": None,
            "uncertainty": uncertainty,
            "confidence": None,
            "source_quote": quote,
            "source_quote_method": quote_method if quote_method == text_method
            else quote_method + "+" + text_method,
            "model_reported_count": model_reported_count,
            "claim_category": _text(claim.get("claim_category")) or None,
            "declared_kind": declared_kind or None,
            "recovered": bool(claim.get("text_is_model_label")),
            # V7.4 — identity provenance and context.
            "kind_basis": kind_basis,
            "context_kinds": context_kinds,
            "relations": relations,
        })

    # V7.3 — recovered stage-C claims must never inflate the carried set. A
    # record identical to one already carried (same quote, kinds and label) is
    # dropped. Non-recovered records are untouched, so V7.2 behaviour is
    # preserved exactly.
    _seen = set()

    _deduped: List[Dict[str, Any]] = []

    for record in accepted:

        _key = (record["source_quote"], tuple(sorted(record["kind"])),
                record["element"])

        if record.get("recovered") and _key in _seen:

            continue

        _deduped.append(record)

        _seen.add(_key)

    accepted = _deduped

    anchored = attach_element_evidence(
        observation, accepted, source_image=source_image)

    report = {
        "contract": "SourceAnchoredElementEvidenceV1",
        "source_text_sha256": hashlib.sha256(
            source_text.encode("utf-8")).hexdigest(),
        "source_text_length": len(source_text),
        "claim_count": len(list(claims or [])),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "rejected": rejected,
        # V7.4 — claim bookkeeping is NOT object bookkeeping. Carried records
        # come from far fewer distinct source quotations, and no record is a
        # verified physical object.
        "raw_claim_count": raw_claim_count,
        "accepted_claim_count": normalizer_accepted_count,
        "carried_evidence_record_count": len(accepted),
        "unique_evidence_claim_count": len({
            (record["source_quote"], tuple(sorted(record["kind"])),
             record["element"]) for record in accepted
        }),
        "unique_source_quote_count": len({
            record["source_quote"] for record in accepted
        }),
        "supported_count_claim_count": sum(
            1 for record in accepted
            if isinstance(record.get("model_reported_count"), int)),
        # Evidence records and supported count claims cannot establish how many
        # physical objects exist. Keep both model-reported and verified object
        # totals explicitly unknown rather than deriving them from list length.
        "model_reported_object_count": None,
        "physical_object_count": None,
        "verified_object_count": None,
        "object_count_note": (
            "carried records are evidence claims, not counted physical objects; "
            "no automatic pixel verification exists"
        ),
        "position_available": False,
        "position_note": (
            "the normalizer claim schema (structured-visual-observation-v1.2) "
            "has no position field and forbids additional properties, so no "
            "position can be derived from normalization"
        ),
    }

    return anchored, report


#: Vocabulary labels, used by the V7.3 stage-C recovery gate.
_ELEMENT_VOCABULARY = frozenset(
    label for label, _ in ARCHITECTURAL_ELEMENT_MARKERS)


def recovered_claims_from_failures(
    failures: Any,
    source_text: str,
) -> List[Dict[str, Any]]:
    """Recover stage-C claims: valid quote, non-verbatim summary text.

    V7.3 — `parse_normalization` rejects a claim when its concise `text` is not
    a verbatim substring of its own `source_quote` (``field="text"``,
    ``reason="no_match"``). For a visually descriptive sentence that is expected:
    the model writes "A shallow, ribbed/scalloped stone bowl ..." and labels it
    "planter". The label is a REPRESENTATION, not a fabricated claim.

    This returns claim dicts that the normalizer dropped for that reason ONLY,
    and only when every remaining invariant still holds:

      * the rejection was for ``text``/``no_match`` — never for the quote;
      * the ``source_quote`` still resolves verbatim against the saved text;
      * the quote does not assert absence;
      * the declared kind is supported by that quote, or — when the declared
        kind is not a vocabulary label at all — the quote supports some
        architectural kind, which is then used instead.

    V7.4 additionally permits one of the bounded appearance categories returned
    by :func:`_appearance_kind`. The original model label is preserved verbatim
    and the record is marked ``text_is_model_label`` so the adapter keeps it as
    MODEL_REPORTED.
    """

    from core.vision.observation_normalizer_v1 import resolve_source_quote

    source_text = source_text if isinstance(source_text, str) else ""

    recovered: List[Dict[str, Any]] = []

    for failure in failures or []:

        if not isinstance(failure, dict):

            continue

        if failure.get("field") != "text" or failure.get("reason") != "no_match":

            continue

        claim = failure.get("claim")

        if not isinstance(claim, dict):

            continue

        quote, _method = resolve_source_quote(
            _text(claim.get("source_quote")), source_text)

        if quote is None:

            continue

        label = _text(claim.get("text"))

        if not label or _states_absence(label) or _states_absence(quote):

            continue

        supported = _labels(
            quote, ARCHITECTURAL_ELEMENT_MARKERS,
            suppress_compound_modifiers=True)

        appearance = _appearance_kind(quote)

        declared = _norm(claim.get("kind")).replace(" ", "_")

        if declared in _ELEMENT_VOCABULARY:

            # The declared label must be supported by the quote, OR the
            # description must support some narrow appearance category.
            if not (declared in supported or appearance):

                continue

        else:

            # Meta-kind or uncovered label: the label itself, or the
            # description, must name a subject.
            if not (_labels(label, ARCHITECTURAL_ELEMENT_MARKERS,
                            suppress_compound_modifiers=True) or appearance):

                continue

        recovered.append({
            "text": label,
            "source_quote": quote,
            "kind": claim.get("kind"),
            "certainty": claim.get("certainty"),
            "count": claim.get("count"),
            "claim_category": failure.get("category"),
            "text_is_model_label": True,
        })

    return recovered
