# -*- coding: utf-8 -*-
"""ARCHITECTURAL_RENDER_INSTRUCTION_V1 — Persian request -> English render instruction.

WHY THIS EXISTS
---------------
The canonical Persian -> English path already exists and is reused here:

    core/prompt_intelligence/persian_architectural_understanding.understand()
    core/prompt_intelligence/architectural_prompt_compiler_v1.compile_prompt()
    core/cognition/architectural_terminology_v1.normalize_architectural_terms()
    core/cognition/architectural_terminology_v1.augment_compiled_prompt()

But the compiled English prompt does NOT carry every element the brief requires.
Measured on the real modules (no mocks):

* "یک ویلای دو طبقه با نمای سنتی بساز"  -> the floor COUNT (two) is lost; only
  "Refine the architectural design" is emitted.
* "اتاق ۱۲ متره، نه ۱۰ متر"             -> the understanding is empty and the
  compiled prompt is EMPTY, so the dimension never reaches English.
* "نمای جنوبی ... سه طبقه ..."           -> "three floors" is lost (only
  "Preserve the existing floor count" is emitted).

So this module is the SMALLEST ADDITIVE CONTRACT that closes exactly those
gaps. It re-derives nothing: understanding, compilation and terminology stay
owned by their existing modules. It only

  1. extracts the STRUCTURED constraints the compiler drops
     (floor count, dimensions, geometry, openings, camera, negations), and
  2. assembles ONE English render instruction that carries them explicitly,
     together with the Image A / Image B roles.

It is a CONTRACT. It calls no renderer, no ComfyUI and no model.
`core/cognition/render_semantic_fidelity_v1.py` validates its output.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.chat.negation_scope_v1 import (
    _IMPERATIVE_PROHIBITION_MARKERS,
    has_contrastive_negation,
    is_affirmed,
    is_prohibited,
    prohibition_spans,
    rejected_span,
    trim_replacement_span,
)
from core.cognition.architectural_terminology_v1 import (
    augment_compiled_prompt,
    normalize_architectural_terms,
)
# T2I_ARCHITECTURAL_FEATURE_HANDOFF_V1 — the clause splitter and the
# opening-vs-protection element split are OWNED by the geometry-authority
# contract, which already draws exactly that distinction. They are reused
# here rather than re-implemented, so one layer owns the semantics.
from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    split_clauses,
)
from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
    compile_prompt,
)
from core.prompt_intelligence.persian_architectural_understanding import (
    PersianArchitecturalUnderstandingEngine,
    understand,
)


CONTRACT = "ArchitecturalRenderInstructionV1"
VERSION = "1.0"


# ==========================================================
# IMAGE ROLES
#
# Image A is the FACADE REFERENCE (appearance source only).
# Image B is the TARGET BUILDING (geometry authority).
#
# This is a role ASSIGNMENT, not a geometry copy: the reference may
# inform appearance, never the target's massing or openings.
# ==========================================================

ROLE_FACADE_REFERENCE = "facade_reference"
ROLE_TARGET_BUILDING = "target_building"

IMAGE_A = "A"
IMAGE_B = "B"


# ==========================================================
# NUMBER / UNIT LEXICON  (grammar, not test data)
# ==========================================================

_NUMBER_WORDS = {
    "صفر": 0, "یک": 1, "یه": 1, "دو": 2, "سه": 3, "چهار": 4, "چهارتا": 4,
    "پنج": 5, "شش": 6, "شیش": 6, "هفت": 7, "هشت": 8, "نه": 9, "ده": 10,
    "یازده": 11, "دوازده": 12, "سیزده": 13, "چهارده": 14, "پانزده": 15,
    "شانزده": 16, "هفده": 17, "هجده": 18, "نوزده": 19, "بیست": 20,
    "thirty": 30, "twenty": 20, "ten": 10, "nine": 9, "eight": 8,
    "seven": 7, "six": 6, "five": 5, "four": 4, "three": 3, "two": 2,
    "one": 1,
}

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"

# "طبقه" = floor/storey.  Matched immediately after a number, never anywhere.
_FLOOR_NOUNS = ("طبقه‌ای", "طبقات", "طبقه", "floors", "floor", "storeys",
                "storey", "stories", "story")

# A quantity scoped to the portion ABOVE an already named ground floor is a
# component of the level breakdown, not a second statement of the building's
# total. Excluding it prevents an explicit total such as "three floors in
# total: ground plus two floors above it" from becoming a false conflict.
_FLOOR_COMPONENT_SUFFIXES = (
    "بالای آن", "بالای همکف", "روی همکف",
    "above it", "above the ground floor", "above ground floor",
)

# A bound is not an exact building total. These markers are deliberately
# limited to the phrase immediately before the number; their presence
# elsewhere in an architectural description must not suppress a valid count.
_FLOOR_LIMIT_PREFIXES = (
    "at least", "at most", "up to", "maximum", "minimum",
    "no more than", "no less than", "not more than", "not less than",
    "حداکثر", "حداقل",
)

# ==========================================================
# R1_B_FLOOR_COUNT_DESCRIPTION_REQUEST_V1 — DESCRIPTION vs REQUEST
#
# A floor count attached to a copula or possession predicate states what the
# building ALREADY IS:
#
#     "این ساختمان سه طبقه است."        -> the building is three storeys
#     "The building has three storeys."  -> the building is three storeys
#
# That is a description of the existing building, not a request to make it
# so. Treating it as a requested target is how a pure observation became a
# hard floor-count constraint. A count is therefore only a REQUEST when it
# is NOT description-attached, or when the sentence makes the stated value
# operative (an explicit preserve request, or a contrastive correction of a
# rejected value).
#
# These are grammatical predicates only — no domain vocabulary.
# ==========================================================

# Predicates that FOLLOW the floor phrase (Persian is post-verbal here).
_FLOOR_DESCRIPTION_AFTER = (
    "می‌باشد", "میباشد", "می‌باشند", "میباشند",
    "هستند", "هستن", "هست",
    "است", "بوده", "بودند", "بود",
    "دارد", "دارند", "داره", "دارن",
)

# Predicates that PRECEDE the floor phrase (English is pre-verbal here).
_FLOOR_DESCRIPTION_BEFORE = (
    "has", "have", "had",
    "is", "are", "was", "were",
    "contains", "comprises", "includes",
)

# A preserve request makes the user's OWN stated count operative — it is
# quoted, not invented. Deliberately narrow: "تغییر نده" preserves, while
# "تغییر بده" does not.
_FLOOR_PRESERVE_MARKERS = (
    "تغییر نده", "تغییر ندهید", "تغییر نکن",
    "بدون تغییر", "ثابت بماند", "ثابت بمانند",
    "حفظ شود", "حفظ کن", "حفظ کنید",
    "preserve", "unchanged", "keep the same",
    "do not change", "don't change", "same number of floors",
)

# "متر" = metre.  Longest first so مترمربع wins over متر.
_AREA_UNITS = ("مترمربع", "متر مربع", "square meter", "square meters")
_LENGTH_UNITS = ("متر", "سانتی‌متر", "سانتیمتر", "centimeter", "centimetre",
                 "meter", "meters", "metre", "metres")

# English units for the render instruction. A Persian request must produce an
# ENGLISH instruction, so the unit is translated while the value is kept.
_UNIT_EN = {
    "مترمربع": "m2", "متر مربع": "m2", "square meter": "m2",
    "square meters": "m2",
    "متر": "m", "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "سانتی‌متر": "cm", "سانتیمتر": "cm",
    "centimeter": "cm", "centimetre": "cm",
}

_GEOMETRY_MARKERS = (
    "ابعاد", "زیربنا", "فرم", "حجم", "هندسه", "مستطیل", "مربع", "کشیدگی",
    "تناسبات", "dimensions", "footprint", "massing", "geometry", "form",
)

_OPENING_NOUNS = ("پنجره", "پنجره ها", "پنجره‌ها", "در", "درها", "بازشو",
                  "بازشوها", "نورگیر", "window", "windows", "door", "doors",
                  "opening", "openings")

_OPENING_CHANGE_VERBS = ("جابه", "جابجا", "جابه‌جا", "تغییر", "عوض", "حذف",
                         "اضافه", "بردار", "بزرگ", "کوچک", "move", "relocate",
                         "replace", "remove", "add", "resize", "shift", "change")

# ==========================================================
# T2I_ARCHITECTURAL_FEATURE_HANDOFF_V1 — REQUESTED FEATURE PRESENCE
#
# MEASURED DEFECT: `_openings` extracted `nouns`/`verbs` and NOTHING read them,
# so an explicit "add a wooden entrance door" produced no instruction sentence
# at all and the sampler never learned the door was wanted.
#
# The tables below are the SMALLEST thing that closes that gap. They add no
# ontology and no new engine:
#
#   * the opening nouns and the material vocabulary already exist in this
#     module (`_OPENING_NOUNS`) and in the canonical terminology layer
#     (`architectural_terminology_v1`), which is reused for materials;
#   * the element/domain split (window+door = OPENING; railing/balustrade/
#     parapet = CIRCULATION/protection) already exists in
#     `geometry_authority_handoff_v1`, which is likewise reused.
# ==========================================================

#: Railings, balustrades and parapets are PROTECTION / ENCLOSURE elements, not
#: openings: they guard a balcony, terrace, staircase or roof edge. They are
#: kept in their own table so an opening whitelist can never consume them.
_FEATURE_GUARD_NOUNS = (
    "نرده", "نرده‌ها", "نرده ها", "جان‌پناه", "جانپناه", "بالوستراد",
    "بالسترد", "پاراپت", "حصار", "حفاظ",
    "railing", "railings", "handrail", "handrails", "guardrail",
    "guardrails", "balustrade", "balustrades", "parapet", "parapets",
    "banister", "banisters", "rail",
)

#: ADD/REQUEST verbs. These ask for the feature to EXIST. An authorisation
#: also comes from a describing request with no verb at all ("ساختمانی با
#: پنجره‌های قوسی"), which is handled by `_FEATURE_DESIGN_MARKERS` below.
_FEATURE_ADD_VERBS = (
    "اضافه کن", "اضافه‌اش کن", "اضافه کنید", "اضافه کنم", "اضافه شود",
    "اضافه بشه", "اضافه", "بگذار", "بذار", "نصب کن", "بساز", "درست کن",
    "بزن", "بده", "اجرا کن", "طراحی کن", "طراحی کنید", "با", "دارای",
    "مجهر", "مجهز", "شامل",
    "add", "adds", "added", "include", "includes", "including",
    "incorporate", "incorporates", "install", "installs", "place",
    "places", "introduce", "introduces", "with", "featuring", "fitted",
    "designed with", "equipped",
)

#: A describing design request ("design a building WITH arched windows and
#: stone railings") carries no ADD verb but still asks for the feature.
_FEATURE_DESIGN_MARKERS = (
    "طراحی کن", "طراحی کنید", "بساز", "بسازید", "درست کن", "ایجاد کن",
    "design", "designs", "design a", "design an", "create", "creates",
    "build", "builds", "generate", "generates", "draw", "draws",
)

#: INTRODUCTION markers. A clause that introduces an element with one of these
#: asks for that element to exist ("ساختمانی با پنجره‌های قوسی", "a building
#: with stone railings"). It is only treated as an authorisation when the
#: clause carries no appearance object and no change verb — see
#: `_clause_authorises_feature`, because "با" also appears in appearance edits
#: ("پنجره را با رنگ عوض کن" = repaint the window).
_FEATURE_INTRODUCING_MARKERS = (
    "با ", " با", "به همراه", "همراه با", "دارای", "مجهز", "مجهر",
    "with ", " with", "featuring", "equipped with", "complete with",
)

#: APPEARANCE objects and CHANGE verbs. Their presence in a clause means the
#: clause is editing an EXISTING element's look, not asking for a new one.
_FEATURE_APPEARANCE_OBJECTS = (
    "رنگ", "مصالح", "بافت", "پوشش", "سطح", "متریال", "جنس", "رنگ‌آمیزی",
    "colour", "color", "paint", "material", "finish", "texture", "cladding",
    "surface", "tone", "palette", "veneer",
)

_FEATURE_CHANGE_VERBS = (
    "عوض کن", "تغییر بده", "تغییر", "جابه‌جا کن", "جابجا کن", "بزرگ کن",
    "کوچک کن", "بلندتر کن", "کوتاه‌تر کن", "بازتر کن", "تنگ‌تر کن",
    "change the", "replace the", "move the", "resize the", "enlarge",
    "shrink", "widen the", "narrow the", "repaint", "restyle the",
)

#: TARGET LOCATION vocabulary. Reused to report WHERE the user asked for the
#: feature; a location is NEVER invented when the request does not state one.
_FEATURE_LOCATIONS = (
    ("entrance", ("ورودی", "ورودی ساختمان", "در ورودی", "main entrance",
                  "entrance", "entry", "front door", "main door")),
    ("facade", ("نما", "نمای", "نماي", "جلو", "facade", "front", "frontage",
                "elevation")),
    ("balcony", ("بالکن", "بالکن‌ها", "balcony", "balconies")),
    ("terrace", ("تراس", "ایوان", "تراس‌ها", "terrace", "terraces")),
    ("staircase", ("راه‌پله", "راه پله", "پله", "پله‌ها", "staircase",
                   "stairway", "stair", "stairs")),
    ("rooftop", ("پشت‌بام", "پشت بام", "بام", "روف", "لبه بام", "rooftop",
                 "roof", "roof edge", "roofline")),
    # SPATIAL_FRAMING_RETENTION_V1 — the FLOOR an element stands on. The
    # closed vocabulary used to stop at the building's parts, so an element
    # the user placed "در طبقات بالایی" (on the upper floors) lost its floor
    # while keeping its part-location. Only these two general levels are
    # named; a specific storey ("طبقه دوم") is deliberately absent, so a floor
    # the user never stated can never be invented.
    ("ground floor", ("همکف", "طبقه همکف", "طبقهٔ همکف", "ground floor",
                      "ground-floor", "ground level")),
    ("upper floor", ("طبقات بالایی", "طبقه بالا", "طبقات بالا", "طبقهٔ بالا",
                     "طبقات فوقانی", "upper floor", "upper floors",
                     "upper-floor", "upper level")),
)

#: The FLOOR entries of `_FEATURE_LOCATIONS`. They are carried in a SEPARATE
#: attribute (`floors`) because a floor is not a kind of location the other
#: rows describe: the existing `locations` field is the element's PART
#: ("balcony", "rooftop"), and mixing the two would re-label every caller's
#: expectations about what `locations` means.
_FLOOR_LOCATION_NAMES = ("ground floor", "upper floor")

#: WHOLE-BUILDING FRAMING vocabulary. Reported ONLY when the request states
#: both a whole-building noun AND a view/framing word in the SAME clause: a
#: whole-building noun on its own is the scope of the WORK ("کل ساختمان را
#: بازسازی کن" = renovate the whole building), never a camera requirement.
_WHOLE_BUILDING_MARKERS = (
    "کل ساختمان", "تمام ساختمان", "همه ساختمان", "ساختمان کامل",
    "کل بنا", "تمام بنا", "کل پروژه",
    "whole building", "entire building", "full building", "complete building",
    "whole house", "entire house",
)

_VIEW_CONTEXT_MARKERS = (
    "نما", "پرسپکتیو", "دوربین", "دید", "دیده", "قاب", "ویو",
    "view", "perspective", "camera", "shot", "framing", "visible", "frame",
)

#: Words that mark a request as NOT asking for a new feature. A negated,
#: optional, observational or preservation statement must never authorise
#: an addition — "نرده می‌خوام نه پنجره", "فقط عناصر قابل مشاهده", "پنجره‌ها
#: را دست نزن" all describe or exclude, they do not add.
_FEATURE_NEGATION_MARKERS = (
    "نکن", "نکنید", "نمی‌خوام", "نمیخوام", "نمی‌خواهم", "نمیخواهم",
    "نخواستم", "نباشه", "نباشد", "بدون", "بدون هیچ", "حذف کن", "حذف کنید",
    "بردار", "پاک کن", "دست نزن", "دست نزنید", "تغییر نده",
    "حفظ کن", "حفظ کنید", "حفظ شود", "حفظ بشه", "نگه دار", "نگه دارید",
    "do not add", "don't add", "dont add", "no new", "without adding",
    "without any", "remove the", "delete the", "never add",
    "keep the existing", "do not change", "don't change", "leave the",
    "unchanged", "as is", "only observe", "just observe",
)

#: A META-STATEMENT about missing information. It names an element only to say
#: its quantity is unknown ("تعداد درها مشخص نشده است"), so it authorises
#: nothing and prohibits nothing. VISUAL_ACCEPTANCE_BLOCKER_REPAIR_V1.
_FEATURE_META_INFORMATION_MARKERS = (
    "مشخص نشده", "مشخص نیست", "نامشخص", "معلوم نیست", "تعیین نشده",
    "مشخص نکرده", "نسبت نده", "نسبت ندهید", "نسبت داده نشود",
    "not specified", "unspecified", "not stated", "unknown",
)

#: An OBSERVATION-ONLY request describes what is visible; it never authorises
#: construction. Reuses the same visible-evidence vocabulary the vision
#: observation layer already defines.
_FEATURE_OBSERVATION_MARKERS = (
    "قابل مشاهده", "دیده می‌شود", "دیده میشه", "دیده شده", "مشهود",
    "فقط لیست", "لیست کن", "بشمار", "فهرست کن", "بررسی کن", "بررسی کنید",
    "observe", "observed", "observation", "list the", "enumerate",
    "check the", "check how many", "count the",
    "visibly", "visible in the image",
)

#: Optional / hypothetical framing — a feature the user is TALKING about is
#: not a feature the user WANTS BUILT.
_FEATURE_OPTIONAL_MARKERS = (
    "اختیاری", "اختیاراً", "شاید", "ممکن است", "اگر", "در صورت",
    "optional", "optionally", "maybe", "perhaps", "might", "could",
    "if needed", "possibly",
)

#: MATERIAL vocabulary. The canonical Persian -> English material lexicon is
#: OWNED by `architectural_terminology_v1.TERMINOLOGY` and is read from there
#: at import time, so no material vocabulary is duplicated here. This tuple is
#: only the fallback pronoun needed when a request states a material the
#: terminology layer does not carry.
_FEATURE_MATERIAL_TERMS = (
    ("stone", ("سنگ", "stone", "stonemasonry")),
    ("wood", ("چوب", "ترمووود", "wood", "timber", "wooden")),
    ("metal", ("فلز", "metal", "steel", "iron", "aluminium", "aluminum")),
    ("glass", ("شیشه", "glass", "glazed")),
    ("brick", ("آجر", "brick")),
    ("concrete", ("بتن", "concrete")),
)

#: SHAPE vocabulary. A shape the user stated about the element is part of the
#: requirement: "tall windows" and "windows" are not the same render ask, and
#: dropping the adjective silently lowers the requirement.
#:
#: The terminology layer does not carry a shape family, so this table is the
#: single owner of shape vocabulary for feature requirements. Order matters:
#: a more specific shape must precede a generic one it contains
#: ("semi-circular" before "circular").
_FEATURE_SHAPES = (
    ("semi-circular", ("نیم‌دایره", "نیم دایره", "semi-circular",
                       "semicircular", "half-round", "half round")),
    ("arched", ("قوسی", "قوس دار", "قوس‌دار", "طاقی", "arched", "arch-shaped",
                "arch shaped", "curved-top", "curved top")),
    ("rectangular", ("مستطیل", "rectangular", "rectangular-shaped")),
    ("circular", ("دایره", "گرد", "circular", "round")),
    ("oval", ("بیضی", "oval", "elliptical")),
    ("triangular", ("مثلثی", "مثلث", "triangular", "triangle")),
    # "taller"/"shorter" are COMPARATIVES: they name a change against an
    # existing element, never a shape. They are matched FIRST and yield no
    # shape, so they can never be swallowed by the absolute "tall"/"narrow"
    # patterns below.
    ("__comparative__", ("بلندتر", "بلند‌تر", "کوتاه‌تر", "کوتاه تر", "taller",
                         "higher", "shorter")),
    ("tall", ("بلند", "قدبلند", "tall", "full-height", "full height",
              "floor-to-ceiling", "floor to ceiling")),
    ("wide", ("پهن", "عریض", "wide", "broad")),
    ("narrow", ("باریک", "narrow", "slim")),
    ("slender", ("کشیده", "لاغر", "slender")),
)

#: EXPLICIT COUNT vocabulary. Only a count the user actually STATED is kept:
#: "a single wooden door" asks for ONE door, which is a different requirement
#: from "wooden doors".
#:
#: Persian "یک"/"یه" is deliberately ABSENT from the numeral-1 entry: it is the
#: indefinite article ("یک در" = "a door"), so reading it as an explicit count
#: would invent exactly the precision this module must never invent. It counts
#: only when reinforced ("فقط یک", "تنها یک"). "دو/سه/چهار" carry no such
#: ambiguity. "double"/"دو لنگه" is a LEAF configuration, not a count, so it is
#: absent as well.
_FEATURE_COUNT_WORDS = (
    # "دقیقاً یک" / "صرفاً یک" REINFORCE the numeral, exactly as "فقط یک" does:
    # the user has said the count is not incidental, so it IS an explicit
    # count. A bare "یک" stays absent — that is the indefinite article.
    ("one", ("فقط یک", "تنها یک", "دقیقاً یک", "دقیقا یک", "صرفاً یک",
             "یک عدد", "only one", "exactly one", "just one", "single",
             "one")),
    ("two", ("دو", "دوتا", "دو عدد", "two", "pair of")),
    ("three", ("سه", "سه‌تا", "سه عدد", "three")),
    ("four", ("چهار", "چهار عدد", "four")),
)

#: A door's LEAF configuration, never a count of doors: "دو لنگه" / "double
#: leaf" is one doorway with two leaves. Its numeral must not be read as a
#: count, or the requirement silently becomes "exactly 2 doors".
_FEATURE_LEAF_MARKERS = (
    "لنگه", "دو لنگه", "یک لنگه", "double leaf", "double-leaf", "single leaf",
    "single-leaf", "two-leaf", "two leaf",
)

#: Numerals the user may have written in either Persian or Arabic-Indic form.
_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"

_DIGIT_FOLD = str.maketrans(
    _PERSIAN_DIGITS + _ARABIC_DIGITS, "01234567890123456789"
)

#: The single, unique prefix every emitted feature sentence begins with. It is
#: the ONLY handle `build_constraint_block` uses to admit a feature sentence,
#: which keeps the admission narrow: no descriptive narrative can start with
#: it by accident.
FEATURE_SENTENCE_PREFIX = "REQUIRED ARCHITECTURAL FEATURE —"

#: The one sentence stating an explicit WHOLE-BUILDING framing requirement.
#: SPATIAL_FRAMING_RETENTION_V1 — fixed wording, and it is admitted into the
#: bounded constraint block by its own prefix so it can never be truncated
#: into a fragment.
WHOLE_BUILDING_FRAMING_SENTENCE = (
    "Frame the complete building: show the whole exterior elevation with all "
    "its floors, the entrance, the balcony and the roof visible in one view."
)

WHOLE_BUILDING_FRAMING_PREFIX = "Frame the complete building"

#: WHOLE_BUILDING_VISUAL_VERIFIABILITY_V1 — the framing a user-stated EXACT
#: floor count requires. A count that cannot be counted is not a satisfied
#: constraint: the first real render published "The building has exactly 3
#: floors." and produced a tight oblique crop in which neither the ground
#: storey nor the roofline was fully in frame.
#:
#: Deliberately does NOT reuse WHOLE_BUILDING_FRAMING_SENTENCE: that sentence
#: asserts "the entrance, the balcony", which would invent elements the user
#: never asked for. This one names only what the floor count itself implies —
#: the ground level, the roofline, and enough distance to count the storeys.
#: It shares the same prefix, so the EXISTING block admission and truncation
#: protection apply unchanged.
#:
#: Wording constraint: it must contain NO negation marker ("do not", "never",
#: "without"). `RenderSemanticFidelityV1` treats any such marker in the
#: instruction as evidence that a prohibition was preserved, so a negation here
#: would mask a genuinely lost prohibition and silently weaken the gate.
WHOLE_BUILDING_COUNT_FRAMING_SENTENCE = (
    "Frame the complete building in one view: show the ground level and the "
    "full roofline, keep enough camera distance for all %d storeys to be "
    "counted, and keep the entire building inside the frame."
)

#: T2I_FULL_TOWER_CAMERA_FRAMING_V1 — the framing a TALL tower needs, and the
#: reason the sentence above was not enough for one.
#:
#: MEASURED: two consecutive portrait runs stated "keep enough camera distance
#: for all 25 storeys to be counted" and both cropped the roof; top-row
#: building occupancy went 29.9 % → 62.5 %. Source inspection shows the framing
#: vocabulary contains no notion of IMAGE MARGIN at all — "sky" and "margin"
#: appear nowhere in this module — so the model was told the building must fit
#: but never where the frame edges should sit relative to the roof and the
#: entrance.
#:
#: This variant names the two margins that make "inside the frame" checkable,
#: and nothing else. It is selected ONLY for a grounded tower request, so every
#: other exact-count request (notably a three-storey building) keeps the
#: sentence above byte for byte.
#:
#: Wording constraint inherited from the sentence above: NO negation marker
#: ("do not", "never", "without"), because `RenderSemanticFidelityV1` reads any
#: such marker as evidence that a prohibition was preserved.
WHOLE_BUILDING_TOWER_FRAMING_SENTENCE = (
    "Frame the complete building in one distant long shot with enough camera "
    "distance for all %d storeys to be counted: the full roofline sits below "
    "the top of the image with clear open sky above it, the main entrance and "
    "ground plane stay above the bottom edge, and the whole building sits well "
    "inside the frame."
)

#: An explicit close-up / detail framing. A user who chose a detail view chose
#: a camera that CANNOT show every storey, so the floor-count framing
#: requirement must never override that choice.
_CLOSEUP_MARKERS = (
    "کلوزآپ", "کلوزاپ", "نزدیک", "جزئیات", "بزرگ‌نمایی", "بزرگنمایی",
    "close-up", "closeup", "close up", "detail shot", "detail view", "macro",
)

#: Human-readable element names for the emitted sentence. Doors and windows
#: are openings; railings, balustrades and parapets are protection elements.
_FEATURE_ELEMENT_LABELS = (
    ("door", ("در", "درب", "درها", "door", "doors")),
    ("window", ("پنجره", "پنجره‌ها", "پنجره ها", "نورگیر", "window",
                "windows")),
    ("opening", ("بازشو", "بازشوها", "opening", "openings")),
    ("railing", ("نرده", "نرده‌ها", "نرده ها", "handrail", "railing",
                 "railings", "guardrail", "guardrails", "banister")),
    ("balustrade", ("بالوستراد", "بالسترد", "balustrade", "balustrades")),
    # ROOT_HANDOFF_V1 — a word may have ONE owner. "پشت‌بام" (rooftop) is a
    # LOCATION, owned by `_FEATURE_LOCATIONS` at line ~222; it used to be a
    # parapet label as well, so merely NAMING the rooftop ("برای پشت‌بام کاشی
    # بگذار") fabricated a parapet request. The parapet element is now recognised
    # by its own nouns only, and the rooftop is still reported as the parapet's
    # LOCATION when the request states it ("جانپناه سنگی پشت‌بام").
    ("parapet", ("جان‌پناه", "جانپناه", "پاراپت", "حصار",
                 "حفاظ", "parapet", "parapets")),
)

#: The ORDER elements are reported in, so one request always yields one
#: deterministic sentence per element. Openings precede protection elements.
_FEATURE_ELEMENT_ORDER = (
    "door", "window", "opening", "railing", "balustrade", "parapet",
)

#: Which semantic group each element belongs to, so the emitted sentence can
#: state it: an opening is an opening; a railing/balustrade/parapet is a
#: protection/enclosure element and must never be phrased as an opening.
_FEATURE_ELEMENT_GROUP = {
    "door": "opening",
    "window": "opening",
    "opening": "opening",
    "railing": "protection",
    "balustrade": "protection",
    "parapet": "protection",
}


def _feature_material(clause: str) -> Optional[str]:
    """The material the user stated IN THIS CLAUSE, or None.

    Reuses the canonical terminology layer when it already matched a material,
    so the Persian -> English material lexicon keeps a single owner. Returns
    None when the clause states no material, which is what stops a material
    from being invented — and what stops one element's material being copied
    onto another element that never had it.
    """

    terminology = normalize_architectural_terms(clause)

    for item in terminology.get("matched") or []:

        if item.get("family") == "material":

            canonical = str(item.get("canonical") or "").strip()

            if canonical and canonical != "material":

                return canonical

    lowered = clause.lower()

    for canonical, patterns in _FEATURE_MATERIAL_TERMS:

        if any(pattern in lowered for pattern in patterns):

            return canonical

    return None


def _feature_locations(clause: str) -> List[str]:
    """The target PART-locations stated IN THIS CLAUSE, in a fixed order.

    SPATIAL_FRAMING_RETENTION_V1 — a FLOOR is deliberately NOT returned here.
    `locations` has always meant "which part of the building", and the callers
    and tests that read it are frozen on that meaning. Floors travel in their
    own `floors` attribute; see `_feature_floors`.
    """

    lowered = clause.lower()

    found = []

    for canonical, patterns in _FEATURE_LOCATIONS:

        if canonical in _FLOOR_LOCATION_NAMES:

            continue

        if any(pattern in lowered for pattern in patterns):

            found.append(canonical)

    return found


def _feature_floors(clause: str) -> List[str]:
    """The FLOOR(s) stated IN THIS CLAUSE, in the table's fixed order.

    Kept separate from `_feature_locations` so the two claims stay distinct:
    "بالکن در طبقات بالایی" states a PART (balcony) and a FLOOR (upper floor),
    and an element that keeps only one of them is a different requirement.
    """

    lowered = clause.lower()

    found = []

    for canonical, patterns in _FEATURE_LOCATIONS:

        if canonical not in _FLOOR_LOCATION_NAMES:

            continue

        if any(pattern in lowered for pattern in patterns):

            found.append(canonical)

    return found


def _whole_building_visibility(text: str) -> bool:
    """True when the request asks for a view of the WHOLE building.

    SPATIAL_FRAMING_RETENTION_V1 — a camera/framing requirement is a
    requirement, and it used to survive only in the discarded builder tail.

    Fail-closed in BOTH directions, because either half alone is a different
    request:

      * a whole-building noun without a view word is the SCOPE OF THE WORK
        ("کل ساختمان را بازسازی کن" = renovate the whole building), not a
        camera instruction, so it is not reported;
      * a view word without a whole-building noun ("نمای جنوبی",
        "پرسپکتیو داخلی") is an ordinary camera request the existing camera
        path already carries, so it is not converted into this constraint.

    Evaluated CLAUSE BY CLAUSE over the shared splitter so a view word in one
    clause can never combine with a building noun in another.
    """

    for clause in split_clauses(str(text or "")):

        lowered = clause.lower()

        if not any(
            marker in lowered for marker in _WHOLE_BUILDING_MARKERS
        ):

            continue

        if any(marker in lowered for marker in _VIEW_CONTEXT_MARKERS):

            return True

    return False


def _closeup_requested(text: str) -> bool:
    """True when the user asked for a close-up / detail framing."""

    lowered = str(text or "").lower()

    return any(marker in lowered for marker in _CLOSEUP_MARKERS)


def _floor_count_framing(floors: Any, text: str) -> Optional[int]:
    """The exact user-stated floor count that REQUIRES a countable view.

    WHOLE_BUILDING_VISUAL_VERIFIABILITY_V1 — the floor count was represented
    numerically and never as a framing requirement, so a request stating an
    exact count could be answered with a tight crop in which the count is not
    verifiable.

    Grounded in the request, never added indiscriminately:

      * only an EXACT count reaches here — `_floor_count` already drops an
        ambiguous count and a NEGATED count (through `is_affirmed`), so a
        rejected count can never authorise framing;
      * a single storey needs no whole-building framing to be countable;
      * an explicit close-up request IS the user's camera choice, and is never
        silently overridden.
    """

    if not isinstance(floors, dict):

        return None

    value = floors.get("value")

    if not isinstance(value, int) or isinstance(value, bool):

        return None

    if value < 2:

        return None

    if _closeup_requested(text):

        return None

    return value


def _pattern_stated(text: str, pattern: str) -> bool:
    """True when ``pattern`` occurs in ``text`` as a stated word/phrase.

    Latin patterns match on WORD boundaries: "round" must not be found inside
    "background", and "wide" must not be found inside "widespread". Persian
    patterns are matched as substrings, because Persian inflection suffixes
    ("قوسی‌ها") are attached and a boundary test would miss them.
    """

    if pattern.isascii():

        return re.search(
            r"\b" + re.escape(pattern) + r"\b", text, re.IGNORECASE
        ) is not None

    return pattern in text


def _feature_shapes(clause: str) -> List[str]:
    """The shapes the user stated IN THIS CLAUSE, in the table's fixed order.

    A shape is part of the requirement, not decoration: "arched windows" must
    not degrade to "windows". Only AFFIRMED mentions count, so "بدون پنجره
    قوسی" (no arched windows) never attaches "arched".
    """

    lowered = clause.lower()

    # Each matched spelling is blanked out before the next entry is tested, so
    # a more specific shape cannot also be reported through a shorter pattern
    # it contains ("semi-circular" before "circular").
    working = lowered

    found = []

    for canonical, patterns in _FEATURE_SHAPES:

        spelling = next(
            (p for p in patterns if _pattern_stated(working, p)), None
        )

        if spelling is None:
            continue

        working = working.replace(spelling, " " * len(spelling))

        if canonical == "__comparative__":
            continue

        if is_affirmed(clause, spelling):

            found.append(canonical)

    return found


def _count_stated(text: str, pattern: str) -> bool:
    """True when a COUNT word/phrase is stated as a whole token.

    A numeral must never be found inside a longer word: Persian "دو" (two) is
    a substring of "دوم" (second), so "پنجره‌های طبقه دوم" would otherwise ask
    for TWO windows when the user said nothing about a count at all.

    ZWNJ (U+200C) counts as a token boundary, because a Persian number word
    may carry a ZWNJ suffix ("سه‌تا"). A phrase with a space in it ("فقط یک")
    is matched as a phrase, which cannot be embedded in a longer word.
    """

    return re.search(
        r"(?<!\w)" + re.escape(pattern) + r"(?!\w)", text, re.IGNORECASE
    ) is not None


#: Nouns that turn the numeral in front of them into a statement about the
#: NUMBER OF ELEMENT TYPES rather than the number of architectural instances.
#: "نرده فلزی بالکن و جانپناه سنگی پشتبام دو عنصر متفاوت هستند" says the two
#: ELEMENTS are distinct; it is not a request for two parapets. The numeral must
#: actually QUALIFY one of these nouns — optionally through one or two short
#: modifiers ("متفاوت" / "different") — so a genuine quantity that qualifies an
#: element noun ("دو جانپناه سنگی") is left untouched.
_ELEMENT_TYPE_NOUNS = (
    r"عنصر\u200c?(?:ها|های)?", r"نوع\u200c?(?:ها|های)?",
    r"گونه\u200c?(?:ها|های)?", r"elements?", r"types?", r"kinds?",
)

_ELEMENT_TYPE_FOLLOW = re.compile(
    r"\s*(?:\w+\s+){0,2}(?:" + "|".join(_ELEMENT_TYPE_NOUNS) + r")\b",
    re.IGNORECASE,
)


def _numeral_qualifies_element_type(text: str, numeral: str) -> bool:
    """True when ``numeral`` qualifies an ELEMENT-TYPE noun, not an instance.

    Only the occurrence that actually precedes the type noun is disregarded, so
    a REAL quantity ("دو جانپناه سنگی") keeps counting while a relationship
    statement ("دو عنصر متفاوت", "two different elements") does not.
    """

    if not numeral:

        return False

    for match in re.finditer(
        r"(?<!\w)" + re.escape(numeral) + r"(?!\w)", text, re.IGNORECASE
    ):

        if _ELEMENT_TYPE_FOLLOW.match(text, match.end()):

            return True

    return False


def _numeral_qualifies_floor_count(text: str, numeral: str) -> bool:
    """True when ``numeral`` counts FLOORS, not the element in the clause.

    ARCHITECTURAL_REQUIREMENT_GROUNDING_V1 — "ساختمان دو طبقه با یک در چوبی"
    states two FLOORS and one door. The «دو» sits in front of the floor noun
    (`_FLOOR_NOUNS`, the same table the storey reader uses), so it is a storey
    count and must never be read as a quantity of the door. Only the occurrence
    that actually precedes a floor noun is disregarded, so a real quantity
    ("دو در چوبی روی نما") keeps counting.
    """

    if not numeral:

        return False

    lowered = str(text or "").lower()

    for match in re.finditer(
        r"(?<!\w)" + re.escape(numeral.lower()) + r"(?!\w)", lowered
    ):

        if _adjacent(lowered, match.end(), _FLOOR_NOUNS):

            return True

    return False


def _normalise_digits(text: str) -> str:
    """Fold Persian/Arabic-Indic numerals to ASCII so one pattern reads both."""

    return str(text or "").translate(_DIGIT_FOLD)


#: A dimension marking this clause as measuring the element, not counting it.
#: The clause splitter breaks on ".", so the front half of a decimal request
#: ("add a 2" + "4 m wide window") is recovered by the caller before this test
#: is applied to the joined sentence.
_FEATURE_DIMENSION_MARKERS = (
    "متر", "سانتی", "میلی‌متر", " m ", "cm", "mm", "sqm", "m2", "m²",
)


def _decimal_continuation(clause: str, following: str) -> bool:
    """True when two adjacent fragments are the two halves of one decimal.

    The shared clause splitter breaks on ".", so "add a tall window 3.5 m"
    arrives as "… 3" + "5 m". This predicate is the ONLY case in which a
    neighbouring fragment may join the count context; it never widens to a
    neighbour that merely happens to start with a digit.
    """

    return bool(
        following
        and re.search(r"\d\s*$", str(clause or ""))
        and re.match(r"\s*\d", str(following or ""))
    )


def _looks_like_dimension(text: str) -> bool:

    lowered = " %s " % str(text or "").lower().replace(".", " ")

    return any(marker in lowered for marker in _FEATURE_DIMENSION_MARKERS)


def _feature_count(clause: str, context: Optional[str] = None) -> Optional[int]:
    """The explicit count the user stated IN THIS CLAUSE, or None.

    Only an EXPLICIT count is returned: "a single wooden door" is one door,
    but a bare plural ("doors") states no count and must not become one. A
    count already expressed as a word is preferred over a digit, because the
    word form is the one that survives the Persian -> English transition.
    """

    lowered = clause.lower()

    # "دو لنگه" / "double leaf" describes a door's LEAF configuration, not the
    # number of doors. When it is present the numeral belongs to it, so no
    # count is read from this clause at all.
    if any(marker in lowered for marker in _FEATURE_LEAF_MARKERS):

        return None

    # A dimension ("2.4 m wide") measures the element; it never counts it.
    # ``context`` is the clause plus any decimal-fractured continuation, so
    # "… 3" + "5 m" is recognised as the dimension 3.5 m rather than 3 units.
    # The digit scan below MUST read the SAME text the dimension test reads.
    # The clause splitter breaks on ".", so for "add a tall window 3.5 m" the
    # clause alone ends in a bare "3" ("... window 3" + "5 m"); the digit
    # pattern would then read that "3" as a count of three windows. Reading
    # the joined text keeps the fractured decimal whole: the trailing "3" is
    # followed by "." and no longer terminates the fragment.
    count_text = context if context is not None else clause

    if _looks_like_dimension(count_text):

        return None

    # The element noun has to occur in the same clause, which the caller
    # guarantees by only asking about a clause that names an element.
    for word, patterns in _FEATURE_COUNT_WORDS:

        for pattern in patterns:

            # A numeral that qualifies an ELEMENT-TYPE noun is a statement about
            # the relationship between element types ("دو عنصر متفاوت هستند" =
            # the two elements are distinct), never a quantity of THIS element.
            if _numeral_qualifies_element_type(lowered, pattern):

                continue

            # ARCHITECTURAL_REQUIREMENT_GROUNDING_V1 — a numeral that qualifies
            # a FLOOR noun is a storey count, never a quantity of this element.
            if _numeral_qualifies_floor_count(lowered, pattern):

                continue

            if _count_stated(lowered, pattern) and is_affirmed(clause, pattern):

                return {
                    "one": 1, "two": 2, "three": 3, "four": 4,
                }[word]

    # A digit count is read in EITHER order: Persian puts the numeral before
    # the noun ("۴ پنجره"), English before it too ("4 windows"), and a request
    # may put it straight after ("windows: 4"). Persian/Arabic-Indic digits are
    # folded to ASCII first, so the same request works in both scripts.
    folded = _normalise_digits(count_text.lower())

    for pattern in (
        # numeral, then at most a few modifiers, then the element noun
        # ("3 arched windows" is a count; "2 m tall windows" is a dimension)
        r"(?<![\d.])(\d{1,3})\s*(?:عدد|تایی)?\s*"
        r"(?:(?!متر|سانتی|\bm\b|\bcm\b|\bmm\b|[.,])\w+\s+){0,3}"
        r"(?:در|پنجره|بازشو|نرده|بالوستراد|جان‌پناه|doors?|windows?|openings?|"
        r"railings?|balustrades?|parapets?)\b",
        # element noun, optional counter, then the numeral
        r"(?:در|پنجره|بازشو|نرده|بالوستراد|جان‌پناه|doors?|windows?|openings?|"
        r"railings?|balustrades?|parapets?)\s*(?:عدد|تایی)?\s*[:=]?\s*"
        r"(\d{1,3})(?![\d.]|\s*(?:متر|سانتی|m\b|cm\b|mm\b))",
    ):

        match = re.search(pattern, folded, re.IGNORECASE)

        if match:

            value = int(match.group(1))

            # The same element-TYPE rule for a digit numeral ("2 elements"),
            # and the same FLOOR rule for "2 طبقه" in front of an element.
            if value > 0 \
                    and not _numeral_qualifies_element_type(
                        folded, match.group(1)
                    ) \
                    and not _numeral_qualifies_floor_count(
                        folded, match.group(1)
                    ):

                return value

    return None


#: Element labels that are also ordinary Persian function words. "در" means
#: "door", but it is also the preposition "in/at/into" ("در مجموع", "در نظر",
#: "در محل", "در نور") and a substring of "رندر" (render). A SUBSTRING match
#: therefore invents a door in clauses that never mentioned one — that is how
#: the storey clause, the parapet clause and the camera clause all became
#: doors. These labels are matched as WHOLE TOKENS only.
_FEATURE_WORD_BOUNDED_LABELS = ("در",)

#: Persian letters that may legitimately follow a whole-token element label as
#: an attached inflection ("درِ ورودی", "درها", "دری"). A ZWNJ is included
#: because Persian attaches suffixes with it.
_PERSIAN_LETTERS = "ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی"
_PERSIAN_JOINERS = "‌‏"

#: "در" is a genuine homograph: the NOUN "door" and the PREPOSITION
#: "in / at / into / within". A whole-token match cannot tell them apart, so
#: the prepositional collocations are listed explicitly. Each entry is the text
#: that follows the "در" token. Without this, every clause shaped
#: "… در نظر بگیر" / "… در مجموع …" / "… در محل …" was attributed to the door
#: element and donated its count and location to the requirement.
_DOOR_LABEL_PREPOSITION_FOLLOWERS = (
    "مجموع", "نظر", "محل", "نور", "این", "آن", "حال", "واقع", "جهت",
    "سطح", "طبقه", "ساختمان", "هر", "کل", "ضمن", "نتیجه", "صورت",
    "ادامه", "ارتباط", "کنار", "بالا", "بالای", "پایین", "طی", "مورد",
    "زمینه", "حد", "بین", "طول", "عرض", "ارتفاع", "قالب", "خصوص",
    # T2I_TALL_TOWER_PORTRAIT_PRESET_V1 — "در تصویر" means "in the image".
    # Without this existing homograph guard, a full-building framing sentence
    # fabricated a rooftop/ground-floor door and injected it into node 206.
    "تصویر", "شب", "روز",
    # ARCHITECTURAL_REQUIREMENT_GROUNDING_V1 — "در زمین" (in the land / on the
    # site) is the preposition plus a SITE noun, not the door noun. It was
    # missing from this list, so "… با نمای آجری در زمین داشته باشد" produced a
    # door requirement that then borrowed the facade material, the ground/upper
    # floor locations and the «دو» of «دو طبقه بالای آن» as "exactly 2 brick
    # doors". Only the PREPOSITIONAL collocation is added; a door noun is still
    # read from the unambiguous forms ("درها", "در ورودی", "در چوبی").
    "زمین",
)

#: ROOT_HANDOFF_V1 — the vocabularies that ALREADY own the word a prepositional
#: "در" introduces. "در طبقات بالایی" (in the upper floors) is not a special
#: case of anything: it is a "در" followed by a FLOOR noun, and this module owns
#: the floor vocabulary (`_FLOOR_NOUNS` — the same table the storey reader and
#: the dimension reader use). Reading that table covers the whole paradigm at
#: once (singular, plural, ZWNJ spellings and the English words), so a new floor
#: spelling never needs a new "در" entry.
#:
#: MEASURED DEFECT: the follower tuple above listed the SINGULAR "طبقه" and
#: nothing else, so "در طبقات بالایی پنجره بگذار" read the "در" as the DOOR
#: noun. That single misreading invented a door requirement AND shadowed the
#: window the clause actually asked for; inside a balcony request ("برای بالکن
#: در طبقات بالایی نرده فلزی اضافه کن") it replaced the railing with a door.
#:
#: DELIBERATELY NOT IN THIS TABLE: the location vocabulary. A prepositional
#: reading is not safe there, because "در ورودی" is BOTH the compound noun
#: "entrance door" ("یک در ورودی چوبی") and the phrase "at the entrance" — the
#: two cannot be told apart by the following word. That ambiguity is reported as
#: unresolved instead of patched with a guess.
_DOOR_PREPOSITION_SCOPE_TERMS = tuple(_FLOOR_NOUNS)

#: The location vocabulary a prepositional "در" may introduce. Reused as-is from
#: `_FEATURE_LOCATIONS`: no new table is created.
_DOOR_PREPOSITION_LOCATION_TERMS = tuple(
    pattern for _canonical, patterns in _FEATURE_LOCATIONS for pattern in patterns
)


def _without_joiner(text: str) -> str:
    """The text with ZWNJ removed, for VOCABULARY matching only.

    A ZWNJ is a joiner, not a letter: "rooftop", "staircase" and "parapet" are
    written by users both with and without it, and the module's own label tables
    already carry both spellings in places. Comparing through this normalisation
    keeps ONE table authoritative for both spellings instead of needing a new
    entry for every typed variant — which is what a follower list always ends up
    needing. It is deliberately not applied to the emitted text or to any
    offset, only to a yes/no vocabulary test.
    """

    return str(text or "").replace("\u200c", "")


def _door_introduces_location(text: str, index: int) -> bool:
    """True when the "در" at ``index`` introduces the LOCATION of the request.

    ROOT_HANDOFF_V1 — "در" is a homograph, and a follower list can never finish
    the job. "در نما پنجره بگذار" (put a window on the facade) and
    "در پشت\u200cبام یک نورگیر بگذار" (put a skylight on the roof) both produced a
    DOOR for the facade / the rooftop and lost the window that was asked for;
    "در پشت\u200cبام جانپناه سنگی بگذار" produced a door for the rooftop instead of
    the parapet. The signal is the clause's own STRUCTURE, not another listed
    word: the "در" is directly followed by a target LOCATION and the same span
    then names ANOTHER element — so the location is WHERE that other element
    goes, and the "در" cannot be this element's noun.

    Only a DIFFERENT element counts, so a genuine door compound keeps its noun
    reading: "یک در ورودی چوبی" and "دو در چوبی روی نما" name no other element,
    and "در بالکن یک در چوبی بگذار" names the door again — it asks for a door,
    located on the balcony.
    """

    tail = str(text or "")[index + 2:].lstrip(" \u200c")

    if not tail:

        return False

    if not any(
        _without_joiner(tail).startswith(_without_joiner(term))
        for term in _DOOR_PREPOSITION_LOCATION_TERMS
        if term
    ):

        return False

    for element in _FEATURE_ELEMENT_ORDER:

        if element == "door":

            continue

        for pattern in dict(_FEATURE_ELEMENT_LABELS).get(element, ()):

            if _label_position(text, pattern) is not None:

                return True

    return False


def _door_label_is_noun(text: str, index: int) -> bool:
    """True when the "در" at ``index`` is the NOUN (door), not the preposition.

    The test is the word that follows it. The "در" introduces a CIRCUMSTANCE —
    not a door — when that word is either one of the listed prepositional
    collocations ("in total", "at the correct location") or a member of a
    vocabulary this module already owns for a non-element role (a FLOOR noun).
    A word that follows a genuine door noun ("در ورودی" = entrance door,
    "در چوبی" = wooden door) belongs to no such table and keeps the noun
    reading.

    The third test is STRUCTURAL, not lexical: a "در" directly followed by a
    target LOCATION while the same span names ANOTHER element is introducing
    that location ("put a skylight on the roof"), so it is not an element noun
    either.
    """

    tail = str(text or "")[index + 2:].lstrip(" ‌")

    if not tail:

        return True

    normalized = _without_joiner(tail)

    for follower in _DOOR_LABEL_PREPOSITION_FOLLOWERS:

        if normalized.startswith(_without_joiner(follower)):

            return False

    for term in _DOOR_PREPOSITION_SCOPE_TERMS:

        if term and normalized.startswith(_without_joiner(term)):

            return False

    if _door_introduces_location(text, index):

        return False

    return True


def _label_position(text: str, pattern: str) -> Optional[int]:
    """The index where ``pattern`` names the element in ``text``, or None.

    ROOT_HANDOFF_V1 — the SAME acceptance rules as ``_label_stated`` (whole
    tokens for homograph labels, word boundaries for Latin labels, substrings
    for inflected Persian labels), returned as a POSITION. Element IDENTITY and
    attribute SCOPE must agree about which mention they are looking at, so both
    read this one function instead of re-deciding what a mention is.
    """

    lowered = str(text or "").lower()

    search = pattern.lower()

    if pattern not in _FEATURE_WORD_BOUNDED_LABELS:

        if search.isascii():

            match = re.search(r"\b" + re.escape(search) + r"\b", lowered)

            return match.start() if match else None

        index = lowered.find(search)

        return index if index >= 0 else None

    start = lowered.find(search)

    while start >= 0:

        before = lowered[start - 1] if start else ""

        end = start + len(search)

        after = lowered[end] if end < len(lowered) else ""

        # a following ZWNJ is an attached suffix ("درِ"), not a new word
        if after in _PERSIAN_JOINERS:

            after = lowered[end + 1] if end + 1 < len(lowered) else ""

        # An EMPTY string is a substring of everything, so the clause-initial
        # case must be excluded explicitly rather than tested with `in`.
        before_ok = not before or before not in _PERSIAN_LETTERS

        after_ok = not after or after not in _PERSIAN_LETTERS

        if before_ok and after_ok and _door_label_is_noun(lowered, start):

            return start

        start = lowered.find(search, start + 1)

    return None


def _label_stated(text: str, pattern: str) -> bool:
    """True when ``pattern`` names the element in ``text`` as a whole token.

    Latin patterns keep the existing word-boundary behaviour. Persian patterns
    are substring-matched by default, because Persian inflections attach to the
    noun ("پنجره‌ها"). A label that is ALSO an ordinary function word cannot
    use that rule, so it is matched with an explicit token boundary on both
    sides: the character before must not be a Persian letter, and the character
    after must not be a letter that would extend it into another word
    ("رندر"). The homograph "در" is additionally rejected in its prepositional
    collocations ("در مجموع", "در نظر", "در محل", "در نور") and before a FLOOR
    noun ("در طبقات بالایی").
    """

    return _label_position(text, pattern) is not None


def _element_mentions(clause: str) -> List[Tuple[int, str]]:
    """Every element this clause names, as (position, element), in order.

    ROOT_HANDOFF_V1 — identity must come from the clause's OWN order. The
    element table's order (door, window, opening, railing, balustrade, parapet)
    is a REPORT order, but it was also deciding identity, so a clause naming two
    elements was attributed to whichever appeared earlier IN THE TABLE rather
    than in the sentence. That is how "در طبقات بالایی پنجره بگذار" became a
    door and hid the window it actually asked for, and how a parapet clause that
    merely mentioned the railing ("... که با نرده بالکن متفاوت باشد") became a
    second railing request and donated the rooftop to it.

    The acceptance tests are the module's existing ones — `_label_position`
    (whole-token homograph labels) and `is_affirmed` (a noun inside a negation
    is not a request) — so no new notion of a mention is introduced.
    """

    mentions: List[Tuple[int, str]] = []

    for element in _FEATURE_ELEMENT_ORDER:

        position: Optional[int] = None

        for pattern in dict(_FEATURE_ELEMENT_LABELS).get(element, ()):

            if not is_affirmed(clause, pattern):

                continue

            found = _label_position(clause, pattern)

            if found is None:

                continue

            if position is None or found < position:

                position = found

        if position is not None:

            mentions.append((position, element))

    mentions.sort(key=lambda item: item[0])

    return mentions


def _element_in_clause(clause: str) -> Optional[str]:
    """The element this clause is ABOUT, or None.

    The element named EARLIEST wins, because that is the clause's own subject; a
    later mention is a reference ("... که با نرده بالکن متفاوت باشد" = which
    differs from the balcony railing) or a complement, not a second request. The
    element table's order no longer decides identity, so a label that is also an
    ordinary word ("در" = door AND in/at) can no longer claim a clause it merely
    appears in.

    Only AFFIRMED mentions count: a noun inside a negation is not a request to
    build anything. The affirmation test is the project's existing negation
    scope helper, not a second one.
    """

    mentions = _element_mentions(clause)

    return mentions[0][1] if mentions else None


def _own_attribute_scope(clause: str, element: str) -> str:
    """The span of ``clause`` whose material / location / shape belongs to it.

    ROOT_HANDOFF_V1 — the module's rule for FRAGMENTS is that a fragment naming
    a DIFFERENT element is never inside an element's attribute scope. The same
    rule holds inside one clause: "جانپناه سنگی پشت‌بام هم داشته باشد که با
    نرده بالکن متفاوت باشد" names the parapet and then REFERS to the balcony
    railing to state a difference. Reading the whole clause gave the railing the
    rooftop and the stone, and dropped the parapet entirely.

    The span is the clause up to the first mention of a different element. A
    clause that names only its own element is returned UNCHANGED, so no
    legitimate descriptor is ever dropped, and the authorisation / exclusion /
    negation tests keep reading the full resolved scope.
    """

    mentions = _element_mentions(clause)

    for position, other in mentions:

        if other != element:

            if position > 0:

                return clause[:position].strip()

            return clause

    return clause


def _clause_states_missing_information(clause: str) -> bool:
    """True when this clause only reports that a quantity is NOT specified.

    VISUAL_ACCEPTANCE_BLOCKER_REPAIR_V1 — "تعداد درها مشخص نشده است" (the number
    of doors has not been specified) names the door element and then inherited
    `enumeration_open` authorisation from an earlier feature clause, so it
    emitted `REQUIRED ARCHITECTURAL FEATURE — include doors`. That is a
    META-STATEMENT about missing information, not an instruction to create an
    element, and it is neither a requirement nor a prohibition: the clause is
    skipped, so no door requirement and no "Do NOT use" line is produced.
    """

    lowered = clause.lower()

    return any(
        marker in lowered for marker in _FEATURE_META_INFORMATION_MARKERS
    )


def _clause_is_excluded(clause: str) -> bool:
    """True when this clause excludes the element it names.

    A preservation phrase ("پنجره‌ها را دست نزن") or a removal phrase
    ("نرده را حذف کن") names the element but does NOT ask for it to exist.
    """

    lowered = clause.lower()

    return any(marker in lowered for marker in _FEATURE_NEGATION_MARKERS)


def _clause_authorises_feature(clause: str, enumeration_open: bool = False) -> bool:
    """True when this clause ASKS for the element it names to exist.

    An authorisation comes from an explicit ADD / REQUEST verb ("اضافه کن",
    "add", "نصب کن"), a design request ("طراحی کن", "design"), or an element
    introduced with "با" / "with" ("ساختمانی با پنجره‌های قوسی").

    The last shape is deliberately narrow. "با" also occurs in appearance edits
    ("پنجره را با رنگ عوض کن" = repaint the window), so a clause that carries
    BOTH an appearance object and a change verb is an edit of an existing
    element, never a request to add one.

    ``enumeration_open`` continues a request already authorised earlier in the
    same turn, which is what makes "…with arched windows AND stone balcony
    railings" authorise the railing too.
    """

    lowered = clause.lower()

    has_appearance = any(
        marker in lowered for marker in _FEATURE_APPEARANCE_OBJECTS
    )

    has_change = any(marker in lowered for marker in _FEATURE_CHANGE_VERBS)

    if has_appearance and has_change:

        return False

    if any(marker in lowered for marker in _FEATURE_ADD_VERBS):

        return True

    if any(marker in lowered for marker in _FEATURE_DESIGN_MARKERS):

        return True

    if any(marker in lowered for marker in _FEATURE_INTRODUCING_MARKERS):

        return True

    return enumeration_open


# ==========================================================
# COORDINATED-FEATURE RECOVERY
#
# MEASURED DEFECT (PERSIAN_COORDINATION_FIX_V1): the shared clause splitter
# breaks on "و"/"and", so a natural coordinated description is destroyed:
#
#   "پنجره‌های بلند و قوسی به نما اضافه کن"
#      -> "پنجره‌های بلند"          (element, NO authorising verb)
#      -> "قوسی به نما اضافه کن"    (shape + verb, NO element)
#
# and the feature never reaches the sampler at all. The same break silently
# drops the FIRST element of "یک در چوبی و دو پنجره قوسی اضافه کن".
#
# This pass is LOCAL to feature extraction. It re-joins fragments that
# coordination split apart, so the clause seen by the existing extractors is
# the one the user wrote. Nothing here changes `split_clauses`, and every
# existing authorisation / negation / exclusion test still runs afterwards on
# the result — this pass only restores text, it never grants authority.
# ==========================================================

#: An element noun that implicitly requests the element ("در چوبی" = a wooden
#: door). Used only to recognise where a clause has gone wrong: a fragment
#: whose element is separated from its descriptor cannot be resolved from the
#: authorisation signals alone.
def _opens_with_shape(text: str) -> bool:
    """True when a fragment starts with a shape word, not an element noun."""

    tokens = str(text or "").strip().split()

    if not tokens:
        return False

    head = tokens[0].lower()

    for _canonical, patterns in _FEATURE_SHAPES:

        for pattern in patterns:

            if pattern.isascii():

                if re.match(re.escape(pattern) + r"\b", head):
                    return True

            elif head.startswith(pattern):

                return True

    return False


#: The verbs that make a coordinated fragment an ADD request of its own.
#: Deliberately narrower than `_FEATURE_ADD_VERBS`: the loose "با" / "with"
#: entries only introduce an element, they do not ask for one to be added, so
#: they must not authorise a NEIGHBOURING element through coordination.
_FEATURE_COORDINATION_VERBS = (
    "اضافه کن", "اضافه کنید", "اضافه‌اش کن", "اضافه کنم", "اضافه شود",
    "اضافه بشه", "بگذار", "بذار", "نصب کن", "بساز", "بسازید", "درست کن",
    "ایجاد کن", "بزن", "طراحی کن", "طراحی کنید",
    "add", "include", "incorporate", "install", "place", "introduce",
    "design", "create", "build", "generate", "draw",
)


def _clause_is_add_request(clause: str) -> bool:
    """True when this fragment carries its OWN explicit ADD / DESIGN verb."""

    lowered = str(clause or "").lower()

    return any(marker in lowered for marker in _FEATURE_COORDINATION_VERBS)


#: A descriptive Persian predicate: the fragment STATES what the element is
#: like ("قوسی باشد" = "should be arched") without asking for anything to be
#: added. Only these may complete a neighbour's description, and only when
#: nothing else in the fragment qualifies it.
_DESCRIPTIVE_PREDICATES = (
    "باشد", "باشند", "باشه", "هستند", "است", "داشته", "دارد", "دارند",
    "should be", "must be", "has", "have", "are", "is",
)

#: Words that carry no architectural content: pure coordination and copulas.
#: After removing them (and the shape vocabulary) a descriptor fragment must be
#: EMPTY, otherwise it is saying something the previous fragment did not.
_FILLER_TOKENS = (
    "و", "and", "،", ",", "با", "with",
) + _DESCRIPTIVE_PREDICATES


def _clause_completes_description(clause: str) -> bool:
    """True when this fragment ONLY describes the element before it.

    MEASURED DEFECT: the shared splitter breaks the coordination in
    "نمای ساختمان دارای پنجره‌های بلند و قوسی باشد" into
    "…پنجره‌های بلند" + "قوسی باشد". The first fragment names the element, the
    second carries the adjective, and neither is an add request — so the window
    shape was reduced to "tall" and "arched" never reached the sampler.

    This predicate is deliberately narrow. The fragment must
        * name no element of its own,
        * exclude nothing, change nothing, observe nothing,
        * open with a shape word, and
        * contain NOTHING except shape words, coordination and a copula.
    "قوسی باشد" qualifies. "قوسی نصب کن" (an add request), "قوسی نکن"
    (excluded), "قوسی را تغییر بده" (a change) and "قوسی پنجره" (names an
    element) all fail, so no authority is ever granted from here.
    """

    text = str(clause or "").strip()

    if not text:

        return False

    if _element_in_clause(text):

        return False

    if _clause_is_excluded(text):

        return False

    lowered = text.lower()

    if any(marker in lowered for marker in _FEATURE_CHANGE_VERBS):

        return False

    if any(marker in lowered for marker in _FEATURE_APPEARANCE_OBJECTS):

        return False

    if any(marker in lowered for marker in _FEATURE_OBSERVATION_MARKERS):

        return False

    if not _opens_with_shape(text):

        return False

    # Remove every shape spelling, then every filler. Anything left over means
    # the fragment says more than "this element has this shape".
    #
    # Removal is on WHOLE TOKENS, never by substring: Persian "و" is a single
    # letter and a substring of countless ordinary words, so a substring
    # replacement would hollow out innocent text and silently widen this gate.
    remaining = lowered

    for _canonical, patterns in _FEATURE_SHAPES:

        for pattern in patterns:

            remaining = remaining.replace(pattern, " ")

    tokens = [token for token in remaining.split() if token]

    for token in tokens:

        if not any(token == filler for filler in _FILLER_TOKENS):

            return False

    return True


#: The two FLOOR levels a fragment may contribute to a neighbouring element.
_FLOOR_LOCATIONS = ("ground floor", "upper floor")


def _clause_adds_only_floor(clause: str) -> bool:
    """True when this fragment contributes ONLY a floor the element stands on.

    Deliberately narrow, in the same spirit as ``_clause_completes_description``:

      * it names no element of its own (else it is a different ask),
      * it excludes, changes or observes nothing,
      * it states at least one FLOOR location, and
      * its ONLY locations are floors — a fragment that also names a material
        or a part-location ("چوبی روی نما") is NOT absorbed, so no attribute
        can migrate to the neighbouring element.
    """

    text = str(clause or "").strip()

    if not text:

        return False

    if _element_in_clause(text):

        return False

    if _clause_is_excluded(text):

        return False

    lowered = text.lower()

    if any(marker in lowered for marker in _FEATURE_CHANGE_VERBS):

        return False

    if any(marker in lowered for marker in _FEATURE_APPEARANCE_OBJECTS):

        return False

    if any(marker in lowered for marker in _FEATURE_OBSERVATION_MARKERS):

        return False

    if not _feature_floors(text):

        return False

    # A part-location in the same fragment would be that part's own claim
    # ("... روی نما"), so the fragment is not a pure floor continuation.
    return not _feature_locations(text)


def _leading_descriptor(text: str) -> bool:
    """True when a fragment can only be the lead-in of the next element.

    It names no element, excludes nothing, and states no change of its own —
    "add tall" qualifies. A fragment that edits an existing thing ("نمای قوسی
    را تغییر بده") does not, so its shape can never leak into the element that
    follows it.
    """

    if not text:

        return False

    lowered = text.lower()

    if _element_in_clause(text):

        return False

    if _clause_is_excluded(text):

        return False

    if any(marker in lowered for marker in _FEATURE_CHANGE_VERBS):

        return False

    if any(marker in lowered for marker in _FEATURE_APPEARANCE_OBJECTS):

        return False

    if any(marker in lowered for marker in _FEATURE_OBSERVATION_MARKERS):

        return False

    return True


def _chain_add_request(fragments: List[str]) -> bool:
    """True when an element LIST ends in one explicit ADD request.

    "پنجره و در و نرده اضافه کن" is three elements sharing one verb at the end
    of the list. Only fragments that are bare element nouns (no verb of their
    own, nothing excluded) may sit between the element and that verb, so a
    negated, preserved or edited element can never borrow the verb.
    """

    if not fragments:

        return False

    last = fragments[-1]

    if _clause_is_excluded(last) or not _clause_is_add_request(last):

        return False

    for fragment in fragments[:-1]:

        if _clause_is_excluded(fragment):

            return False

        if _clause_is_add_request(fragment):

            return False

        if not _element_in_clause(fragment):

            return False

    return True


def _segment_scope(
    segment: str, previous: str, following: str, trailing: Optional[List[str]] = None
) -> Optional[Tuple[str, bool]]:
    """The text an element named in ``segment`` may be extracted from, or None.

    Returns ``(scope, inherited_authorisation)``: the ATTRIBUTE SCOPE — the
    fragments whose material / location / shape / count legitimately describe
    THIS element — and whether the request is authorised by a coordinated
    neighbour rather than by the scope's own text. A fragment that names a
    different element is never inside the scope, which is what stops one
    element's attributes migrating to another. None when the element is not
    requested at all.

    Four coordination shapes are recovered, and nothing else:

    1. The element has its own authorising verb — scope is the segment itself.
       Unchanged behaviour.

    2. The element was separated from its verb by coordination, and the next
       fragment completes the description and owns the verb
           "پنجره‌های بلند" + "قوسی به نما اضافه کن"
       Scope is both fragments: the following one names no other element, so
       its "قوسی" and its "نما" belong to this window. The verb authorises the
       request, and is reported as inherited rather than inserted into the
       scope — a bare element noun must not authorise itself.

    3. Coordination put a descriptor BEFORE the element
           "add tall" + "arched windows to the facade"
       Scope is both fragments: the leading fragment names no element, excludes
       nothing, and changes nothing.

    4. The element stands alone with no verb. Scope is its own fragment; the
       caller's existing enumeration rule decides whether it was requested
       ("…and a single wooden door at the entrance").

    When the next fragment names ANOTHER element ("یک در چوبی" + "دو پنجره
    قوسی اضافه کن"), the door is authorised by that verb but its scope stays
    its own fragment — the windows' "قوسی" and "دو" are not the door's.

    An excluded segment is never rescued, and an excluded / non-authorising
    neighbour never completes a request. That is what keeps
    "در را حذف کن و پنجره اضافه کن" from resurrecting the door.
    """

    if _clause_is_excluded(segment):
        return None

    # 2c FIRST — a following fragment that ONLY describes this element always
    #     belongs to it, whether or not the element's own clause already
    #     authorises it. "نمای ساختمان دارای پنجره‌های بلند" authorises the
    #     window through "دارای", so checking shape 1 first would end the scope
    #     there and silently drop the coordinated "قوسی". The descriptor grants
    #     nothing: authorisation still comes from the element's own clause.
    if following and _clause_completes_description(following):

        return segment + " و " + following, False

    # 2d — a following fragment that adds ONLY a FLOOR location the element
    #      stands on. SPATIAL_FRAMING_RETENTION_V1: the shared splitter breaks
    #      "بالکنی مشخص و قابل‌تشخیص در طبقات بالایی طراحی کن" into
    #      "برای ساختمان بالکنی مشخص" + "قابل‌تشخیص در طبقات بالایی طراحی کن",
    #      so the balcony kept its part-location ("balcony") and lost the floor
    #      the user actually stated. The fragment is absorbed only when it
    #      names no other element, excludes nothing, and its locations are
    #      EXACTLY the floor levels — a fragment that also carries a material
    #      or a part-location stays out, so no other attribute can ride along.
    if following and _clause_adds_only_floor(following):

        return segment + " و " + following, False

    # 1 — the segment asks for its own element. Unchanged behaviour.
    if _clause_authorises_feature(segment, False):
        return segment, False

    # 2 — coordination separated the element from its verb.
    #
    # 2a — a later fragment supplies the verb and completes the description
    #      ("پنجره‌های بلند" + "قوسی به نما اضافه کن"). Its shape and location
    #      belong to THIS element, so they are inside the scope. The verb
    #      authorises the request, yet it is intentionally NOT in the text:
    #      a bare element noun is not an add request of its own.
    if following \
            and _opens_with_shape(following) \
            and not _element_in_clause(following) \
            and _clause_is_add_request(following) \
            and not _clause_is_excluded(following):

        return segment + " و " + following, True

    # 2b — a later fragment supplies the verb but names ANOTHER element
    #      ("یک در چوبی" + "دو پنجره قوسی اضافه کن"). The coordinated verb
    #      authorises this element too, but the scope stays its own fragment:
    #      the other element's shape and count are not its own.
    if following \
            and _element_in_clause(following) \
            and _clause_is_add_request(following):

        return segment, True

    # 3 — coordination put the verb or a pure descriptor BEFORE the element
    #     ("add tall" + "arched windows to the facade"). Only a lead fragment
    #     that can describe something is absorbed; one that names another
    #     element, excludes one, or edits an existing one is a different ask.
    if previous and _leading_descriptor(previous):

        return previous + " " + segment, False

    # 4 — an ELEMENT LIST shares one verb at its end
    #         "پنجره و در و نرده اضافه کن"
    #     The coordinating verb authorises every bare noun before it. Each
    #     element keeps its OWN scope, so no attribute migrates; the verb is
    #     inherited, exactly as in shape 2.
    if trailing and _chain_add_request(list(trailing)) \
            and not _clause_is_add_request(segment):

        return segment, True

    # 5 — the element stands on its own with no verb. Scope is its own
    #     fragment; the caller's existing enumeration rule decides whether a
    #     request opened earlier in the turn authorises it ("…and a single
    #     wooden door at the entrance").
    return segment, False


def _splice_decimal_fractures(clauses: List[str]) -> List[str]:
    """Rejoin clauses the shared splitter broke INSIDE a decimal number.

    "۳.۵" is one dimension, but the shared splitter breaks on "." and hands back
    "... به ارتفاع ۳" + "۵ متر روی نما بگذار". The pair is spliced back once, on
    the clause LIST, before ANY consumer reads it — element identity,
    authorisation, shapes and count must all be read from the same fragments.

    ROOT_HANDOFF_V1 — the previous repair spliced inside the reading loop, after
    the element had already been resolved, so it could only ever help a clause
    whose element stood in the SAME fragment as the verb. A request whose
    element stood one fragment earlier, separated from its verb by coordination
    ("یک پنجره بلند" + "قوسی به ارتفاع ۳" + "۵ متر روی نما بگذار"), still lost
    its window entirely — while the same request with "۳ متر" survived. Splicing
    the list first is both a repair of that loss and what keeps a DIMENSION from
    becoming a COUNT, which is why the rule is kept, unchanged, at this level.
    """

    spliced: List[str] = []

    for clause in clauses:

        if spliced and re.search(r"\d\s*$", spliced[-1]) \
                and re.match(r"\s*\d", clause):

            spliced[-1] = (
                spliced[-1].rstrip() + "." + clause.lstrip()
            ).strip()

            continue

        spliced.append(clause)

    return spliced


def _feature_requirements(text: str) -> List[Dict[str, Any]]:
    """Explicitly requested architectural features, or [] when none were asked.

    Resolved CLAUSE BY CLAUSE, so an element's material and location come only
    from the clause that names it: "arched windows and stone balcony railings"
    must not give the windows a stone material it never had.
    """

    if not text:

        return []

    lowered = text.lower()

    # A request that only observes, hedges or excludes the whole turn carries
    # no feature authorisation at all.
    if any(marker in lowered for marker in _FEATURE_OBSERVATION_MARKERS):

        return []

    if any(marker in lowered for marker in _FEATURE_OPTIONAL_MARKERS):

        return []

    requirements: List[Dict[str, Any]] = []

    seen: Dict[str, Dict[str, Any]] = {}

    enumeration_open = False

    clauses = split_clauses(text)

    clauses = _splice_decimal_fractures(clauses)

    for index, clause in enumerate(clauses):

        previous = clauses[index - 1] if index else ""

        element = _element_in_clause(clause)

        # SPATIAL_FRAMING_RETENTION_V1 — a building PART that the vocabulary
        # owns as a LOCATION ("بالکن", "ایوان") can be the subject of its own
        # request without naming an element from the element table. When such
        # a clause ALSO states the floor the part stands on, the pair is a
        # real, stated spatial requirement: "بالکن ... در طبقات بالایی".
        # Resolved here, before the element lookup, so it can never be read as
        # an attribute of a later element.
        if not element:

            _following_part = (
                clauses[index + 1] if index + 1 < len(clauses) else ""
            )

            _located = _located_part_requirement(
                clause, previous, _following_part
            )

            if _located is not None:

                _merge_spatial_requirement(_located, seen, requirements)

            continue

        following = clauses[index + 1] if index + 1 < len(clauses) else ""

        # PERSIAN_COORDINATION_FIX_V1 — coordination may have separated this
        # element from the verb, or a descriptor from the element it belongs
        # to. Resolve the scope FIRST; every authorisation / exclusion test
        # below then runs on the text the user actually wrote, with the same
        # rules as before.
        resolved = _segment_scope(
            clause, previous, following, clauses[index + 1:]
        )

        if resolved is None:

            continue

        scope, authorised_by_neighbour = resolved

        # ROOT_HANDOFF_V1 — a clause may NAME a second element only to RELATE the
        # two ("... که با نرده بالکن متفاوت باشد" = which differs from the
        # balcony railing). The rule that governs FRAGMENTS — a fragment naming
        # a different element is never inside an attribute scope — is applied
        # inside the clause as well, so a reference never donates its location
        # or material to this element. Authorisation, exclusion and negation
        # keep reading the FULL resolved scope; only the attribute text is
        # narrowed.
        attribute_scope = _own_attribute_scope(scope, element)

        if _clause_is_excluded(scope):

            continue

        # VISUAL_ACCEPTANCE_BLOCKER_REPAIR_V1 — a clause that only reports an
        # unspecified quantity is not a request for the element it names.
        if _clause_states_missing_information(scope):

            continue

        if not authorised_by_neighbour \
                and not _clause_authorises_feature(scope, enumeration_open):

            continue

        enumeration_open = True

        material = _feature_material(attribute_scope)

        locations = _feature_locations(attribute_scope)

        floors = _feature_floors(attribute_scope)

        shapes = _feature_shapes(attribute_scope)

        # The neighbour is added to the count context ONLY when the scope ends
        # in a bare digit and the neighbour starts with one — i.e. a decimal
        # split by the shared clause splitter ("… 3" + "5 m"). In every other
        # case the context is the scope alone: a neighbour naming ANOTHER
        # element ("سه طبقه" + "یک در") must never donate its numeral, which is
        # what turned the storey count سه into "exactly 3 wood doors".
        count_context = attribute_scope

        if _decimal_continuation(attribute_scope, following):

            count_context = attribute_scope.rstrip() + "." + following.lstrip()

        count = _feature_count(attribute_scope, context=count_context)

        if element in seen:

            # The same element named in a second clause adds its locations and
            # shapes; a material/count is only adopted when the first clause
            # stated none — the same never-invent rule, in both directions.
            existing = seen[element]

            if existing.get("material") is None and material:

                existing["material"] = material

            if existing.get("count") is None and count is not None:

                existing["count"] = count

            for location in locations:

                if location not in existing["locations"]:

                    existing["locations"].append(location)

            for floor in floors:

                if floor not in existing["floors"]:

                    existing["floors"].append(floor)

            for shape in shapes:

                if shape not in existing["shapes"]:

                    existing["shapes"].append(shape)

            continue

        requirement = {
            "element": element,
            "group": _FEATURE_ELEMENT_GROUP.get(element, "opening"),
            "material": material,
            "locations": list(locations),
            "floors": list(floors),
            "shapes": list(shapes),
            "count": count,
        }

        seen[element] = requirement

        requirements.append(requirement)

    return requirements


#: Building PARTS this module speaks, mapped to the element-table identity they
#: share. A part is a real architectural element; only its NAME is owned by the
#: location vocabulary, which is why it is resolved here and not in
#: `_FEATURE_ELEMENT_LABELS` (a word has ONE owner in this module).
_FEATURE_PART_NAMES = {
    "balcony": ("balcony", "balconies"),
    "terrace": ("terrace", "terraces"),
}


def _located_part_requirement(
    clause: str, previous: str, following: str = ""
) -> Optional[Dict[str, Any]]:
    """The PART + FLOOR spatial requirement this clause states, or None.

    SPATIAL_FRAMING_RETENTION_V1 — "بالکنی مشخص ... در طبقات بالایی" used to
    yield nothing, because a part word is owned by the LOCATION vocabulary and
    the element table never saw it. The result was that the balcony itself was
    never a requirement and the floor the user put it on travelled only in the
    builder tail that the authoritative handoff skips.

    The shared splitter separates the part from the floor it stands on
    ("برای ساختمان بالکنی مشخص" + "قابل‌تشخیص در طبقات بالایی طراحی کن"), so
    the pair is recovered from ADJACENT fragments — never from an arbitrary
    distance, and never from a fragment that names another element.

    Fail-closed, and each half must come from exactly one fragment:
      * the PART from this fragment, the FLOOR from this one or the next;
      * a fragment naming another element is not consulted for either half;
      * the request must be authorised by a verb in one of the three;
      * a part with no stated floor is a different request and is left alone;
        a floor with no part ("دو طبقه بالای آن") is massing, not a feature.
    """

    text = str(clause or "").strip()

    if not text:

        return None

    if _clause_is_excluded(text):

        return None

    if _element_in_clause(text):

        return None

    parts = _feature_locations(text)

    if not parts:

        return None

    part = parts[0]

    if part not in _FEATURE_PART_NAMES:

        return None

    floors = _feature_floors(text)

    if not floors:

        neighbour = str(following or "")

        if neighbour \
                and not _element_in_clause(neighbour) \
                and not _clause_is_excluded(neighbour) \
                and not _feature_locations(neighbour):

            floors = _feature_floors(neighbour)

    # The request must ASK for the part — by its own verb in this fragment, or
    # by a verb in the fragment that carries the rest of the description
    # ("بالکنی مشخص" + "... در طبقات بالایی طراحی کن"). No exclusion or
    # observation rule is relaxed.
    authorising_text = " ".join(
        [text, str(previous or ""), str(following or "")]
    )

    if not _clause_authorises_feature(authorising_text, False):

        return None

    # A part with NO stated floor is still a requested part: it is emitted
    # with `floors` empty, so the sentence says the part exists and says
    # NOTHING about where it is. That is what keeps "a three-storey building
    # with a balcony" from inventing an upper floor.
    return {
        "element": part,
        "group": "opening",
        "material": None,
        "locations": [part],
        "floors": list(floors),
        "shapes": [],
        "count": None,
        "spatial_only": True,
    }


def _merge_spatial_requirement(
    requirement: Dict[str, Any],
    seen: Dict[str, Dict[str, Any]],
    requirements: List[Dict[str, Any]],
) -> None:
    """Add or extend ONE located-part requirement, never duplicating it."""

    element = requirement["element"]

    if element not in seen:

        seen[element] = requirement

        requirements.append(requirement)

        return

    existing = seen[element]

    for floor in requirement.get("floors") or []:

        if floor not in existing["floors"]:

            existing["floors"].append(floor)


def _feature_sentence(requirement: Dict[str, Any]) -> str:
    """ONE deterministic English sentence stating a requested feature.

    Reports only what the request stated: the element, its semantic group and
    the location/material when the user named one. Nothing is inferred.
    """

    element = str(requirement.get("element") or "").strip()

    group = str(requirement.get("group") or "opening").strip()

    material = requirement.get("material")

    locations = [
        str(item) for item in (requirement.get("locations") or []) if item
    ]

    # SPATIAL_FRAMING_RETENTION_V1 — an element's OWN NAME already says its
    # part-location ("بالکن" -> "balcony"), so restating it would read
    # "include balcony for the balcony". The entry is dropped ONLY when it is
    # exactly the element's own name; a genuinely different part ("railing
    # for the balcony") is still spoken.
    parts = [
        location for location in locations
        if location.lower() != element.lower()
    ]

    # The FLOOR the element stands on is a separate claim and is stated as a
    # floor ("on the upper floor"), never as another part.
    floors = [
        str(item) for item in (requirement.get("floors") or []) if item
    ]

    shapes = [
        str(item) for item in (requirement.get("shapes") or []) if item
    ]

    count = requirement.get("count")

    if not isinstance(count, int) or count <= 0:

        count = None

    # A door/window requirement is stated in the plural, because the request
    # asks for the element to be present, not for one named unit of it —
    # unless the user stated an explicit count, in which case the sentence
    # must state exactly that count or it is not the requirement they gave.
    if element in ("window", "door"):

        noun = element if count == 1 else element + "s"

    else:

        noun = element

    # The adjective chain is emitted in a fixed order (shape -> material ->
    # noun) so the same request always yields byte-identical output, and it
    # carries ONLY what the request stated.
    modifiers = list(shapes) + ([str(material)] if material else [])

    if count is not None:

        article = {
            1: "exactly 1", 2: "exactly 2", 3: "exactly 3", 4: "exactly 4",
        }.get(count, "exactly %d" % count)

        modifiers.insert(0, article)

    phrase = " ".join(modifiers + [noun])

    if parts:

        phrase += " for the " + " and ".join(parts)

    # SPATIAL_FRAMING_RETENTION_V1 — the floor the element stands on is a
    # separate, equally binding claim: "on the upper floor" places the
    # balcony, while the absence of this clause leaves its level unstated.
    if floors:

        phrase += " on the " + " and ".join(floors)

    if group == "opening":

        kind = "an opening in the building envelope"

    else:

        kind = "a protection / enclosure element, distinct from an opening"

    return (
        "%s include %s, %s; render it visibly."
        % (FEATURE_SENTENCE_PREFIX, phrase, kind)
    )

# A Persian prohibition attached to a verb: "... نکن" / "... نکنید".
_PROHIBITION = re.compile(
    r"(نکن|نکنید|نشه|نشود|نباشه|نباشد|نخواه|do not|don't|dont|never)",
    re.IGNORECASE,
)

# An intent to CREATE (as opposed to refine an existing design).
_CREATE_MARKERS = ("بساز", "بسازید", "طراحی کن", "طراحی کنید", "ایجاد کن",
                   "درست کن", "بزن", "build", "create", "design a",
                   "generate")

# The existing compiler's default opening, which asserts REFINEMENT.
_REFINE_MARKERS = ("refine the architectural design", "preserve the existing")


# ==========================================================
# NUMBER SCAN
# ==========================================================

def _digits_to_int(token: str) -> Optional[int]:
    """Accept ASCII and Persian-Indic digits."""

    mapped = "".join(
        str(_PERSIAN_DIGITS.index(ch)) if ch in _PERSIAN_DIGITS else ch
        for ch in token
    )

    if mapped.isdigit():

        return int(mapped)

    return None


def _numbers(text: str) -> List[Dict[str, Any]]:
    """Every number in the text with its span. Digits outrank words."""

    found: List[Dict[str, Any]] = []

    for match in re.finditer(r"[0-9\u06F0-\u06F9]+", text):

        value = _digits_to_int(match.group(0))

        if value is not None:

            found.append({
                "value": value,
                "start": match.start(),
                "end": match.end(),
                "raw": match.group(0),
                "source": "digits",
            })

    # A hyphen or ZWNJ joins a word-number to its noun in valid forms such as
    # ``Two-storey`` and ``دو‌طبقه``. Treat those characters as token
    # boundaries here; `_adjacent` below remains the single owner of the
    # permitted separator grammar. Case-fold only for lexicon lookup, while
    # preserving the original span/raw token for provenance.
    for match in re.finditer(
        r"[^\s\u200c،,.!؟;:\-\u2010\u2011\u2013\u2014]+",
        text,
    ):

        raw_token = match.group(0)
        token = raw_token.casefold()

        if token in _NUMBER_WORDS:

            found.append({
                "value": _NUMBER_WORDS[token],
                "start": match.start(),
                "end": match.end(),
                "raw": raw_token,
                "source": "word",
            })

    return found


def _adjacent(text: str, index: int, nouns) -> Optional[str]:
    """The noun immediately after ``index``.

    V4.3A — M1 (separator behaviour only): a hyphen is a valid separator, so
    "30-floor" and "30-storey" bind exactly like "30 floor". The V4.2
    sentence-filtering contract in `build_constraint_block` is untouched.

    Separators allowed between the number and its noun: space, ZWNJ, and the
    hyphen family (U+002D, U+2013, U+2014, U+2011). Nothing else.
    """

    tail = text[index:].lstrip(" \u200c-\u2010\u2011\u2013\u2014")

    for noun in nouns:

        if tail.startswith(noun):

            return noun

    return None


def _is_compound_word_tail(text: str, number: Dict[str, Any]) -> bool:
    """Reject an unsupported compound word number instead of truncating it.

    The simple lexicon intentionally does not compose ``twenty-one`` or
    ``twenty one``. Without this guard, the trailing ``one`` would sit next to
    ``storey`` and become an incorrect authoritative value of 1.
    """

    if number.get("source") != "word":

        return False

    prefix = text[:number["start"]].casefold()
    separator = r"[\s\u200c\-\u2010\u2011\u2013\u2014]+"

    direct = re.search(r"([^\W\d_]+)" + separator + r"$", prefix)

    if direct and direct.group(1) in _NUMBER_WORDS:

        return True

    linked = re.search(
        r"([^\W\d_]+)" + separator + r"(?:and|و)" + separator + r"$",
        prefix,
    )

    return bool(linked and linked.group(1) in _NUMBER_WORDS)


def _phrase_immediately_before(
    text: str,
    index: int,
    phrases,
) -> bool:
    """Whether one complete phrase ends immediately before ``index``."""

    prefix = text[:index].casefold()

    for phrase in phrases:

        pattern = re.escape(phrase).replace(r"\ ", r"[\s\u200c]+")

        if re.search(
            r"(?<!\w)" + pattern + r"[\s\u200c]*$",
            prefix,
        ):

            return True

    return False


def _is_non_exact_floor_candidate(
    text: str,
    number: Dict[str, Any],
    numbers: List[Dict[str, Any]],
) -> bool:
    """Reject a floor noun's number when local syntax makes it non-exact.

    The floor grammar binds only the number next to the noun. In an elided
    range such as ``2-4 storeys`` that number is the upper bound, not a total.
    This guard uses only the immediately preceding number and connector, or a
    limit phrase immediately before the candidate, so unrelated hyphens,
    alternatives, and numbers elsewhere in the request remain harmless.
    """

    if _phrase_immediately_before(
        text,
        number["start"],
        _FLOOR_LIMIT_PREFIXES,
    ):

        return True

    previous = [
        item for item in numbers
        if item["end"] <= number["start"] and item is not number
    ]

    if not previous:

        return False

    prior = max(previous, key=lambda item: item["end"])
    connector = text[prior["end"]:number["start"]].casefold()
    spacing = r"[\s\u200c]*"
    range_or_alternative = (
        spacing
        + r"(?:[/]|[-\u2010\u2011\u2013\u2014]"
        + spacing
        + r"(?:(?:to|or|تا|یا)"
        + spacing
        + r")?|(?:to|or|تا|یا|الی))"
        + spacing
    )

    if re.fullmatch(range_or_alternative, connector):

        return True

    if re.fullmatch(spacing + r"(?:and|و)" + spacing, connector):

        return _phrase_immediately_before(
            text,
            prior["start"],
            ("between", "بین"),
        )

    return False


# ==========================================================
# CONSTRAINT EXTRACTION
# ==========================================================

def _floor_count_is_description(text: str, number: Dict[str, Any], end: int) -> bool:
    """True when this floor count states what the building ALREADY IS.

    R1_B_FLOOR_COUNT_DESCRIPTION_REQUEST_V1 — the predicate decides, not the
    number. `سه طبقه است` / `has three storeys` describe the existing
    building; `چهار طبقه کن` / `Make it four storeys` request a new one.

    A predicate is only accepted as a description when it ends on a word
    boundary, so `استفاده` (use) is not mistaken for the copula `است`.
    """

    tail = text[end:].lstrip(" \u200c,،:؛;-.!?\u061f\u00ab\u00bb")

    for marker in _FLOOR_DESCRIPTION_AFTER:

        if not tail.startswith(marker):

            continue

        remainder = tail[len(marker):]

        if not remainder or not remainder[0].isalnum():

            return True

    before = text[:number["start"]].rstrip(" \u200c,،:؛;")

    words = before.replace("\u200c", " ").split()

    if words and words[-1].casefold() in _FLOOR_DESCRIPTION_BEFORE:

        return True

    return False


def _floor_description_is_operative(text: str, rejected_count_seen: bool) -> bool:
    """True when the user's OWN stated count is meant as the requirement.

    A description becomes operative only when the sentence makes it so:

      * an explicit preserve request quotes the existing count
        ("بدون تغییر در تعداد طبقات"), or
      * the user REJECTED another floor value in the same instruction, so the
        affirmed count is the correction ("سه طبقه نیست، چهار طبقه است").

    A bare description ("این ساختمان سه طبقه است") is NOT operative.

    The correction signal is "a floor candidate was dropped because it was
    negated", not `has_contrastive_negation()`: that helper deliberately
    treats a negation followed by a comma as a discourse marker, so
    "نیست، چهار طبقه است" reports no contrast at all.
    """

    lowered = text.casefold()

    if any(marker.casefold() in lowered for marker in _FLOOR_PRESERVE_MARKERS):

        return True

    return bool(rejected_count_seen)


def _floor_span_is_prohibited(text: str, end: int) -> bool:
    """True when an imperative prohibition verb IMMEDIATELY follows the span.

    R1_B_FLOOR_COUNT_DESCRIPTION_REQUEST_V1 — `چهار طبقه نکن` forbids the
    count; it is neither a description nor a request. The check is
    adjacency-only on purpose: `is_prohibited()` reports a whole-clause span,
    which for "سه طبقه نباشد، چهار طبقه کن" covers the second clause too and
    would wrongly forbid the count the user DID ask for.
    """

    tail = text[end:].lstrip(" \u200c,،:؛;-.!?\u061f")

    return any(
        tail.startswith(marker)
        for marker in _IMPERATIVE_PROHIBITION_MARKERS
    )


def _floor_count_candidates(text: str) -> tuple:
    """Every floor-count candidate, split by clause type.

    Returns ``(requested, described, rejected_seen)``. Both lists keep the
    exact span and value the accepted grammar produced; this function only
    classifies. ``rejected_seen`` reports whether a floor candidate was
    dropped because the user negated it, which is the correction signal.
    """

    requested: List[Dict[str, Any]] = []

    described: List[Dict[str, Any]] = []

    rejected_seen = False

    lowered = text.lower()

    numbers = _numbers(text)

    for number in numbers:

        noun = _adjacent(lowered, number["end"], _FLOOR_NOUNS)

        if not noun:

            continue

        if _is_compound_word_tail(text, number):

            continue

        if _is_non_exact_floor_candidate(text, number, numbers):

            continue

        tail = text[number["end"]:]

        separators = len(tail) - len(
            tail.lstrip(" \u200c-\u2010\u2011\u2013\u2014")
        )

        end = number["end"] + separators + len(noun)

        suffix = lowered[end:].lstrip(" \u200c,،:؛;-")

        if any(
            suffix.startswith(marker)
            for marker in _FLOOR_COMPONENT_SUFFIXES
        ):

            continue

        # FLOOR_COUNT_NEGATION_GATE_V1 — a count the user NEGATED is not a
        # requirement. "not a three-storey building" used to publish
        # floors=3 with USER_TEXT/hard_constraint provenance, so the final
        # workflow prompt asserted "exactly 3 floors" while the same turn's
        # prohibition said "Do NOT use or repeat: a three-storey building".
        # The shared negation layer already decides this per marker
        # (`is_affirmed`, the project's only negation authority), so the
        # candidate is dropped instead of a second negation engine being
        # introduced. Distinct remaining values still fail closed below.
        if not is_affirmed(text, text[number["start"]:end]):

            rejected_seen = True

            continue

        # R1_B — "چهار طبقه نکن" forbids the count: neither description nor
        # request.
        if _floor_span_is_prohibited(text, end):

            continue

        candidate = {
            "value": number["value"],
            "noun": noun,
            "raw": text[number["start"]:end],
            "start": number["start"],
            "end": end,
        }

        if _floor_count_is_description(text, number, end):

            described.append(candidate)

        else:

            requested.append(candidate)

    return requested, described, rejected_seen


def _resolve_floor_candidates(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """One unambiguous value, or None. Distinct values fail closed."""

    if not candidates:

        return None

    if len({candidate["value"] for candidate in candidates}) != 1:

        return None

    return candidates[0]


def _floor_count(text: str) -> Optional[Dict[str, Any]]:
    """One unambiguous stated total — number ADJACENT to the floor noun.

    Multiple mentions are accepted only when they agree. Distinct values are
    contradictory/ambiguous and fail closed instead of making the first match
    authoritative.

    R1_B_FLOOR_COUNT_DESCRIPTION_REQUEST_V1 — a count that merely DESCRIBES
    the existing building is not a requested target. It is used only when the
    sentence makes it operative (a preserve request, or a contrastive
    correction). This is what lets
    "ساختمان سه طبقه است، آن را چهار طبقه کن" publish 4 instead of failing
    closed on two competing numbers, and what stops
    "این ساختمان سه طبقه است" from publishing 3 as a hard requirement.
    """

    requested, described, rejected_seen = _floor_count_candidates(text)

    operative = list(requested)

    if described and _floor_description_is_operative(text, rejected_seen):

        operative.extend(described)

    return _resolve_floor_candidates(operative)


def requested_floor_count(text: str) -> Optional[Dict[str, Any]]:
    """PUBLIC read-only alias of the single floor-count authority.

    T2I_HIGH_RISE_SUBJECT_FIDELITY_V1 — the prompt compiler needs the
    VALIDATED requested count to build a count-bearing subject phrase. It must
    not re-implement the floor grammar, so this exposes the existing
    `_floor_count` contract instead: the same `is_affirmed` negation gate, the
    same description/request split and the same fail-closed conflict
    behaviour. Nothing here changes that behaviour.

    Returns the accepted candidate dict (``value``, ``noun``, ``raw``,
    ``start``, ``end``) or ``None``. A negated, merely descriptive or
    preservation-only count yields ``None``.
    """

    return _floor_count(text)


def _floor_count_description(text: str) -> Optional[Dict[str, Any]]:
    """The count the user stated about the EXISTING building, or None.

    Reported separately so a description is never confused with a requested
    target. Never sourced from vision — this is USER_TEXT only.
    """

    _requested, described, _rejected = _floor_count_candidates(text)

    return _resolve_floor_candidates(described)


def _dimensions(text: str) -> List[Dict[str, Any]]:
    """Every stated dimension — number ADJACENT to a unit."""

    out: List[Dict[str, Any]] = []

    for number in _numbers(text):

        unit = _adjacent(text, number["end"], _AREA_UNITS)

        kind = "area"

        if not unit:

            unit = _adjacent(text, number["end"], _LENGTH_UNITS)

            kind = "length"

        if unit:

            out.append({
                "value": number["value"],
                "unit": unit,
                "kind": kind,
                "raw": number["raw"] + " " + unit,
                "start": number["start"],
                "end": number["end"] + len(unit),
            })

    return out


def _split_by_rejection(text: str, dimensions: List[Dict[str, Any]]) -> tuple:
    """Partition dimensions into AFFIRMED and REJECTED.

    "اتاق ۱۲ متره، نه ۱۰ متر" states two values and rejects the second. Only
    the affirmed value may become a requirement; emitting the rejected one
    would invert the user's correction.
    """

    rejected = rejected_span(text)

    if not rejected:

        return dimensions, []

    offset = text.rfind(rejected)

    if offset < 0:

        return dimensions, []

    affirmed: List[Dict[str, Any]] = []

    denied: List[Dict[str, Any]] = []

    for item in dimensions:

        (denied if item["start"] >= offset else affirmed).append(item)

    return affirmed, denied


def _geometry(text: str, understanding: Dict[str, Any]) -> Dict[str, Any]:
    """Geometry constraints: explicit wording plus the understanding flags.

    FACADE-04D.3C-9P-A — `preserve_floor_count` is reported when the user
    explicitly asked to keep the existing floor count (e.g. "بدون تغییر در
    تعداد طبقات"), which does NOT require the user to state a numeral. The
    VALUE is anchored to IMAGE B, never to IMAGE A (see `_reference_ab_section`
    and `floor_count_provenance`).
    """

    markers = [m for m in _GEOMETRY_MARKERS if m in text]

    preserve = (understanding or {}).get("preserve_constraints") or {}

    return {
        "markers": markers,
        "preserve_geometry": bool(preserve.get("geometry")),
        "preserve_massing": bool(preserve.get("massing")),
        "preserve_floor_count": bool(preserve.get("floor_count")),
    }


def _openings(text: str, understanding: Dict[str, Any]) -> Dict[str, Any]:
    """Opening constraints: what the user said about windows/doors.

    FACADE-04D.3C-9P-A — two additive, backward-compatible fields distinguish
    POSITION preservation from a generic "openings mentioned":

        preserve_window_positions   the user asked to keep window POSITIONS
        preserve_opening_positions  the user asked to keep opening POSITIONS

    They are true only when the understanding layer recognised an explicit
    preservation of window/opening position. A bare mention of "پنجره" is
    never enough (see `_no_change_clause_fields` upstream).
    """

    nouns = [n for n in _OPENING_NOUNS if n in text]

    verbs = [v for v in _OPENING_CHANGE_VERBS if v in text]

    preserve = (understanding or {}).get("preserve_constraints") or {}

    preserve_windows = bool(preserve.get("windows"))

    preserve_openings = bool(preserve.get("openings"))

    return {
        "nouns": nouns,
        "verbs": verbs,
        "preserve_windows": preserve_windows,
        "preserve_openings": preserve_openings,
        "preserve_window_positions": preserve_windows,
        "preserve_opening_positions": preserve_openings,
        "mentioned": bool(nouns),
    }


def _camera(terminology: Dict[str, Any], source: Any = None) -> List[str]:
    """Camera / view terms, taken from the shared terminology layer.

    EXISTING_CAMERA_INSTRUCTION_HANDOFF_FIX_V1 — a term the user REJECTED is
    not a camera requirement. The terminology extractor drops English
    negations itself, but it does not recognise Persian trailing prohibitions,
    so «نمای روبرو نکن» still produced `frontal view`. The decision is taken
    from the shared negation layer (`is_prohibited`, the project's only
    prohibition authority) rather than a second parser.
    """

    matched = terminology.get("matched") or []

    terms = []

    for item in matched:

        if item.get("family") != "camera":

            continue

        canonical = item.get("canonical")

        if not canonical:

            continue

        evidence = item.get("evidence") or canonical

        if source is not None and is_prohibited(source, evidence):

            continue

        if canonical not in terms:

            terms.append(canonical)

    return terms


#: Contrastive markers that introduce the user's AFFIRMED replacement
#: ("not X, but Y" / "نه X بلکه Y"). They end the negated requirement. The
#: definition lives in the shared negation layer so the prohibition here and
#: the material rejection in the knowledge resolver cannot drift apart.
def _negated_requirement(span: str) -> str:
    """The negated requirement only — never the affirmed replacement.

    ARCHITECTURAL_NEGATION_OUTPUT_CONSISTENCY_V1 — the shared negation layer
    returns the whole sentence tail after the last negation word, so
    "not a three-storey building, but a four-storey one" produced
    "Do NOT use or repeat: a three-storey building, but a four-storey one."
    The prohibition then contained the user's own affirmative replacement and
    contradicted the positive constraint emitted in the same prompt.

    The negated requirement ends where the replacement is introduced. The
    negation decision and the boundary both come from the shared negation
    layer; no second negation engine and no architectural vocabulary is added.
    """

    return trim_replacement_span(span)


def _prohibited_content(text: str) -> list:
    """The OBJECTS a shared leading/trailing prohibition actually rejects.

    LIVE_RENDER_FIDELITY_HANDOFF_FIX_V1 — the prohibition evidence used to be
    the MARKER ONLY ("نکن"), so the instruction said
    "Respect the user's prohibition (نکن)." and lost WHAT was prohibited: a
    meta-statement about a prohibition is not a prohibition.

    The clause comes from the shared negation layer
    (``trailing_prohibition_spans``), the SAME evidence the space and material
    guards already use. The trailing prohibition marker and its ADD verb are
    removed so only the rejected objects remain. No second negation parser and
    no architectural vocabulary is added.
    """

    contents = []

    for start, end in prohibition_spans(text):

        clause = str(text[start:end] or "").strip(" .،,;؛")

        if not clause:

            continue

        # Cut at the prohibition marker: everything before it is what the user
        # rejects, everything after it is the prohibition itself.
        cut = len(clause)

        for match in _PROHIBITION.finditer(clause):

            cut = min(cut, match.start())

        head = clause[:cut].strip(" .،,;؛")

        # Drop a trailing ADD verb ("... اضافه نکن" -> "...").
        tokens = head.split()

        while tokens and tokens[-1] in _FEATURE_ADD_VERBS:

            tokens.pop()

        head = " ".join(tokens).strip(" .،,;؛")

        if head and head not in contents:

            contents.append(head)

    return contents


def _negations(text: str) -> Dict[str, Any]:
    """Negation and correction evidence, from the shared negation layer."""

    prohibitions = [m.group(0) for m in _PROHIBITION.finditer(text)]

    return {
        "has_contrastive_negation": bool(has_contrastive_negation(text)),
        "rejected_span": _negated_requirement(rejected_span(text)),
        "prohibitions": prohibitions,
        "prohibited_content": _prohibited_content(text),
        "is_negated": bool(prohibitions) or bool(has_contrastive_negation(text)),
    }


def _intent(text: str) -> str:
    """CREATE when the user asks for a new design, else REFINE."""

    lowered = text.lower()

    for marker in _CREATE_MARKERS:

        if marker in lowered:

            return "CREATE"

    return "REFINE"


# ==========================================================
# ENGLISH INSTRUCTION ASSEMBLY
# ==========================================================

def _normalise_intent_opening(base: str, intent: str) -> str:
    """Stop a CREATE request from carrying the compiler's REFINE opener.

    The canonical compiler always opens with "Refine the architectural
    design." That is correct for an edit and WRONG for a request that asks
    for a new design — it reverses the user's intent. This is a deterministic
    one-sentence substitution, not a rewrite of the compiled prompt.
    """

    if intent != "CREATE":

        return base

    for marker in _REFINE_MARKERS:

        position = base.lower().find(marker)

        if position == 0:

            base = base[len(marker):].lstrip(" .")

            break

        if position > 0:

            base = (base[:position] + base[position + len(marker):]).strip()

            break

    return base


# FACADE-04A.1 — the terminology augmenter appends its terms with ", " even
# when the compiled prompt already ended with a sentence period, producing a
# malformed fragment such as "... geometry template., material, style". This
# rewrites that tail as a clean sentence. It is a display/assembly fix only —
# no terminology is added or dropped.
_TERMINOLOGY_TAIL = re.compile(r"([.!?])\s*,\s*([^.!?]+?)\s*$")


def _normalise_terminology_tail(text: str) -> str:

    value = str(text or "")

    match = _TERMINOLOGY_TAIL.search(value)

    if not match:

        return value

    head = value[: match.start(1) + 1].strip()

    tail = match.group(2).strip().strip(",").strip()

    if not tail:

        return head

    return head + " Terminology: " + tail + "."


def _constraint_sentences(
    floors: Optional[Dict[str, Any]],
    dimensions: List[Dict[str, Any]],
    openings: Dict[str, Any],
    geometry: Dict[str, Any],
    camera: List[str],
    negations: Dict[str, Any],
    intent: str,
    facade_restyle: bool = False,
    target_floor_count: Any = None,
    feature_requirements: Optional[List[Dict[str, Any]]] = None,
    whole_building_visibility: bool = False,
    floor_count_framing: Any = None,
    tall_tower: bool = False,
    existing_facade_redesign: bool = False,
) -> List[str]:
    """Deterministic English sentences carrying the extracted constraints.

    FACADE-04A.1 — ``facade_restyle`` marks a request that restyles the FACADE
    of an existing target building against a style reference (IMAGE A). Such a
    request must NOT be phrased as "create a new architectural design": that
    contradicts preserving the target building's geometry. It is a facade
    redesign — re-cladding and facade restyling — of the SAME building.

    FACADE-04D.3C-9P-A — ``target_floor_count`` is the floor count OBSERVED on
    the target building (IMAGE B). It is used ONLY to phrase a floor-count
    PRESERVATION clause; it is never a user-stated hard number and never taken
    from IMAGE A.

    T2I_ARCHITECTURAL_FEATURE_HANDOFF_V1 — ``feature_requirements`` are the
    architectural elements the user explicitly asked to exist. They are emitted
    as their own sentences; every other group keeps its existing wording and
    relative order, so a request that carries no feature requirement is
    byte-identical to the previous behaviour.
    """

    lines: List[str] = []

    if facade_restyle:

        lines.append(
            "Redesign the FACADE of the existing target building (facade "
            "restyling / re-cladding) — do NOT create or reconstruct a new "
            "building and do NOT change its massing, floor structure or "
            "opening layout."
        )

    elif intent == "CREATE" and not existing_facade_redesign:

        lines.append("Create a new architectural design (not a refinement).")

    # NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1 — MEASURED CONTRADICTION.
    #
    # A facade design for an EXISTING building was classified CREATE, so the
    # prompt said both
    #
    #   "Create a new architectural design (not a refinement)."
    #   "Preserve the existing building geometry."
    #
    # A model cannot satisfy both: the first asks for a new building, the
    # second asks to keep the old one. The request is neither a new build nor
    # a refinement — it is a NEW FACADE TREATMENT ON THE EXISTING BUILDING, so
    # that is what it now says. The distinction is gated on a real style, a
    # facade target and a reference to the building as already existing; a
    # genuine new-build request keeps the original CREATE wording.
    elif existing_facade_redesign:

        lines.append(
            "Design a new facade treatment for the EXISTING building, "
            "preserving its primary geometry and architectural identity — "
            "do NOT replace the building and do NOT add storeys, structural "
            "bays, window openings or building volumes."
        )

    # T2I_ARCHITECTURAL_FEATURE_HANDOFF_V1 — the user's explicitly requested
    # architectural features (doors/windows = openings; railings/balustrades/
    # parapets = protection elements). Emitted FIRST, because this is the
    # user's own ask and the measured defect was that it never reached the
    # sampler at all. Nothing is emitted when the request asked for no
    # feature, so every other request is byte-identical to before.
    for requirement in feature_requirements or []:

        lines.append(_feature_sentence(requirement))

    if floors:

        lines.append(
            "The building has exactly %d floors." % floors["value"]
        )

    if dimensions:

        for item in dimensions:

            label = "area" if item["kind"] == "area" else "dimension"

            lines.append(
                "Required %s: %d %s." % (
                    label,
                    item["value"],
                    _UNIT_EN.get(item["unit"], item["unit"]),
                )
            )

    # FACADE-04D.3C-9P-A — explicit POSITION preservation. Phrased so the
    # fidelity gate can verify the span ("window positions" / "opening
    # positions") and the polarity (keep / unchanged).
    if openings.get("preserve_window_positions"):

        lines.append(
            "Keep the existing window positions unchanged; do NOT move or "
            "relocate the windows."
        )

    elif openings.get("preserve_windows"):

        lines.append(
            "Keep the existing window positions, sizes and opening layout."
        )

    if openings.get("preserve_opening_positions"):

        lines.append(
            "Keep the existing opening positions unchanged; do NOT move or "
            "relocate the openings."
        )

    elif openings.get("preserve_openings"):

        lines.append("Keep the existing opening layout.")

    # FACADE-04D.3C-9P-A — floor-count preservation. The user does NOT need to
    # state a numeral: "بدون تغییر در تعداد طبقات" preserves whatever the
    # TARGET BUILDING (IMAGE B) actually has. When B is unavailable the value
    # is left unstated and the gate stays fail-closed (see `_geometry`).
    if geometry.get("preserve_floor_count"):

        if target_floor_count is not None:

            lines.append(
                "Keep the target building's existing floor count unchanged "
                "(%d floor(s)); do NOT add or remove floors."
                % target_floor_count
            )

        else:

            lines.append(
                "Keep the target building's existing floor count unchanged; "
                "do NOT add or remove floors."
            )

    if negations.get("rejected_span"):

        lines.append(
            "Do NOT use or repeat: %s." % negations["rejected_span"]
        )

    # LIVE_RENDER_FIDELITY_HANDOFF_FIX_V1 — the CONTENT of a trailing Persian
    # prohibition, not its marker. "Respect the user's prohibition (نکن)" told
    # the renderer that a prohibition existed but never WHAT it forbade, and
    # the semantic fidelity gate correctly refused to call that preservation.
    # The sentence states the rejected objects explicitly and in the negative
    # form this contract already uses ("Do NOT use or repeat: ..."), so a
    # rejection is never phrased as a positive design instruction.
    _prohibited_content = negations.get("prohibited_content") or []

    for content in _prohibited_content:

        lines.append("Do NOT include: %s." % content)

    if not _prohibited_content:

        for prohibition in negations.get("prohibitions") or []:

            lines.append("Respect the user's prohibition (%s)." % prohibition)

    if geometry.get("preserve_geometry"):

        lines.append("Preserve the existing geometry exactly.")

    if geometry.get("preserve_massing"):

        lines.append("Preserve the existing massing exactly.")

    if camera:

        lines.append("Camera / view: " + ", ".join(camera) + ".")

    # SPATIAL_FRAMING_RETENTION_V1 — the user's explicit whole-building
    # framing. Emitted AFTER the feature sentences (so the elements keep
    # priority in the bounded block) and ONLY when the request stated both a
    # whole-building noun and a view word in one clause; nothing is added for
    # a request that never asked to see the whole building.
    if whole_building_visibility:

        lines.append(WHOLE_BUILDING_FRAMING_SENTENCE)

    # WHOLE_BUILDING_VISUAL_VERIFIABILITY_V1 — an EXACT user-stated floor count
    # is only satisfied by a view in which the storeys can be counted. Emitted
    # only when `_floor_count_framing` says the request grounds it, so a
    # request without an exact count, a single-storey request and an explicit
    # close-up request are all unchanged.
    if isinstance(floor_count_framing, int) and floor_count_framing >= 2:

        # T2I_FULL_TOWER_CAMERA_FRAMING_V1 — a grounded tall tower gets the
        # margin-explicit long shot; every other exact-count request keeps the
        # existing sentence unchanged.
        if tall_tower:

            lines.append(
                WHOLE_BUILDING_TOWER_FRAMING_SENTENCE % floor_count_framing
            )

        else:

            lines.append(
                WHOLE_BUILDING_COUNT_FRAMING_SENTENCE % floor_count_framing
            )

    return lines


def _reference_roles(references: Any) -> Dict[str, Any]:
    """Assign the fixed roles: A = facade reference, B = target building."""

    supplied = references if isinstance(references, dict) else {}

    def _present(key):

        value = supplied.get(key)

        return bool(value)

    return {
        IMAGE_A: {
            "role": ROLE_FACADE_REFERENCE,
            "present": _present(IMAGE_A) or _present(IMAGE_A.lower()),
            "authority": "appearance_only",
        },
        IMAGE_B: {
            "role": ROLE_TARGET_BUILDING,
            "present": _present(IMAGE_B) or _present(IMAGE_B.lower()),
            "authority": "geometry",
        },
        "facade_reference_may_change": (
            "materials", "style", "colour", "ornament", "lighting",
        ),
        "target_building_may_change": (
            "materials", "style", "colour", "ornament", "lighting",
        ),
        "geometry_authority": ROLE_TARGET_BUILDING,
    }


# ==========================================================
# FACADE-04A — GROUNDED A/B RENDER-INSTRUCTION SECTION
#
# IMAGE A = facade style reference  -> APPEARANCE ONLY (style, colours,
#   materials, ornament, decorative vocabulary).
# IMAGE B = target building         -> GEOMETRY AUTHORITY (massing, floor
#   levels, openings, balconies, roof geometry, camera viewpoint).
#
# Every value is reported as the MODEL'S OBSERVATION (unverified). A value the
# analysis does not carry is omitted, never guessed. No UNKNOWN or INFERRED
# value is ever promoted to a hard constraint — the hard constraints below are
# pure geometry-PRESERVATION rules that hold regardless of any uncertain value.
# ==========================================================

# FACADE-04A.1 — vocabulary that is TRANSFERABLE from the style reference
# (IMAGE A) and vocabulary that is NOT. A may contribute style, colours,
# material appearance, ornament and compatible facade details. A must NEVER
# contribute its dome, roof massing, floor count, building silhouette,
# opening positions or balconies as TARGET geometry.
_NON_TRANSFERABLE_FROM_A = (
    "dome", "roof", "mansard", "silhouette", "massing", "floor", "floors",
    "storey", "storeys", "story", "stories", "level", "levels",
    "balcony", "balconies", "opening", "openings", "window position",
    "plan", "layout", "گنبد", "بام", "سقف", "طبقه", "بالکن", "پلان",
)


def _transferable_from_a(labels: List[str]) -> List[str]:

    kept = []

    for label in labels or []:

        lowered = str(label or "").lower()

        if any(term in lowered for term in _NON_TRANSFERABLE_FROM_A):

            continue

        if label not in kept:

            kept.append(label)

    return kept


# ==========================================================
# FACADE-04D.3C-9P-B1 — USER CONFIRMATION VALIDATION
#
# A user-geometry confirmation is accepted ONLY when it is structurally
# valid. Anything ambiguous, malformed or non-user-originated is rejected
# and the caller falls back to the unverified Vision observation — a
# confirmation is never fabricated.
# ==========================================================

# Fields a caller may use to assert the confirmation ORIGIN. Only
# "user" is accepted; assistant/model/session text is not user-originated.
#
# FACADE-04D.3C-9P-B12 — the origin is now MANDATORY. A carrier that omits it
# is untrusted: an arbitrary dictionary that merely looks like a count is NOT
# evidence of user authorship. The origin must be established by a trusted
# server-side boundary (see `chat_architect._trusted_user_geometry`).
_USER_CONFIRMATION_ORIGINS = ("user", "user_confirmation", "user_message")


def _valid_user_geometry(user_geometry: Any) -> Optional[Dict[str, Any]]:
    """Return a normalised confirmation, or None when it is not trustworthy.

    FACADE-04D.3C-9P-B1 — fail-safe: a malformed, empty or non-user-originated
    carrier yields None (never a fabricated confirmation).

    FACADE-04D.3C-9P-B12 — the origin field is REQUIRED. A carrier with no
    origin (e.g. ``{"storey_count": 3}``) is rejected: this validator cannot
    itself prove authorship, so it refuses to promote an originless value.
    """

    if not isinstance(user_geometry, dict):

        return None

    # Origin is MANDATORY and must be explicitly user-originated. A missing
    # origin is treated exactly like a stated non-user origin: rejected.
    origin = user_geometry.get("origin") or user_geometry.get("source_kind")

    if origin is None or str(origin).strip().lower() not in _USER_CONFIRMATION_ORIGINS:

        return None

    count = user_geometry.get("storey_count")

    if count is None:

        count = user_geometry.get("floor_count")

    if isinstance(count, bool) or not isinstance(count, int):

        return None

    if count < 1:

        return None

    scope = user_geometry.get("storeys") or user_geometry.get("confirmed_scope")

    scope_out = None

    if isinstance(scope, (list, tuple)):

        scope_out = [str(item) for item in scope]

    # a declared scope that disagrees with the count is malformed
    if scope_out is not None and len(scope_out) != count:

        return None

    return {
        "value": count,
        "source": "USER_CONFIRMATION",
        "hard_constraint": True,
        "confirmed_scope": scope_out,
    }


# ==========================================================
# FACADE-04D.3C-9P-B12 — TRUSTED USER-MESSAGE GEOMETRY EXTRACTION
#
# The ONLY way a USER_CONFIRMATION may be produced: scan messages that a
# trusted caller has ALREADY established as user-authored, and accept a
# confirmation only when the message is EXPLICIT and the number is ADJACENT
# to the floor noun. An ordinary design sentence that happens to contain a
# numeral never becomes a geometry confirmation.
# ==========================================================

# An EXPLICIT, self-standing statement of how many storeys the building has.
# Deliberately narrow: the phrase must assert a count about the building.
_USER_ASSERTION_MARKERS_FA = (
    "طبقه دارد", "طبقه داره", "طبقه است", "طبقه هست",
    "طبقات دارد", "طبقات داره", "تعداد طبقات",
)
_USER_ASSERTION_MARKERS_EN = (
    "has", "have", "is", "are", "consists of", "with",
)

# FACADE-04D.3C-9P-B12 — markers that a count is being asserted about a
# DIFFERENT building. A neighbour/adjoining/other building's storey count must
# never bind to the current target (IMAGE B).
_OTHER_BUILDING_MARKERS = (
    "همسایه", "مجاور", "کناری", "ساختمان دیگر", "بنای دیگر", "آن ساختمان",
    "ساختمان بعدی", "neighbou", "neighbor", "adjacent", "next building",
    "other building", "another building",
    "این ساختمان", "این بنا", "همین ساختمان", "همین بنا", "این نما",
)


def _asserts_current_building(text: str) -> bool:
    """True when the explicit count is about the CURRENT target building.

    A message that explicitly names a different building (a neighbour, an
    adjacent or "other" building) is rejected even when its count is explicit,
    so a foreign building's storey count never binds to IMAGE B.
    """

    lowered = (text or "").lower()

    for marker in _OTHER_BUILDING_MARKERS:

        if marker in text or marker in lowered:

            # "این ساختمان / این بنا / این نما" are SELF references, not other
            # buildings — only accept those as current-building anchors.
            if marker in ("این ساختمان", "این بنا", "همین ساختمان",
                          "همین بنا", "این نما"):

                continue

            return False

    return True



def user_geometry_from_messages(messages: Any) -> Optional[Dict[str, Any]]:
    """Derive a trustworthy confirmation from USER-AUTHORED messages.

    ``messages`` must already be filtered by a trusted boundary — this helper
    never inspects roles itself beyond a defensive re-check. It returns the
    LATEST explicit floor-count assertion (so a later user correction wins),
    or None when no message states an unambiguous count.

    Fail-safe: an unrelated numeral, an implicit phrase, or a malformed value
    yields None. The raw Vision observation is never touched here.
    """

    if not isinstance(messages, (list, tuple)):

        return None

    candidate = None

    for message in messages:

        if not isinstance(message, dict):

            continue

        # defensive re-check — only user-authored turns are ever considered
        role = str(message.get("role") or "").strip().lower()

        if role not in ("user", "user_confirmation", "user_message"):

            continue

        text = message.get("text")

        if not isinstance(text, str) or not text.strip():

            continue

        floors = _floor_count(text)

        if not floors:

            continue

        # EXPLICITNESS — the count must be asserted about the building, not
        # merely mentioned. Require an assertion marker in the SAME message.
        lowered = text.lower()

        explicit = any(
            marker in text for marker in _USER_ASSERTION_MARKERS_FA
        ) or any(
            marker in lowered for marker in _USER_ASSERTION_MARKERS_EN
        )

        if not explicit:

            continue

        # TARGET BUILDING — a count about a DIFFERENT building (neighbour,
        # adjacent, "other") is never promoted to the current target.
        if not _asserts_current_building(text):

            continue

        # LATEST explicit assertion wins — a later correction supersedes an
        # earlier one, so we keep scanning and overwrite.
        candidate = {
            "origin": "user",
            "storey_count": floors["value"],
        }

    if candidate is None:

        return None

    # Route through the SAME structural validator every other carrier uses.
    if _valid_user_geometry(candidate) is None:

        return None

    return candidate


# ==========================================================
# FACADE_RENDER_INSTRUCTION_AUTHORITY_V2 — ONE ROLE VOCABULARY
#
# MEASURED DEFECT: the final model prompt carried two incompatible definitions
# of the same label. The user's own request opens with
#
#     "IMAGE A — TARGET BUILDING (geometry authority) …"
#
# while this module emitted
#
#     "Do NOT copy the style reference's (IMAGE A) massing …"
#     "Keep the target building's (IMAGE B) massing …"
#
# because the PRODUCT keys are the inverse of the test pack's letters
# (product A = style reference -> node 302, product B = target -> node 300).
# A model reading both sentences cannot know which image is the geometry
# authority.
#
# The model text now uses SEMANTIC roles only, plus one sentence that states
# the mapping once. The physical bindings are untouched: node 300 still
# receives the target building and node 302 the style reference.
# ==========================================================

DUAL_IMAGE_ROLE_BLOCK = (
    "Role mapping (authoritative, use these names): "
    "TARGET_BUILDING is the original building being redesigned — it is the "
    "geometry authority and the only source of massing, floors, openings, "
    "balconies, roof and camera. "
    "STYLE_REFERENCE is the supplied reference facade — it is an appearance "
    "reference ONLY (material, colour, surface rhythm, decorative language) "
    "and carries no geometry authority. "
    "Where the user's own wording uses image letters, those letters are the "
    "user's naming, not the product's; the semantic roles above are what bind.",
    "Do NOT copy the STYLE_REFERENCE's massing, floor count, dome, roof "
    "configuration, openings or balconies into the TARGET_BUILDING.",
    "Keep the TARGET_BUILDING's massing, floor levels, openings, balconies, "
    "roof geometry and camera viewpoint unchanged.",
    # SITE_OBJECT_CLASSIFICATION_V1 — the acceptance criteria stated as a
    # constraint, so a worksite object can never be promoted into ornament and
    # a permanent element is never deleted because equipment overlaps it.
    "Temporary construction objects (scaffolding, platforms, debris, signage, "
    "worksite equipment) are never architectural features: do not render "
    "scaffolding as columns, debris as landscaping or signage as facade "
    "ornament. Do not remove a permanent architectural element because "
    "construction equipment overlaps it.",
)


def dual_image_role_block() -> List[str]:
    """The dual-image role constraints, with semantic role names only."""

    return list(DUAL_IMAGE_ROLE_BLOCK)


def _reference_ab_section(reference_analysis_ab: Any,
                          source_floor_count: Any = None,
                          confirmed_floor_count: Any = None,
                          source_text: Any = None) -> Dict[str, Any]:

    if not isinstance(reference_analysis_ab, dict):

        return {"present": False, "a_analyzed": False, "b_analyzed": False,
                "roles": {}, "lines": [], "hard_constraints": [],
                "floor_count_conflict": None}

    a = reference_analysis_ab.get("A")
    b = reference_analysis_ab.get("B")

    a = a if isinstance(a, dict) else {}
    b = b if isinstance(b, dict) else {}

    roles = reference_analysis_ab.get("roles")
    roles = roles if isinstance(roles, dict) else {}

    def _ok(analysis):

        return bool(analysis) and analysis.get("analysis_status") not in (
            None, "PROVIDER_UNAVAILABLE", "FAILED",
        )

    def _labels(value):

        out = []

        for item in (value or []):

            if isinstance(item, dict):

                text = (item.get("style") or item.get("type")
                        or item.get("label") or item.get("name"))

            else:

                text = item

            text = " ".join(str(text or "").split())

            if text and text not in out:

                out.append(text)

        return out

    a_ok, b_ok = _ok(a), _ok(b)

    lines: list = []

    if a_ok:

        style = _labels(a.get("style_candidates")) or (
            [a.get("facade_style")] if a.get("facade_style") else []
        )

        bits = []

        if style:
            bits.append("style " + ", ".join(style[:3]))
        if _labels(a.get("color_palette")):
            bits.append("colours " + ", ".join(_labels(a.get("color_palette"))[:6]))
        if _labels(a.get("materials")):
            bits.append("materials " + ", ".join(_labels(a.get("materials"))[:6]))
        if a.get("ornament_level"):
            bits.append("ornament level " + str(a.get("ornament_level")))

        # FACADE-04A.1 — only TRANSFERABLE facade detail vocabulary is taken
        # from IMAGE A. Its dome / roof / floor count / balcony / opening
        # vocabulary is filtered out and can never reach the target building.
        a_decorative = _transferable_from_a(_labels(a.get("classical_features")))

        if a_decorative:
            bits.append("decorative vocabulary " + ", ".join(a_decorative[:6]))

        if bits:

            lines.append(
                "Take the facade APPEARANCE from the STYLE_REFERENCE "
                "(appearance only), as observed by the model (unverified): "
                + "; ".join(bits) + "."
            )

    if b_ok:

        windows = b.get("windows") if isinstance(b.get("windows"), dict) else {}
        balconies = b.get("balconies") if isinstance(b.get("balconies"), dict) else {}

        bits = []

        if isinstance(b.get("visible_floor_count"), int):
            bits.append("%d visible floor level(s)" % b.get("visible_floor_count"))
        if b.get("symmetry"):
            bits.append("symmetry " + str(b.get("symmetry")))
        if windows.get("rhythm"):
            bits.append("window rhythm " + str(windows.get("rhythm")))
        if balconies.get("present") is not None:
            bits.append("balconies " + ("present" if balconies.get("present") else "absent"))
        if _labels(b.get("roof_features")):
            bits.append("roof " + ", ".join(_labels(b.get("roof_features"))[:3]))

        # ==================================================
        # CURVED_GEOMETRY_PRESERVATION_V1
        #
        # MEASURED DEFECT (V4 §6): the instruction asserted ELEMENT PRESENCE
        # ("balconies present") and never SHAPE. The conditioned output then
        # reported `balconies: false` and a "flat roofline" — the curved slab
        # and the curved parapet were straightened away while the scaffolding
        # survived.
        #
        # This carries the SHAPE the target analysis actually reported. It is
        # a semantic constraint, not a geometric guarantee: nothing in the
        # current conditioned graph measures curvature, so the instruction can
        # ask for preservation but cannot prove it. That is why the acceptance
        # verdict for curved geometry stays PARTIALLY ACCEPTED until a render
        # is measured.
        # ==================================================

        _shape_pool = " ".join(
            _labels(b.get("roof_features"))
            + _labels(b.get("balcony_language"))
            + [str((b.get("balconies") or {}).get("type") or "")]
            + _labels(b.get("arches"))
        ).lower()

        _curved = [
            token for token in ("curved", "curve", "wave", "waved", "sweeping")
            if token in _shape_pool
        ]

        if _curved:

            bits.append("CURVED forms reported by the analysis")

            lines.append(
                "The target building has CURVED architectural forms. Preserve "
                "their curvature exactly: keep the curved balcony slab edges, "
                "the curved parapets and the arch profiles as drawn. Do not "
                "straighten, flatten, square off or replace a curved edge with "
                "a straight one, and do not substitute a different classical "
                "detail for a curved element."
            )

        if bits:

            lines.append(
                "Preserve the TARGET_BUILDING (geometry authority) "
                "exactly as observed: " + "; ".join(bits) + "."
            )

    hard_constraints: list = []

    # ==================================================
    # SITE_OBJECT_CLASSIFICATION_V1 — PERMANENT ARCHITECTURE vs WORKSITE
    #
    # MEASURED DEFECT (V4 §6): vision reported
    # `occlusions: ["scaffolding", "debris"]`, and NOTHING consumed it —
    # not this section, not the fidelity gate, not any module in `core/`.
    # The conditioned output therefore kept the scaffolding and signage
    # while losing the curved balconies: the instruction never said which
    # observed objects were architecture.
    #
    # The classification is a lexical projection over strings vision already
    # reported. It opens no image and adds no detector. Removal is authorised
    # ONLY by an explicit request for the finished building; an ambiguous
    # request keeps the objects exactly as observed.
    # ==================================================

    site_classification: Dict[str, Any] = {}

    if b_ok:

        from core.vision.site_object_classification_v1 import (
            classify_site_objects,
            request_wants_finished_building,
        )

        site_classification = classify_site_objects(b)

        temporary = [
            entry["phrase"] for entry in site_classification["temporary_objects"]
        ]

        if temporary:

            finished, marker = request_wants_finished_building(source_text)

            site_classification["finished_request"] = finished
            site_classification["intent_evidence"] = marker

            lines.append(
                "Reported TEMPORARY construction objects on the target "
                "building (not architecture): " + "; ".join(temporary[:6]) + "."
            )

            if finished:

                lines.append(
                    "The request asks for the FINISHED building, so do not "
                    "reproduce these temporary construction objects in the render."
                )

            else:

                lines.append(
                    "The request does not ask for the finished building, so leave "
                    "these objects as observed: do not remove them, and do not "
                    "reinterpret them as architectural features."
                )

    # FACADE-04A — a conflict between the requested floor count and the floor
    # count OBSERVED on the target building (IMAGE B) is reported, never
    # silently resolved. It stays a SOFT signal: an uncertain visual count is
    # never promoted to a hard geometric constraint.
    #
    # `_floor_count` returns a structured slot ({value, noun, raw, ...}), so
    # the requested count is normalised to its numeric value here.
    floor_count_conflict = None

    # FACADE-04D.3C-9P-B1 — the highest-authority USER value is the current
    # request's numeral when present, else a genuine USER_CONFIRMATION. Both
    # outrank the raw Vision observation. A disagreement with IMAGE B is
    # REPORTED, never silently resolved.
    requested_floor_count = source_floor_count

    if isinstance(requested_floor_count, dict):
        requested_floor_count = requested_floor_count.get("value")

    if not isinstance(requested_floor_count, int) and isinstance(
        confirmed_floor_count, int
    ):

        requested_floor_count = confirmed_floor_count

    if (b_ok and isinstance(b.get("visible_floor_count"), int)
            and isinstance(requested_floor_count, int)
            and requested_floor_count != b.get("visible_floor_count")):

        floor_count_conflict = {
            "requested_floor_count": requested_floor_count,
            "target_building_observed_floor_count": b.get("visible_floor_count"),
            "certainty": "OBSERVED_BY_MODEL_UNVERIFIED",
        }

        lines.append(
            "Note: the TARGET_BUILDING shows "
            + str(b.get("visible_floor_count"))
            + " visible floor level(s), which differs from the requested "
            + str(requested_floor_count)
            + " floor(s); this conflict must be resolved before rendering."
        )

    if a_ok and b_ok:

        hard_constraints = list(dual_image_role_block())

        lines.extend(hard_constraints)

    return {
        "present": bool(a_ok and b_ok),
        "a_analyzed": a_ok,
        "b_analyzed": b_ok,
        "roles": roles or {
            "A": ROLE_FACADE_REFERENCE,
            "B": ROLE_TARGET_BUILDING,
            "geometry_authority": ROLE_TARGET_BUILDING,
        },
        "lines": lines,
        "hard_constraints": hard_constraints,
        "floor_count_conflict": floor_count_conflict,
        # SITE_OBJECT_CLASSIFICATION_V1 — the four-way split of what vision
        # reported, so a caller can tell architecture from the worksite.
        "site_objects": site_classification,
    }


# ==========================================================
# PUBLIC ENTRY
# ==========================================================

def build_render_instruction(
    text: Any,
    *,
    understanding: Optional[Dict[str, Any]] = None,
    compiled: Optional[Dict[str, Any]] = None,
    references: Any = None,
    reference_analysis_ab: Any = None,
    user_geometry: Optional[Dict[str, Any]] = None,
    mode: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return the ArchitecturalRenderInstructionV1 contract for ``text``.

    ``understanding`` / ``compiled`` may be supplied by the caller so the
    live chat path never computes them twice. When omitted they are produced
    by the EXISTING canonical modules.

    T2I_MODE_PROPAGATION_V1 — ``mode`` / ``context`` are OPTIONAL and
    backward-compatible carriers for the validated render mode. When
    ``compiled`` is omitted this function compiles the prompt itself, and
    without the mode the compiler had to guess: a fresh text-to-image request
    was compiled as FACADE_REFINEMENT and told the model to "refine the
    existing facade" when no source facade existed. Both default to ``None``,
    so every existing caller is unchanged.

    FACADE-04D.3C-9P-B1 — ``user_geometry`` is an OPTIONAL, backward-compatible
    carrier for a REAL user-originated geometry confirmation (e.g. the user
    stating the target building has exactly three storeys: ground/first/second).
    It is ``None`` by default, so every existing caller and the default
    behaviour are unchanged. When supplied and structurally valid, its floor
    count becomes a hard ``USER_CONFIRMATION`` constraint while the raw Vision
    observation on IMAGE B is preserved verbatim. An unverified Vision
    observation is NEVER relabelled as user confirmation.
    """

    source = str(text or "")

    if understanding is None:

        understanding = understand(source)

    # T2I_HIGH_RISE_SUBJECT_FIDELITY_V1 — computed before compilation so the
    # compiler can build a count-bearing primary subject from the same grounded
    # values this contract already uses. `terminology` used to be computed
    # after the compile; it is a pure deterministic function, so moving it up
    # changes no result, it only makes it available to the subject section.
    terminology = normalize_architectural_terms(source)

    if compiled is None:

        subject_context = dict(context) if isinstance(context, dict) else {}

        _requested = requested_floor_count(source)

        if isinstance(_requested, dict) and isinstance(
            _requested.get("value"), int
        ) and not isinstance(_requested.get("value"), bool):

            subject_context["requested_floors"] = _requested["value"]

        _terms = terminology.get("canonical_terms") or []

        if _terms:

            subject_context["subject_terms"] = list(_terms)

        compiled = compile_prompt(
            understanding,
            mode=mode,
            context=subject_context,
        )

    base_prompt = str((compiled or {}).get("positive_prompt") or "")

    augmented = augment_compiled_prompt(base_prompt, terminology)

    # FACADE-04A.1 — a request carrying a style reference (IMAGE A) plus a
    # target building (IMAGE B) is a FACADE RESTYLE of an EXISTING building,
    # not the creation of a new design. Derived from the SAME A/B evidence the
    # section uses, so the intent, the opener and the constraints can never
    # disagree.
    facade_restyle = bool(
        isinstance(reference_analysis_ab, dict)
        and reference_analysis_ab.get("A")
        and reference_analysis_ab.get("B")
    )

    intent = _intent(source)

    # Reporting CREATE here would contradict preserving the target building's
    # geometry and would trip the fidelity gate's REVERSED_INTENT rule (a
    # facade restyle legitimately REFINES the existing building).
    if facade_restyle:

        intent = "REFINE"

    augmented = _normalise_intent_opening(augmented, intent)

    # FACADE-04A.1 — repair the terminology augmenter's malformed tail
    # ("... template., material, style" -> "... template. Terminology: ...").
    augmented = _normalise_terminology_tail(augmented)

    floors = _floor_count(source)

    # R1_B_FLOOR_COUNT_DESCRIPTION_REQUEST_V1 — the count the user stated
    # about the EXISTING building, kept separate from the requested target.
    # It is USER_TEXT, never vision evidence, and never a hard constraint.
    described_floors = _floor_count_description(source)

    geometry = _geometry(source, understanding)

    openings = _openings(source, understanding)

    camera = _camera(terminology, source)

    negations = _negations(source)

    # A rejected dimension is NOT a requirement — see _split_by_rejection.
    dimensions, rejected_dimensions = _split_by_rejection(
        source, _dimensions(source)
    )

    # FACADE-04D.3C-9P-A — the TARGET BUILDING's observed floor count (IMAGE B
    # ONLY). Used SOLELY to anchor a floor-count PRESERVATION instruction. It
    # is never taken from IMAGE A and never promoted to a user-stated hard
    # number (provenance stays VISION_OBSERVATION_UNVERIFIED in this phase).
    _b_analysis = (
        reference_analysis_ab.get("B")
        if isinstance(reference_analysis_ab, dict)
        else None
    ) or {}

    target_floor_count = (
        _b_analysis.get("visible_floor_count")
        if isinstance(_b_analysis.get("visible_floor_count"), int)
        else None
    )

    # T2I_ARCHITECTURAL_FEATURE_HANDOFF_V1 — the architectural elements the
    # user explicitly asked to exist. Empty for every request that asks for no
    # feature, so the existing instruction is unchanged in that case.
    feature_requirements = _feature_requirements(source)

    # SPATIAL_FRAMING_RETENTION_V1 — an explicit whole-building camera
    # requirement. False for every request that does not state one, so the
    # existing instruction is unchanged in that case.
    whole_building_visibility = _whole_building_visibility(source)

    # WHOLE_BUILDING_VISUAL_VERIFIABILITY_V1 — an EXACT user-stated floor count
    # is a claim the rendered view must be able to prove. None for every
    # request that states no exact count, states one storey, or explicitly
    # asks for a close-up.
    floor_count_framing = _floor_count_framing(floors, source)

    # T2I_FULL_TOWER_CAMERA_FRAMING_V1 — a grounded tall tower, from the same
    # canonical terminology the preset resolver reads. False for every request
    # that names no tower, so non-tower exact-count requests keep the existing
    # framing sentence byte for byte.
    tall_tower = "tower" in (terminology.get("canonical_terms") or [])

    # NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1 — a facade DESIGN on a building the
    # request treats as already existing. Gated on three independent facts so
    # a genuine new-build request can never be captured: a real style, a
    # facade scope, and an explicit reference to the existing building.
    existing_facade_redesign = bool(
        not facade_restyle
        and isinstance(understanding, dict)
        and understanding.get("scope") == "facade"
        and PersianArchitecturalUnderstandingEngine._named_style_target(
            understanding.get("style")
        )
        and PersianArchitecturalUnderstandingEngine._refers_to_existing_building(
            source
        )
    )

    extra = _constraint_sentences(
        floors, dimensions, openings, geometry, camera, negations, intent,
        facade_restyle=facade_restyle,
        target_floor_count=target_floor_count,
        feature_requirements=feature_requirements,
        whole_building_visibility=whole_building_visibility,
        floor_count_framing=floor_count_framing,
        tall_tower=tall_tower,
        existing_facade_redesign=existing_facade_redesign,
    )

    # FACADE-04D.3C-9P-B1 — a validated USER CONFIRMATION is resolved BEFORE
    # the A/B section so the floor-count conflict can be evaluated against the
    # HIGHEST-authority user value (current numeral, else confirmation), never
    # silently against the raw Vision observation. The raw Vision observation
    # is always preserved verbatim.
    _user_confirmation = _valid_user_geometry(user_geometry)

    # FACADE-04A — the grounded A/B section is appended AFTER the textual
    # constraints, so the Persian request keeps its own instructions and the
    # image observations are additive evidence.
    reference_ab = _reference_ab_section(
        reference_analysis_ab,
        floors,
        confirmed_floor_count=(
            _user_confirmation["value"] if _user_confirmation else None
        ),
        source_text=source,
    )

    parts = [
        part for part in [augmented] + extra + reference_ab["lines"] if part
    ]

    english_instruction = " ".join(parts).strip()

    # FACADE-04A.1 — the ONLY source of a hard numerical floor-count
    # constraint is the USER'S OWN TEXT (`floors` = `_floor_count(source)`).
    # A floor count observed on IMAGE B is an uncertain visual observation and
    # is reported as such; it never becomes "The building has exactly N floors".
    floor_count_provenance = None

    _b_analysis_for_prov = (
        reference_analysis_ab.get("B")
        if isinstance(reference_analysis_ab, dict)
        else None
    ) or {}

    _b_visible = _b_analysis_for_prov.get("visible_floor_count")

    _b_visible = _b_visible if isinstance(_b_visible, int) and not isinstance(
        _b_visible, bool
    ) else None

    if floors:

        floor_count_provenance = {
            "value": floors.get("value"),
            "source": "USER_TEXT",
            "raw": floors.get("raw"),
            "span": [floors.get("start"), floors.get("end")],
            "hard_constraint": True,
        }

    elif _user_confirmation is not None:

        _vision_block = None

        _conflict = False

        if _b_visible is not None:

            _vision_block = {
                "value": _b_visible,
                "source": "VISION_OBSERVATION_UNVERIFIED",
                "agrees": _b_visible == _user_confirmation["value"],
            }

            _conflict = _b_visible != _user_confirmation["value"]

        floor_count_provenance = {
            "value": _user_confirmation["value"],
            "source": "USER_CONFIRMATION",
            "hard_constraint": True,
            "confirmed_scope": _user_confirmation["confirmed_scope"],
            "vision_observation": _vision_block,
            "conflict": _conflict,
        }

    elif reference_ab.get("b_analyzed"):

        floor_count_provenance = {
            "value": _b_visible,
            "source": "VISION_OBSERVATION_UNVERIFIED",
            "hard_constraint": False,
        }

        # FACADE-04D.3C-9P-A — the user asked to PRESERVE the floor count
        # without stating a numeral. The VALUE is anchored to IMAGE B (the
        # geometry authority); IMAGE A's count is never used. Provenance stays
        # VISION_OBSERVATION_UNVERIFIED — a USER_CONFIRMATION value is
        # deliberately NOT invented here.
        if geometry.get("preserve_floor_count"):

            floor_count_provenance["preservation_requested"] = True

            floor_count_provenance["anchored_to"] = "IMAGE_B_TARGET"

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "source_text": source,
        "intent": intent,
        "facade_restyle": bool(facade_restyle),
        "english_instruction": english_instruction,
        "base_compiled_prompt": base_prompt,
        "terminology_terms": terminology.get("canonical_terms") or [],
        "terminology_families": terminology.get("families") or [],
        "constraints": {
            "floor_count": floors,
            "floor_count_provenance": floor_count_provenance,
            # R1_B_FLOOR_COUNT_DESCRIPTION_REQUEST_V1 — additive. The count
            # the user stated about the EXISTING building, reported so a
            # description is never mistaken for a requested target. This is
            # USER_TEXT: it is NOT visual evidence, and `visually_verified`
            # is False because text alone cannot establish the built state.
            "floor_count_description": (
                {
                    "value": described_floors.get("value"),
                    "raw": described_floors.get("raw"),
                    "span": [
                        described_floors.get("start"),
                        described_floors.get("end"),
                    ],
                    "source": "USER_TEXT_DESCRIPTION",
                    "visually_verified": False,
                }
                if described_floors
                else None
            ),
            "dimensions": dimensions,
            "rejected_dimensions": rejected_dimensions,
            "geometry": geometry,
            "openings": openings,
            "camera": camera,
            "negations": negations,
            # T2I_ARCHITECTURAL_FEATURE_HANDOFF_V1 — the requested features,
            # exposed alongside the other extracted constraints so a caller can
            # verify what the request asked for without re-parsing the text.
            "feature_requirements": feature_requirements,
            # SPATIAL_FRAMING_RETENTION_V1 — the explicit whole-building
            # framing requirement, stated structurally for the same reason.
            "whole_building_visibility": whole_building_visibility,
            # WHOLE_BUILDING_VISUAL_VERIFIABILITY_V1 — the exact count that
            # grounded the countable-view requirement, or None. Traceable so
            # the framing can be proven to follow the request.
            "floor_count_framing": floor_count_framing,
        },
        "hard_constraints": [
            sentence for sentence in extra
            if sentence.startswith("Do NOT") or "Keep the existing" in sentence
        ] + list(reference_ab["hard_constraints"]),
        "references": _reference_roles(references),
        "reference_analysis_ab": reference_ab,
        # SITE_OBJECT_CLASSIFICATION_V1 — the permanent/worksite split that
        # produced the constraints above, exposed for verification.
        "site_objects": reference_ab.get("site_objects") or {},
        "sources": {
            "understanding": (understanding or {}).get("contract"),
            "compiled": (compiled or {}).get("contract"),
            "terminology": terminology.get("contract"),
            "instruction_contract": CONTRACT,
        },
        "comfy_invoked": False,
        "render_executed": False,
    }


# ==========================================================
# RENDER_INSTRUCTION_HANDOFF_V1 — the bounded constraint block
#
# The full `english_instruction` is a REPORT: it narrates what IMAGE A looks
# like, what IMAGE B looks like, and what must be preserved. Only the last
# part is a CONSTRAINT, and only constraints may enter the sampler prompt:
#
#   * the FLUX T5 encoder runs at ComfyUI's default 512-token budget and no
#     workflow overrides it, so a 2.7k-character narration would push the
#     quality tail past the cut and be truncated mid-block;
#   * the descriptive half already exists in the compiled prompt.
#
# This function extracts the constraint sentences in priority order —
# user/safety rules, then geometry shape, then temporary objects, then target
# preservation — and returns a whole-sentence block under `max_chars`.
# It never invents text: every sentence comes from the instruction itself.
# ==========================================================

# LIVE_HANDOFF_V1 — the budget was calibrated at 1100 chars for a
# single-image instruction. The dual-image semantic role block alone is 1093
# chars (role mapping + the two preservation rules + the worksite-object
# safety rule), so on an A/B reference transfer the block filled up before the
# role mapping was ever reached and TARGET_BUILDING / STYLE_REFERENCE were
# silently dropped. The bound is raised once, here, rather than special-cased
# per caller, so a single documented limit still governs every route.
CONSTRAINT_BLOCK_BUDGET = 2400

#: 0 — the user's own explicitly requested architectural features. This is the
#: AUTHORITATIVE content of the turn: the measured defect was that it never
#: reached the sampler. It is admitted FIRST so a later generic rule can never
#: crowd it out of the budget.
#:
#: T2I_ARCHITECTURAL_FEATURE_HANDOFF_V1 — the prefix is one unique literal, so
#: only the sentences this module's own feature emitter writes can enter
#: through this group. No descriptive narrative shares the prefix.
_FEATURE_PREFIXES = (
    FEATURE_SENTENCE_PREFIX,
)

#: 1 — geometry SHAPE. A lost curve is the failure the product was reported
#: for, and it is the constraint most easily crowded out by generic rules.
_SHAPE_PREFIXES = (
    "The target building has CURVED",
    "Preserve their curvature",
    "Do not straighten",
)

#: 4 — temporary construction objects. The INTENT sentence is placed before the
#: enumeration: it is the actionable half, and the safety rule above already
#: names scaffolding, debris and signage.
_TEMPORARY_PREFIXES = (
    "The request asks for the FINISHED",
    "The request does not ask",
    "Reported TEMPORARY",
)

#: 5 — anything else that is still a constraint.
_OTHER_PREFIXES = (
    "Note: the target building",
)

#: LIVE_RENDER_FIDELITY_HANDOFF_FIX_V1 — the user's prohibition, WITH content.
#: A rejection the user stated explicitly is as binding as a feature request,
#: and the measured defect was that the prohibition sentence never reached the
#: bounded block at all: node 206 carried the feature and the floor count but
#: nothing that told the renderer what NOT to add.
_PROHIBITION_PREFIXES = (
    "Do NOT include:",
    "Respect the user's prohibition",
)

#: EXISTING_CAMERA_INSTRUCTION_HANDOFF_FIX_V1 — the camera sentence the
#: instruction builder has ALWAYS produced for an explicit camera request.
#: It was never admitted into the bounded block, so «نمای روبرو» reached
#: `english_instruction` as "Camera / view: frontal view." and was then
#: silently dropped before node 206.
_CAMERA_PREFIXES = (
    "Camera / view:",
)

#: Sentence prefixes that are DESCRIPTION, never a constraint.
#:
#: FINAL_ROLE_LABEL_CONSISTENCY_V1 — the generated appearance sentence now names
#: the STYLE_REFERENCE instead of "IMAGE A", because the user's own verbatim
#: block assigns IMAGE A to the TARGET building. Both spellings stay listed so a
#: recorded handoff produced before the change is still filtered as description.
_DESCRIPTION_PREFIXES = (
    "Take the facade APPEARANCE from IMAGE A",
    "Take the facade APPEARANCE from the STYLE_REFERENCE",
)

#: The generated target-preservation sentence, matched WITHOUT its suffix so
#: both the legacy "TARGET BUILDING" wording (still present in recorded
#: handoffs) and the current "TARGET_BUILDING" wording are admitted.
_TARGET_PRESERVE_PREFIX = "Preserve the TARGET"


def _sentences(text):
    """Split prose into whole sentences on the sentence boundary only."""

    text = str(text or "").strip()

    if not text:
        return []

    parts = []

    for chunk in text.split(". "):

        chunk = chunk.strip()

        if not chunk:
            continue

        if not chunk.endswith("."):
            chunk += "."

        parts.append(chunk)

    return parts


def _feature_sentences(instruction_text: Any) -> List[str]:
    """Every FEATURE-sentence in ``instruction_text``, whole and in order.

    The prefix is a unique literal this module alone writes, so the sentence
    runs from the prefix to the next sentence end. Slicing this way keeps the
    requirement intact even when the terminology tail abuts it with no period.
    """

    text = str(instruction_text or "").strip()

    if not text or FEATURE_SENTENCE_PREFIX not in text:

        return []

    found = []

    for chunk in text.split(FEATURE_SENTENCE_PREFIX)[1:]:

        # the sentence ends at the first sentence boundary after the prefix
        end = len(chunk)

        for separator in (".", "?", "!", "؟", "\n"):

            position = chunk.find(separator)

            if position >= 0:

                end = min(end, position + 1 if separator != "\n" else position)

        sentence = (FEATURE_SENTENCE_PREFIX + chunk[:end]).strip()

        if sentence:

            found.append(sentence)

    return found


def _prefix_sentences(instruction_text: Any, prefix: str) -> List[str]:
    """Every sentence in ``instruction_text`` that begins with ``prefix``.

    WHOLE_BUILDING_VISUAL_VERIFIABILITY_V1 — the SAME slicing rule
    `_feature_sentences` already uses, generalised so the framing sentences get
    it too. The measured defect: when the compiled prompt is empty, the
    terminology tail abuts the framing sentence with no period
    ("facade, building Frame the complete building: ..."), so a
    sentence-splitter sees ONE sentence that does not start with the prefix and
    the requirement silently vanished from the bounded block. The prefix is a
    unique literal this module alone writes, so the sentence runs from the
    prefix to the next sentence end.
    """

    text = str(instruction_text or "").strip()

    if not text or not prefix or prefix not in text:

        return []

    found = []

    for chunk in text.split(prefix)[1:]:

        end = len(chunk)

        for separator in (".", "?", "!", "؟", "\n"):

            position = chunk.find(separator)

            if position >= 0:

                end = min(end, position + 1 if separator != "\n" else position)

        sentence = (prefix + chunk[:end]).strip()

        if sentence and sentence not in found:

            found.append(sentence)

    return found


_DUAL_ROLE_PREFIXES = (
    "Role mapping (authoritative",
    "Do NOT copy the STYLE_REFERENCE",
    "Keep the TARGET_BUILDING",
)


def _is_dual_role_sentence(sentence):
    """True for a sentence that belongs to the dual-image role block.

    Membership is exact: the block's four sentences (role mapping, the two
    preservation rules and the worksite-object safety rule) are all binding
    for an A/B transfer and are admitted together so the budget can never
    drop one of them while keeping another.
    """

    text = str(sentence or "").strip()

    return text in DUAL_IMAGE_ROLE_BLOCK or any(
        text.startswith(prefix) for prefix in _DUAL_ROLE_PREFIXES
    )


def build_constraint_block(instruction, max_chars=CONSTRAINT_BLOCK_BUDGET):
    """Extract the constraint sentences from a render instruction contract.

    Deterministic. No model call. Returns "" when there is nothing to send.
    """

    if not isinstance(instruction, dict):

        return ""

    ordered = []

    def _add(sentence):

        sentence = str(sentence or "").strip()

        if not sentence:
            return

        if not sentence.endswith("."):
            sentence += "."

        if sentence not in ordered:
            ordered.append(sentence)

    # 0 — the user's own explicitly requested architectural features, which are
    # the authoritative content of the turn and must never be crowded out.
    # These are pulled out of the WHOLE instruction rather than from the
    # sentence split above: when the compiled prompt is empty, the terminology
    # tail can precede the first feature sentence with no period between them
    # ("facade, building REQUIRED ARCHITECTURAL FEATURE — …"), and a
    # startswith filter would then drop the user's own requirement. The prefix
    # is unique, so slicing from it to the next sentence end can never admit a
    # descriptive fragment.
    prose = _sentences(instruction.get("english_instruction"))

    # 0a — LIVE_HANDOFF_V1: the DUAL-IMAGE ROLE MAPPING is the most binding
    # constraint of an A/B reference transfer, and it was silently TRUNCATED.
    # It is admitted at step 5 (last), while the budget is 1100 chars, so the
    # block filled up first and `TARGET_BUILDING` / `STYLE_REFERENCE` never
    # reached node 206 — leaving the user's own IMAGE A / IMAGE B letters as
    # the only role naming in the prompt, with IMAGE B meaning "target" in one
    # half and "style reference" in the other.
    #
    # It is admitted FIRST here, and the budget is extended by exactly the
    # role block's own length so the user's requested features are not
    # crowded out by it. This only fires for a dual-image A/B instruction;
    # every other route keeps the existing ordering and budget byte for byte.
    _role_sentences = [
        sentence for sentence in (instruction.get("hard_constraints") or [])
        if _is_dual_role_sentence(sentence)
    ]

    for sentence in _role_sentences:

        _add(sentence)

    # 0a2 — LIVE_HANDOFF_V1: the GROUNDED target-preservation statement is the
    # only sentence that carries what the vision analysis actually observed
    # ("4 visible floor level(s); symmetry symmetric; …"). Admitting it with
    # the role block keeps the vision evidence from being crowded out by the
    # generic rules that follow. `_add` de-duplicates, so the later
    # "3 — concrete target-preservation" pass stays harmless.
    for sentence in prose:

        if sentence.startswith(_TARGET_PRESERVE_PREFIX):

            _add(sentence)

    for sentence in _feature_sentences(
        instruction.get("english_instruction")
    ):

        _add(sentence)

    # 0b — the USER-STATED floor count. This is a hard constraint on the
    # building's massing, and the measured defect was that it never reached the
    # sampler: the builder tail asserted "single floor building" for a
    # three-storey request. It is admitted immediately after the features so a
    # generic rule can never displace it, and only when the user actually
    # stated a count (`_floor_count` never invents one).
    _floors = (instruction.get("constraints") or {}).get("floor_count") or {}

    _floor_value = _floors.get("value")

    if isinstance(_floor_value, int) and not isinstance(_floor_value, bool) \
            and _floor_value > 0:

        _add(
            "The building has exactly %d floors." % _floor_value
        )

    # 0c — the user's explicit WHOLE-BUILDING framing. SPATIAL_FRAMING_
    # RETENTION_V1: a request that says "a perspective view of the WHOLE
    # building, with all floors, the entrance, the balcony and the roof
    # visible" has stated a camera requirement, which is as binding as a
    # feature requirement and used to survive only in the discarded builder
    # tail. Admitted directly after the features so the FLUX budget can never
    # truncate it before them; absent whenever the request never asked for it.
    # 0c — the user's explicit WHOLE-BUILDING framing, and the countable-view
    # framing an exact floor count requires (same prefix, same admission).
    #
    # WHOLE_BUILDING_VISUAL_VERIFIABILITY_V1 — sliced from the prefix rather
    # than filtered from the sentence split: with an empty compiled prompt the
    # terminology tail abuts the sentence with no period, and a startswith
    # filter then drops the framing entirely. This is the rule the feature
    # sentences already use.
    for sentence in _prefix_sentences(
        instruction.get("english_instruction"),
        WHOLE_BUILDING_FRAMING_PREFIX,
    ):

        _add(sentence)

    # 0e — EXISTING_CAMERA_INSTRUCTION_HANDOFF_FIX_V1 — the camera / view the
    # user explicitly asked for. Admitted directly after the framing so the T5
    # budget can never truncate it, and ONLY when the request stated one: no
    # request gains a camera angle it never mentioned.
    for prefix in _CAMERA_PREFIXES:

        for sentence in _prefix_sentences(
            instruction.get("english_instruction"),
            prefix,
        ):

            _add(sentence)

    # 0d — LIVE_RENDER_FIDELITY_HANDOFF_FIX_V1 — the user's explicit
    # prohibition. Admitted directly after the features and the floor count so
    # the FLUX budget can never truncate it before them, and ONLY when the
    # request actually stated one. Absent for every request without a
    # prohibition, so no accepted route changes.
    for prefix in _PROHIBITION_PREFIXES:

        for sentence in prose:

            if sentence.startswith(prefix):

                _add(sentence)

    # 1 — the shape constraint, which the generic rules do not carry.
    for prefix in _SHAPE_PREFIXES:

        for sentence in prose:

            if sentence.startswith(prefix):

                _add(sentence)

    # 2 — the site-object safety rule from the builder's hard constraints.
    remaining_hard = []

    for sentence in instruction.get("hard_constraints") or []:

        if "never architectural features" in sentence:

            _add(sentence)

        else:

            remaining_hard.append(sentence)

    # 3 — the concrete target-preservation statement.
    for sentence in prose:

        if sentence.startswith(_TARGET_PRESERVE_PREFIX):

            _add(sentence)

    # 4 — temporary objects and the intent that governs their removal.
    for prefix in _TEMPORARY_PREFIXES:

        for sentence in prose:

            if sentence.startswith(prefix):

                _add(sentence)

    # 5 — the remaining generic hard constraints, then anything else.
    for sentence in remaining_hard:

        _add(sentence)

    for prefix in _OTHER_PREFIXES:

        for sentence in prose:

            if sentence.startswith(prefix):

                _add(sentence)

    # 6 — never let a description in.
    ordered = [
        sentence for sentence in ordered
        if not any(sentence.startswith(prefix) for prefix in _DESCRIPTION_PREFIXES)
    ]

    if not ordered:

        return ""

    kept, total = [], 0

    for sentence in ordered:

        addition = len(sentence) + (1 if kept else 0)

        if total + addition > max_chars:

            break

        kept.append(sentence)

        total += addition

    return " ".join(kept)


print("🏗️ ARCHITECTURAL RENDER INSTRUCTION v1.0 ONLINE (contract only, no render)")
