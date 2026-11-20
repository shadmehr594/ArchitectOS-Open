# ==========================================================
# ArchitectOS Architectural Vision Interpreter V1
#
# Read-only architectural interpretation after ImageUnderstandingV1
# and before final response formatting.
#
# This layer does not design, edit, render, generate, or mutate geometry.
# ==========================================================

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

# ARCHITECTURAL_OBSERVATION_V1 — the observation contract + its pass-through.
# The interpreter runs the pass-through BEFORE interpreting, so visible
# evidence can never be lost by the interpretation vocabulary.
from core.vision.architectural_observation_v1 import (
    build_architectural_observation,
    visible_observations_passthrough,
)

# ARCHITECTURAL_VISUAL_INTERPRETATION_V2 — Observation -> Meaning.
# It consumes the observation contract as its PRIMARY SOURCE and is
# published additively; the legacy outputs above stay unchanged.
from core.vision.architectural_visual_interpretation_v2 import (
    build_architectural_visual_interpretation_v2,
)

# ARCHITECTURAL_SPATIAL_RELATIONSHIP_UNDERSTANDING_V1 — visible spatial
# organization. It consumes the observation + the V2 interpretation and is
# published additively; every existing output above stays unchanged.
from core.vision.architectural_spatial_relationship_understanding_v1 import (
    build_architectural_spatial_relationship_understanding_v1,
)

from core.vision.architectural_understanding_v1 import (
    build_architectural_understanding,
)
from core.vision.architectural_understanding_v2 import (
    build_architectural_understanding_v2,
)


CONTRACT = "ArchitecturalVisionInterpreterV1"
VERSION = "1.0"


_PROVIDER_FURNITURE_TOKENS = (
    "bed", "sofa", "couch", "chair", "table", "desk", "wardrobe",
    "closet", "cabinet", "counter", "sleeping element", "seating element",
    "تخت", "مبل", "صندلی", "میز", "کمد", "کابینت",
    "sink", "toilet", "fixture", "basin", "سینک", "روشویی", "توالت",
)


def _provider_phrase_is_furniture(value):
    lowered = _text(value).lower()
    return any(token in lowered for token in _PROVIDER_FURNITURE_TOKENS)


def _provider_evidence_for_local_plan(raw):
    """Remove ungrounded provider objects before generic element grounding.

    The original `raw` object is still passed to the architectural observation
    and preserved verbatim there.  This filtered view is only for deciding
    which objects are allowed to become visible/likely in the final report.
    """

    local = raw.get("local_plan_reading") if isinstance(raw, dict) else None
    if not (
        isinstance(local, dict)
        and (local.get("status") == "grounded" or local.get("symbol_analysis_status") == "analyzed")
    ):
        return raw

    cleaned = dict(raw)
    for field in (
        "observed", "observed_attributed", "inferred", "architectural_elements"
    ):
        value = raw.get(field)
        if isinstance(value, (list, tuple)):
            cleaned[field] = [
                item for item in value
                if not _provider_phrase_is_furniture(item)
            ]

    # Plan labels are handled by the dedicated OCR contract.  Feeding either
    # provider or OCR labels into object grounding would turn "پذیرایی" into
    # an observed sofa, which is exactly the category error this layer fixes.
    cleaned["text_labels_if_visible"] = []
    extras = dict(raw.get("observation_extras") or {})
    extras["furniture_elements"] = []
    extras["spatial_clues"] = []
    cleaned["observation_extras"] = extras
    return cleaned


def _apply_local_opening_grounding(grounding, local):
    if not isinstance(grounding, dict) or not isinstance(local, dict):
        return grounding

    windows = [
        item for item in local.get("openings") or []
        if isinstance(item, dict) and item.get("kind") == "window"
    ]
    if not windows:
        return grounding

    for entry in grounding.get("elements") or []:
        if entry.get("element") != "window":
            continue
        entry["status"] = "visible"
        entry["evidence"] = [{
            "element": "window",
            "field": "local_plan_reading.openings",
            "phrase": "locally grounded perimeter window openings",
            "class": "raster_geometry",
            "source": "local_raster_geometry",
            "instances": windows,
        }]

    visible = grounding.setdefault("visible_elements", [])
    if "window" not in visible:
        visible.append("window")
    for field in ("unverified_elements", "provider_only_elements", "not_reported_elements"):
        grounding[field] = [
            item for item in grounding.get(field) or [] if item != "window"
        ]
    return grounding

SPACE_TYPES = (
    "bedroom",
    "master bedroom",
    "living room",
    "kitchen",
    "bathroom",
    "corridor",
    "balcony",
    "facade",
    "entrance",
    "garden",
    "unknown",
)


# These phrases are only used to map provider evidence into architectural
# vocabulary. They do not create evidence when the provider returned none.
_OBSERVED_MAP = (
    (("bed", "تخت", "تخت خواب"), "sleeping element visible"),
    (("window", "glazing", "پنجره", "شیشه"), "daylight opening visible"),
    (("opening", "openings", "بازشو", "بازشوها"), "opening visible"),
    (("balcony", "بالکن"), "projecting outdoor platform visible"),
    (("entrance", "entry", "door", "ورودی", "درب"), "entrance threshold visible"),
    (("facade", "elevation", "نمای", "پوسته بیرونی"), "facade plane visible"),
    (("room", "اتاق", "فضای داخلی"), "enclosed room volume visible"),
    (("corridor", "hallway", "راهرو"), "circulation passage visible"),
    (("kitchen", "آشپزخانه"), "kitchen work zone visible"),
    (("bathroom", "حمام", "سرویس"), "sanitary zone visible"),
    (("seating", "chair", "sofa", "couch", "صندلی", "مبل"), "seating element visible"),
    (("cabinet", "counter", "cupboard", "کابینت", "کانتر"), "kitchen work zone visible"),
    (("toilet", "wc", "sink", "basin", "shower", "bathtub", "توالت", "دستشویی", "دوش"),
     "sanitary fixture visible"),
    (("closet", "wardrobe", "dressing", "کمد", "رختکن"), "storage or dressing element visible"),
    (("garden", "landscape", "باغ", "محوطه"), "landscape area visible"),
    (("wall", "partition", "vertical enclosure", "دیوار", "پارتیشن"),
     "vertical enclosure surface visible"),
    (("floor plane", "سطح کف", "کف اتاق"), "horizontal floor plane visible"),
)

_TYPE_TERMS = {
    "bedroom": ("bedroom", "bed", "تخت", "اتاق خواب"),
    "master bedroom": ("master bedroom", "اتاق خواب مستر", "مستر"),
    "living room": ("living room", "lounge", "نشیمن", "پذیرایی"),
    "kitchen": ("kitchen", "آشپزخانه"),
    "bathroom": ("bathroom", "حمام", "سرویس"),
    "corridor": ("corridor", "hallway", "راهرو"),
    "balcony": ("balcony", "بالکن"),
    "facade": ("facade", "elevation", "نمای ساختمان", "نمای", "exterior"),
    "entrance": ("entrance", "entry", "ورودی"),
    "garden": ("garden", "landscape", "باغ", "محوطه"),
}

_NUMBER_WORDS = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ده", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه",
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _items(value: Any) -> List[str]:
    if isinstance(value, str):
        return [_text(value)] if _text(value) else []
    if not isinstance(value, (list, tuple)):
        return []
    result = []
    for item in value:
        item_text = _text(item)
        if item_text and item_text not in result:
            result.append(item_text)
    return result


def _contains(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _has_floor_claim(text: str) -> bool:
    lowered = text.lower()
    if not _contains(lowered, ("floor", "floors", "طبقه", "طبقات", "level", "levels")):
        return False
    return bool(re.search(r"\d", lowered)) or _contains(lowered, _NUMBER_WORDS + ("exact", "exactly", "تعداد"))


def _is_unsupported_claim(text: str) -> bool:
    lowered = text.lower()
    if _has_floor_claim(text):
        return True
    return _contains(
        lowered,
        (
            "dimension", "measurement", "meter", "metre", "متر", "سانتی",
            "structural system", "structure", "load-bearing", "سازه", "اسکلت",
            "north", "south", "east", "west", "شمال", "جنوب", "شرق", "غرب",
            "luxury", "لوکس",
        ),
    )


# ==========================================================
# ARCHITECTURAL_VISION_OBSERVATION_V2 — THE PLAN READING
#
# A floor plan is a DRAWING OF MANY SPACES, never one room. Everything
# below is a deterministic projection of what the OBSERVATION ALREADY
# CONTAINS — the provider's own payload:
#
#   readable room LABEL     -> a space            (text_labels_if_visible)
#   the furniture list      -> furniture          (extras.furniture_elements)
#   a visible relation      -> an adjacency       (extras.spatial_clues)
#   the element list        -> walls / openings   (architectural_elements)
#
# NOTHING is invented. An item is emitted only when the provider named it,
# and every item carries the phrase it came from. Dimensions, orientation,
# materials, structure and hidden connections are never produced.
#
# This is a PROJECTION, not a new perception layer: the two additive V2
# layers already derive the same reading (`plan_interpretation`), and this
# publishes it into the contract the conversation actually shows.
# ==========================================================

PLAN_LABEL_SPACES = (
    ("اتاق خواب مستر", "master bedroom"),
    ("اتاق نشیمن", "living room"),
    ("اتاق خواب", "bedroom"),
    ("اتاق والدین", "bedroom"),
    ("اتاق مستر", "master bedroom"),
    ("اتاق‌خواب", "bedroom"),
    ("bedroom", "bedroom"),
    ("نشیمن", "living room"),
    ("پذیرایی", "living room"),
    ("living room", "living room"),
    ("آشپزخانه", "kitchen"),
    # "مطبخ" is the ordinary printed label for a kitchen / kitchenette in
    # Persian plans. Without it the label was silently DROPPED.
    ("مطبخ", "kitchen"),
    ("kitchen", "kitchen"),
    ("آبدارخانه", "pantry"),
    ("pantry", "pantry"),
    ("انباری", "storage"),
    ("storage", "storage"),
    ("کمد", "storage"),
    ("کلوزت", "storage"),
    # "service room" / "service area" — the provider's own wording for the
    # WC / service zone of a dwelling.
    ("service room", "wc"),
    ("service area", "wc"),
    ("service", "wc"),
    ("حمام", "bathroom"),
    ("bathroom", "bathroom"),
    ("سرویس", "wc"),
    ("دستشویی", "wc"),
    ("توالت", "wc"),
    ("wc", "wc"),
    ("راهرو", "corridor"),
    ("دالان", "corridor"),
    ("کریدور", "corridor"),
    ("corridor", "corridor"),
    ("ورودی", "entrance"),
    ("سردر", "entrance"),
    ("entrance", "entrance"),
    ("راه‌پله", "stair"),
    ("راه پله", "stair"),
    ("بالکن", "balcony"),
    ("تراس", "balcony"),
    ("ایوان", "balcony"),
    ("balcony", "balcony"),
    ("حیاط", "garden"),
    ("حیاط خلوت", "garden"),
    ("محوطه", "garden"),
    ("garden", "garden"),
    ("غذاخوری", "dining"),
    ("dining room", "dining"),
    ("پله", "stair"),
    ("stair", "stair"),
    # ARCHITECTURAL_SEMANTIC_READING_W3 — Latin architectural terms the label
    # reader can now ground. PATIO / COURTYARD / LIGHTWELL / VOID are published
    # as LABEL-level semantics only: no geometrically verified lightwell is
    # claimed from a text label.
    ("patio", "patio"),
    ("courtyard", "courtyard"),
    ("lightwell", "lightwell"),
    ("light well", "lightwell"),
    ("void", "void"),
    ("hall", "hall"),
    ("terrace", "terrace"),
    ("store room", "storage"),
    ("bed room", "bedroom"),
    ("living area", "living room"),
    ("dining area", "dining"),
    ("bath room", "bathroom"),
)


# Public / private / service — the brief's zoning vocabulary.
SPACE_ZONE = {
    "living room": "public",
    "entrance": "public",
    "dining": "public",
    "kitchen": "service",
    "pantry": "service",
    "storage": "service",
    "bathroom": "service",
    "wc": "service",
    "service": "service",
    "bedroom": "private",
    "master bedroom": "private",
    "corridor": "circulation",
    "stair": "circulation",
    # ARCHITECTURAL_VISION_LABEL_COMPLETENESS_V1 — a terrace / veranda is
    # NOT an interior zone. It gets its own band so it can never be lost
    # inside public/private/service.
    "balcony": "open_semi_open",
    "garden": "external",
    # ARCHITECTURAL_SEMANTIC_READING_W3 — label-level open/void semantics. A
    # patio / courtyard / lightwell / void is an open or semi-open band, never
    # an interior room, so it can never be counted as one.
    "patio": "open_semi_open",
    "terrace": "open_semi_open",
    "courtyard": "external",
    "lightwell": "open_semi_open",
    "void": "open_semi_open",
    "hall": "circulation",
}


# The zone bands, in the order the report renders them.
ZONE_ORDER = (
    "public",
    "private",
    "service",
    "circulation",
    "open_semi_open",
    "external",
)


# Furniture is ARCHITECTURAL EVIDENCE on a plan: it is what tells a
# sleeping space from a living space from a kitchen.
FURNITURE_SPACE_CUES = (
    ("bed", "bedroom"),
    ("تخت", "bedroom"),
    ("sofa", "living room"),
    ("couch", "living room"),
    ("مبل", "living room"),
    ("chair", "living room"),
    ("صندلی", "living room"),
    ("table", "dining"),
    ("میز", "dining"),
    ("cabinet", "kitchen"),
    ("counter", "kitchen"),
    ("کابینت", "kitchen"),
    ("appliance", "kitchen"),
    ("toilet", "wc"),
    ("توالت", "wc"),
    ("دستشویی", "wc"),
    ("sink", "bathroom"),
    ("basin", "bathroom"),
    ("bathtub", "bathroom"),
    ("shower", "bathroom"),
    ("دوش", "bathroom"),
    ("وان", "bathroom"),
    ("wardrobe", "storage"),
    ("closet", "storage"),
    ("کمد", "storage"),
)


ADJACENCY_MARKERS = (
    "adjacent to", "next to", "beside", "connected to", "adjoining",
    "attached to", "leading to", "leads to", "opening to", "opens to",
    "مجاور", "کنار", "چسبیده", "همجوار",
)

# A relation the provider stated WITHOUT the "to" — e.g. "bathroom and
# service adjacent". The spaces are then read from the phrase itself.
ADJACENCY_WORDS = (
    "adjacent", "adjoining", "connected", "مجاور", "همجوار", "چسبیده",
)

CIRCULATION_MARKERS = (
    "corridor", "corridors", "hallway", "passage", "circulation",
    "leads to", "leading to", "راهرو", "دالان", "کریدور", "گردش",
)


def _named_spaces(text: str) -> List[str]:
    """Every space the phrase NAMES, in the order the phrase names them."""

    lowered = _text(text).lower()

    found = []

    for token, space in PLAN_LABEL_SPACES:

        index = lowered.find(token.lower())

        if index < 0 or space in [entry[1] for entry in found]:

            continue

        found.append((index, space))

    return [space for _index, space in sorted(found)]


def _observation_extras(payload: Dict[str, Any]) -> Dict[str, Any]:
    """The provider's v3 categories, from wherever the payload keeps them.

    The raw provider output carries them at the TOP level; the
    understanding/observation contract carries them under
    `observation_extras` (and keeps the verbatim output in
    `raw_observations`). Both are read, so the reading never depends on
    which layer is handed in.
    """

    if not isinstance(payload, dict):

        return {}

    extras = payload.get("observation_extras")

    if isinstance(extras, dict) and extras:

        return extras

    raw = payload.get("raw_observations")

    if isinstance(raw, dict):

        nested = raw.get("observation_extras")

        if isinstance(nested, dict) and nested:

            return nested

        return {
            key: raw.get(key)
            for key in ("furniture_elements", "spatial_clues",
                        "style_indicators", "object_elements")
            if raw.get(key) not in (None, [], "", {})
        }

    return {}


def _canonical_space(text: str) -> str:
    """The space a provider phrase names, or the phrase itself."""

    lowered = _text(text).lower()

    for label, space in PLAN_LABEL_SPACES:

        if label.lower() in lowered:

            return space

    return _text(text)


def _plan_building_type(labels: List[str], spaces: List[Dict[str, Any]]):
    """"residential" when the named spaces are a dwelling's own rooms.

    A kitchen AND a bathroom AND a sleeping space named in one plan is a
    dwelling, not an office or a shop. The claim is LIKELY, carries the
    labels it came from, and is never made from a single room.
    """

    dwelling = {
        "bedroom", "master bedroom", "kitchen", "bathroom", "wc",
        "living room", "pantry", "dining",
    }

    named = [
        entry["space"] for entry in spaces if entry.get("space") in dwelling
    ]

    if len(named) < 3:

        return None

    return {
        "value": "residential",
        "status": "likely",
        "confidence": "LOW",
        "evidence": named,
        "reasoning_source": "grounded labels or bounded region-supported functions",
    }


def _plan_walls(elements: List[Dict[str, Any]], spaces: List[Dict[str, Any]],
                enclosure_geometry=None):
    """Enclosure count only comes from localized wall/region geometry.

    Semantic space labels may corroborate function, never count partitions.
    """
    phrases = [entry.get("evidence_phrase") for entry in elements
               if "wall" in (entry.get("kind") or []) and entry.get("evidence_phrase")]
    geometry = enclosure_geometry if isinstance(enclosure_geometry, dict) else {}
    regions = geometry.get("regions") or []
    return {
        "enclosure": {
            "status": "observed" if regions else "unknown",
            "evidence": regions or phrases,
            "reasoning_source": "local raster wall boundaries" if regions else "provider element list",
        },
        "partition": {
            "status": "likely" if geometry.get("multiple_spaces") else "unknown",
            "room_count": geometry.get("count") if geometry.get("count_status") == "exact" else None,
            "count_status": geometry.get("count_status", "unknown"),
            "multiple_spaces": bool(geometry.get("multiple_spaces")),
            "candidate_count_range": geometry.get("candidate_count_range"),
            "evidence": regions, "reasoning_source": "local raster wall/partition/opening regions",
        },
    }


def _items_all(value):
    """`_items`, but EVERY occurrence is kept (transcription, not a set)."""

    if isinstance(value, str):

        text = _text(value)

        return [text] if text else []

    if not isinstance(value, (list, tuple)):

        return []

    out = []

    for item in value:

        text = _text(item)

        if text:

            out.append(text)

    return out


def _semantic_function(text):
    """The space a printed label names, or None when nothing maps."""

    lowered = _text(text).lower()

    for token, space in PLAN_LABEL_SPACES:

        if token.lower() in lowered:

            return space

    return None


def _read_labels(observation: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The VERBATIM read labels, ONE ENTRY PER OCCURRENCE.

    ARCHITECTURAL_VISION_LABEL_COMPLETENESS_V1 — this is a TRANSCRIPTION
    RECORD, not an interpretation:

      * LABEL IDENTITY is the exact text the provider transcribed. It is
        never replaced by the space it may mean.
      * INSTANCE COUNT is preserved: two printed `اتاق خواب` labels are
        two entries, numbered #1 and #2.
      * SEMANTIC FUNCTION is attached as a SEPARATE field, and a label
        that maps to nothing is still recorded (status `label_unmapped`)
        instead of being silently dropped.
    """

    local = observation.get("local_plan_reading")

    if (
        isinstance(local, dict)
        and local.get("status") == "grounded"
        and isinstance(local.get("labels"), list)
    ):

        from core.vision.local_evidence_trust_v1 import (
            INDEPENDENTLY_VERIFIED_OCR, STABLE_LOCAL_OCR,
            ocr_trust_state, stability_passes,
        )

        independent_texts = observation.get("independently_verified_ocr_texts") or []

        seen: Dict[str, int] = {}
        entries: List[Dict[str, Any]] = []

        for item in local.get("labels") or []:

            if not isinstance(item, dict):

                continue

            text = _text(item.get("text"))

            if not text:

                continue

            # VISION_RETENTION_FIX_V2 — three fail-closed tiers. Only an
            # INDEPENDENTLY verified label may name, classify or zone a space.
            # A STABLE label (several passes of ONE engine over ONE image) is
            # reportable AS OCR only, and a lexicon substitution is audit-only.
            state = ocr_trust_state(item, independent_texts)

            seen[text] = seen.get(text, 0) + 1

            common = {
                "text": text,
                "occurrence": seen[text],
                "bbox_pixels": item.get("bbox_pixels"),
                "bbox_normalized": item.get("bbox_normalized"),
                "raw_ocr": item.get("raw_ocr"),
                "ocr_confidence": item.get("ocr_confidence"),
                "match_score": item.get("match_score"),
                "correction": item.get("correction"),
                "independent_passes": item.get("independent_passes"),
                "stability_passes": stability_passes(item),
            }

            if state != INDEPENDENTLY_VERIFIED_OCR:

                entries.append({
                    **common,
                    "semantic_function": None,
                    "zone": None,
                    "evidence_type": "local_ocr",
                    "status": ("stable_local_ocr" if state == STABLE_LOCAL_OCR
                               else "low_trust_ocr"),
                    "trust_state": state,
                    "confidence": ("MEDIUM" if state == STABLE_LOCAL_OCR else "LOW"),
                    "reasoning_source": (
                        "stable local OCR — same engine, same pixels; not "
                        "independent evidence" if state == STABLE_LOCAL_OCR else
                        "local OCR guess — retained for audit only"
                    ),
                    "promotion_reason": (
                        "stable_local_ocr_is_not_independent"
                        if state == STABLE_LOCAL_OCR else "low_trust_ocr"
                    ),
                })

                continue

            function = item.get("semantic_function") or _semantic_function(text)
            entries.append({
                **common,
                "semantic_function": function,
                "zone": SPACE_ZONE.get(function) if function else None,
                "evidence_type": "local_ocr",
                "status": "grounded_ocr",
                "trust_state": INDEPENDENTLY_VERIFIED_OCR,
                "confidence": item.get("confidence") or "LOW",
                "reasoning_source": (
                    "local OCR corroborated by an INDEPENDENT source "
                    "(provider OCR claim confirmed verbatim)"
                ),
                "promotion_reason": "independently_verified_ocr",
            })

        return entries

    texts = _items_all(observation.get("text_labels_verbatim"))

    if not texts:

        texts = _items_all(observation.get("text_labels_if_visible"))

    seen: Dict[str, int] = {}

    entries: List[Dict[str, Any]] = []

    for text in texts:

        seen[text] = seen.get(text, 0) + 1

        function = _semantic_function(text)

        entries.append({
            "text": text,
            "occurrence": seen[text],
            "semantic_function": function,
            "zone": SPACE_ZONE.get(function) if function else None,
            "evidence_type": "label",
            "status": "label" if function else "label_unmapped",
            "confidence": "MEDIUM" if function else "LOW",
            "reasoning_source": "provider text transcription, verbatim",
        })

    return entries


# An ELEMENT that establishes a SPACE. A plan often draws its circulation
# or entrance without printing a name for it.
ELEMENT_SPACES = (
    ("corridor", "corridor"),
    ("stair", "stair"),
    ("balcony", "balcony"),
    ("entrance", "entrance"),
)


def _geometry_spaces(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Spaces established by GEOMETRY (the element list), not by a label.

    ARCHITECTURAL_VISION_LABEL_COMPLETENESS_V1 — TASK 7: a circulation
    space that is drawn but not printed must be published as INFERRED
    CIRCULATION from geometry, never as a read label.
    """

    spaces: List[Dict[str, Any]] = []

    for entry in elements:

        phrase = entry.get("evidence_phrase")

        for kind in entry.get("kind") or []:

            for element_kind, space in ELEMENT_SPACES:

                if kind != element_kind:

                    continue

                if any(item["space"] == space for item in spaces):

                    continue

                spaces.append({
                    "space": space,
                    "zone": SPACE_ZONE.get(space),
                    "evidence": [phrase] if phrase else [],
                    "evidence_type": "geometry",
                    "status": "inferred",
                    "confidence": "MEDIUM",
                    "reasoning_source": "visible element (geometry); no readable "
                                        "label was confirmed for it",
                })

    return spaces


def _plan_spaces(
    labels: List[str], corroborated: Optional[set] = None
) -> List[Dict[str, Any]]:
    """The spaces the READABLE PLAN LABELS name.

    ARCHITECTURAL_VISION_EVIDENCE_PRECISION_V1 — a label is only published
    as a READ LABEL when the SAME payload corroborates the space somewhere
    else: an element in `architectural_elements`, a `spatial_clue`, or a
    furniture/fixture statement. A lone label token is a PROVIDER-ONLY
    claim and is moved out of the named-space section entirely.

    This is what stops a provider that invents a room name ("آبدارخانه")
    from publishing it as a space the image actually labels.
    """

    spaces: List[Dict[str, Any]] = []

    for label in labels:

        lowered = _text(label).lower()

        for token, space in PLAN_LABEL_SPACES:

            if token.lower() not in lowered:

                continue

            if not any(entry["space"] == space for entry in spaces):

                supported = (
                    corroborated is None or space in corroborated
                )

                spaces.append({
                    "space": space,
                    "zone": SPACE_ZONE.get(space),
                    "evidence": [_text(label)],
                    "evidence_type": "label" if supported else "provider_only",
                    "status": "label" if supported else "provider_only",
                    "confidence": "MEDIUM" if supported else "LOW",
                    "reasoning_source": (
                        "readable plan label (corroborated by other provider "
                        "evidence)" if supported else
                        "readable plan label with NO corroborating evidence "
                        "anywhere else in the payload"
                    ),
                })

            break

    return spaces


def _plan_furniture(
    names: List[str], status: str = "symbol_reading"
) -> List[Dict[str, Any]]:
    """The provider's furniture list, with the function each one cues.

    ARCHITECTURAL_VISION_EVIDENCE_PRECISION_V1 — on a DRAWING these are
    plan-SYMBOL readings, never object observations, so they can never
    become `visible`. And furniture is a FUNCTION cue only: it may never
    NAME a space. `usable_for_space_inference` is therefore False unless
    the furniture was genuinely OBSERVED (a photo), which is what stops
    "bed"/"sofa"/"table" from inventing a bedroom, a living room and a
    dining room on a plan that shows no reliable furniture.
    """

    furniture: List[Dict[str, Any]] = []

    observed = status == "visible"

    for name in names:

        lowered = _text(name).lower()

        if not lowered:

            continue

        supports = None

        for token, space in FURNITURE_SPACE_CUES:

            if token in lowered:

                supports = space

                break

        if any(entry["name"].lower() == lowered for entry in furniture):

            continue

        furniture.append({
            "name": _text(name),
            "supports_space": supports,
            "usable_for_space_inference": observed,
            "evidence_type": "furniture",
            "status": status,
            "confidence": "MEDIUM" if observed else "LOW",
            "reasoning_source": (
                "provider furniture observation"
                if observed
                else "provider furniture list on a DRAWING — a plan-symbol "
                     "reading, not an observed object"
            ),
        })

    return furniture


def _corroborated_spaces(observation: Dict[str, Any]) -> set:
    """The spaces the payload names OUTSIDE its text labels.

    Only `architectural_elements`, `spatial_clues` and the furniture list
    count: a label can never corroborate itself.
    """

    extras = _observation_extras(observation)

    named = set()

    for phrase in (
        _items(observation.get("architectural_elements"))
        + _items(extras.get("spatial_clues"))
    ):

        named.update(_named_spaces(phrase))

    # A furniture / fixture cue names the space it belongs to as well, so
    # "kitchen counter" corroborates a kitchen label.
    for phrase in _items(extras.get("furniture_elements")):

        lowered = _text(phrase).lower()

        for token, space in FURNITURE_SPACE_CUES:

            if token in lowered:

                named.add(space)

    return named


def _plan_openings(
    elements: List[Dict[str, Any]], grounding: Any, local_plan_reading: Any = None
) -> List[Dict[str, Any]]:
    """Doors / windows / openings the provider named, with their tier."""

    statuses = {}

    if isinstance(grounding, dict):

        statuses = {
            entry.get("element"): entry.get("status")
            for entry in grounding.get("elements") or []
        }

    tier_of = {
        "door": statuses.get("entrance"),
        "entrance": statuses.get("entrance"),
        "window": statuses.get("window"),
        "opening": statuses.get("opening"),
    }

    openings: List[Dict[str, Any]] = []

    local_openings = (
        local_plan_reading.get("openings") or []
        if isinstance(local_plan_reading, dict)
        and local_plan_reading.get("status") == "grounded"
        else []
    )

    for kind in ("window", "door", "entrance", "opening"):

        instances = [
            item for item in local_openings
            if isinstance(item, dict) and item.get("kind") == kind
        ]

        if not instances:

            continue

        openings.append({
            "kind": kind,
            "evidence": [
                item.get("evidence") for item in instances
                if item.get("evidence")
            ],
            "status": "visible",
            "confidence": min(
                (item.get("confidence") or "LOW" for item in instances),
                key=lambda value: {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(value, 0),
            ),
            "evidence_type": "local_raster_geometry",
            "grounding_note": None,
            "reasoning_source": "provider-independent local raster geometry",
            "instances": instances,
            "instance_count": len(instances),
        })

    for entry in elements:

        phrase = entry.get("evidence_phrase")

        for kind in entry.get("kind") or []:

            if kind not in ("door", "entrance", "window", "opening"):

                continue

            if any(item.get("kind") == kind for item in openings):

                # Local raster evidence wins; retain provider wording only as
                # additional evidence, never as a second opening claim.
                existing = next(
                    item for item in openings if item.get("kind") == kind
                )
                if phrase and phrase not in existing["evidence"]:

                    existing["evidence"].append(phrase)

                continue

            existing = next(
                (item for item in openings if item["kind"] == kind), None
            )

            if existing is not None:

                if phrase and phrase not in existing["evidence"]:

                    existing["evidence"].append(phrase)

                continue

            status = tier_of.get(kind) or "reported"

            note = None

            if status != "visible":

                # ARCHITECTURAL_VISION_EVIDENCE_PRECISION_V1 — say exactly
                # WHY it is not grounded, so the reader can tell a missing
                # symbol from a missing localization.
                region = (
                    grounding.get("region_grounding") or {}
                    if isinstance(grounding, dict)
                    else {}
                )

                note = (
                    "reported in the provider's element list only; the "
                    "provider supplied no localization"
                    + (
                        " (supports_region_grounding = false)"
                        if region.get("supported") is False
                        else ""
                    )
                    + " and no visible opening was grounded"
                )

            openings.append({
                "kind": kind,
                "evidence": [phrase] if phrase else [],
                "status": status,
                "evidence_type": "geometry",
                "grounding_note": note,
                "reasoning_source": "provider element list",
            })

    return openings


def _plan_relations(
    clues: List[str], verified: Optional[set] = None
) -> List[Dict[str, Any]]:
    """The visible RELATIONS the provider reported between spaces.

    ARCHITECTURAL_VISION_EVIDENCE_PRECISION_V1 — each ENDPOINT carries
    whether the payload actually names it. A relation to a space that is
    only furniture-inferred (dining, from "table") is reported as a
    relation to an UNVERIFIED activity zone, never as a named room.
    """

    def marks(between):

        if verified is None:

            return [True] * len(between)

        return [name in verified for name in between]

    relations: List[Dict[str, Any]] = []

    for clue in clues:

        text = _text(clue)

        if not text:

            continue

        lowered = text.lower()

        placed = False

        for marker in ADJACENCY_MARKERS:

            if marker not in lowered:

                continue

            left, _sep, right = lowered.partition(marker)

            endpoints = [_canonical_space(left), _canonical_space(right)]

            relations.append({
                "kind": "adjacency",
                "between": endpoints,
                "between_verified": marks(endpoints),
                "evidence": [text],
                "status": "observed",
                "confidence": "MEDIUM",
                "reasoning_source": "provider spatial clue",
            })

            placed = True

            break

        # "bathroom and service adjacent" states the relation WITHOUT the
        # "to"; the spaces are read from the phrase itself.
        if not placed and any(word in lowered for word in ADJACENCY_WORDS):

            named = _named_spaces(text)

            if len(named) >= 2:

                relations.append({
                    "kind": "adjacency",
                    "between": [named[0], named[1]],
                    "between_verified": marks([named[0], named[1]]),
                    "evidence": [text],
                    "status": "observed",
                    "confidence": "MEDIUM",
                    "reasoning_source": "provider spatial clue",
                })

                placed = True

        if not placed and any(marker in lowered for marker in CIRCULATION_MARKERS):

            endpoints = [_canonical_space(text)]

            relations.append({
                "kind": "circulation",
                "between": endpoints,
                "between_verified": marks(endpoints),
                "evidence": [text],
                "status": "observed",
                "confidence": "LOW",
                "reasoning_source": "provider spatial clue",
            })

    return relations


def _plan_zones(spaces: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Public / private / service / circulation, from the named spaces."""

    zones: Dict[str, List[str]] = {
        "public": [], "private": [], "service": [],
        "circulation": [], "open_semi_open": [], "external": [],
    }

    for entry in spaces:

        zone = entry.get("zone")

        if zone in zones and entry["space"] not in zones[zone]:

            zones[zone].append(entry["space"])

    return zones


def build_plan_reading(
    observation: Dict[str, Any],
    grounding: Any = None,
    furniture_names: Optional[List[str]] = None,
    clue_phrases: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """The published PLAN READING contract for a drawing.

    Local raster evidence and provider claims retain separate provenance.
    Furniture supports function only inside independently localized regions.
    No authoritative dimensions, orientation or design are produced.
    """

    observation = observation if isinstance(observation, dict) else {}

    extras = _observation_extras(observation)

    local_plan_reading = observation.get("local_plan_reading")

    if isinstance(local_plan_reading, dict):
        from core.vision.local_plan_sheet_v1 import grounded_sheet_structure
        if grounded_sheet_structure(local_plan_reading):
            from core.vision.local_plan_sheet_v1 import build_sheet_plan_reading
            return build_sheet_plan_reading(local_plan_reading, build_plan_reading)

    local_grounded = (
        isinstance(local_plan_reading, dict)
        and (local_plan_reading.get("status") == "grounded"
             or local_plan_reading.get("symbol_analysis_status") == "analyzed")
    )

    labels = _items(observation.get("text_labels_if_visible"))

    names = (
        furniture_names
        if furniture_names is not None
        else _items(extras.get("furniture_elements"))
    )

    clues = (
        clue_phrases
        if clue_phrases is not None
        else _items(extras.get("spatial_clues"))
    )

    elements = observation.get("architectural_elements") or []

    # ==================================================
    # ARCHITECTURAL_VISION_EVIDENCE_PRECISION_V1
    #
    # 1. A label is published as a READ LABEL only when the payload
    #    corroborates the space OUTSIDE its labels.
    # 2. Furniture is a FUNCTION cue, never a name, and on a DRAWING it is
    #    only a plan-symbol reading — so it can neither name nor create a
    #    space.
    # ==================================================
    corroborated = None if local_grounded else _corroborated_spaces(observation)

    # ARCHITECTURAL_VISION_LABEL_COMPLETENESS_V1 — the verbatim label
    # record (identity + multiplicity) is built FIRST and kept separate
    # from every semantic reading of it.
    read_labels = _read_labels(observation)

    label_spaces = _plan_spaces(labels, corroborated)

    # A space the GEOMETRY establishes is published as geometry evidence,
    # never as a read label. The provider's label token, when there is
    # one, is attached to it as an unverified claim.
    geometry_spaces = [] if local_grounded else _geometry_spaces(elements)

    geometry_names = {entry["space"] for entry in geometry_spaces}

    for entry in geometry_spaces:

        claims = [
            item.get("evidence", [None])[0]
            for item in label_spaces
            if item["space"] == entry["space"]
        ]

        entry["provider_label_claim"] = [
            claim for claim in claims if claim
        ]

    named_spaces = [
        entry for entry in label_spaces
        if entry.get("status") == "label"
        and entry["space"] not in geometry_names
    ]

    # LOCAL_PLAN_READING_V1 — the provider's own label claims, kept as an
    # auditable provider-only record. A provider label whose SPACE the
    # grounded local reading already established is not repeated.
    grounded_names = {entry["space"] for entry in named_spaces}

    provider_label_claims = []

    for text in _items_all(observation.get("provider_labels")):

        function = _semantic_function(text)

        # EVERY provider label is recorded for audit — including one whose
        # space the local reading already grounded, which is reported as a
        # provider SYNONYM rather than a new claim.
        provider_label_claims.append({
            "text": text,
            "semantic_function": function,
            "space_already_grounded": bool(
                function and function in grounded_names
            ),
            "evidence_type": "provider_only",
            "status": "provider_only",
            "reason_code": (
                "provider_label_synonym_for_grounded_space"
                if function and function in grounded_names
                else "provider_label_not_grounded"
            ),
        })

    spaces = named_spaces + [
        entry for entry in label_spaces
        if entry.get("status") != "label"
    ] + geometry_spaces

    from core.vision.local_plan_symbols_v1 import grounded_plan_items
    from core.vision.local_plan_elements_v1 import grounded_plan_elements, interpret_plan_elements

    enclosure_geometry = (local_plan_reading or {}).get("enclosure_geometry") or {}
    local_items = grounded_plan_items(local_plan_reading)
    if local_grounded and local_plan_reading.get("symbol_analysis_status") == "analyzed":
        geometry_spaces = [
            dict(region, space="enclosed region", status="geometry", evidence_type="geometry",
                 evidence=[region["bbox_pixels"]], reasoning_source="bounded local raster region")
            for region in enclosure_geometry.get("regions") or []
        ]
        spaces = named_spaces + geometry_spaces

    furniture = (
        [dict(item, supports_space=item.get("supported_function"),
              usable_for_space_inference=bool(item.get("region_ids")),
              reasoning_source="localized raster symbol corroborated by drawing geometry")
         for item in local_items]
        if isinstance(local_plan_reading, dict)
        else _plan_furniture(names, status="symbol_reading")
    )


    openings = _plan_openings(elements, grounding, local_plan_reading)

    verified_spaces = {
        entry["space"] for entry in named_spaces
    } | geometry_names

    all_relations = _plan_relations(clues, verified_spaces)

    # TASK 5 — a relation may only be published when BOTH endpoints are
    # themselves supported. A relation to an unsupported space is moved
    # out of the trusted set instead of being printed as if it were real.
    relations = []

    unsupported_relations = []

    for relation in all_relations:

        marks = relation.get("between_verified") or []

        if marks and all(marks):

            relations.append(relation)

        else:

            unsupported_relations.append(relation)

    if local_grounded:

        # Provider-only relation endpoints are retained only in the preserved
        # raw payload.  Publishing them, even under an "unverified" heading,
        # re-introduces room names which the grounded source text does not have.
        unsupported_relations = []

    walls = []

    for entry in elements:

        if "wall" in (entry.get("kind") or []):

            phrase = entry.get("evidence_phrase")

            if phrase and phrase not in walls:

                walls.append(phrase)

    # A localized furniture/fixture cue may support a function ONLY in an
    # independently detected region. Provider-only symbol names are excluded;
    # neither furniture nor source labels may create an enclosure.
    inferred_functions = []

    for item in furniture:
        if not item.get("usable_for_space_inference"):
            continue
        space = item.get("supports_space")
        if not space:
            continue
        if local_grounded:
            eligible = [region for region in geometry_spaces
                        if region.get("region_id") in (item.get("region_ids") or [])]
            if not eligible:
                continue
            # Seating only supports a common zone; a bed needs an enclosure.
            # Fixtures likewise need an enclosure. A function never creates
            # a region or determines its count.
            for region in eligible:
                if space == "living room" and region.get("pixel_area", 0) < (
                    local_plan_reading["image_size"]["width"] * local_plan_reading["image_size"]["height"] * .04
                ):
                    continue
                existing = next((e for e in inferred_functions
                                 if e["space"] == space and e.get("region_id") == region["region_id"]), None)
                if existing:
                    existing["evidence"].append(item["item_id"])
                    continue
                inferred_functions.append({
                    "space": space, "zone": SPACE_ZONE.get(space),
                    "region_id": region["region_id"], "bbox_pixels": region["bbox_pixels"],
                    "evidence": [item["item_id"]], "evidence_type": item["evidence_type"],
                    "status": "inferred", "confidence": region.get("confidence", "LOW"),
                    "reasoning_source": "local enclosed region + localized furniture/fixture",
                })
        elif not any(entry["space"] == space for entry in spaces):
            inferred_functions.append({
                "space": space, "zone": SPACE_ZONE.get(space), "evidence": [item["name"]],
                "evidence_type": "furniture", "status": "inferred", "confidence": "LOW",
                "reasoning_source": "observed furniture cue",
            })

    # A space the GEOMETRY established is supported, not unsupported: it
    # is published with `evidence_type = geometry` in the space section.
    unsupported_claims = [
        {
            "space": entry["space"],
            "evidence": entry.get("evidence") or [],
            "evidence_type": "provider_only",
            "status": "provider_only",
            "reason_code": "label_uncorroborated",
            "reason": entry.get("reasoning_source"),
        }
        for entry in spaces
        if entry.get("status") == "provider_only"
    ]

    for item in furniture:

        if item.get("usable_for_space_inference") or not item.get(
            "supports_space"
        ):

            continue

        # A furniture cue that points at a space the payload ALREADY names
        # is a supporting cue for a confirmed space, not an unsupported
        # space claim. Publishing it here too would put the same space in
        # two sections with two different confidences.
        if any(
            entry["space"] == item["supports_space"]
            for entry in named_spaces
        ):

            continue

        unsupported_claims.append({
            "space": item["supports_space"],
            "evidence": [item["name"]],
            "evidence_type": "furniture",
            "status": "unverified",
            "reason_code": "furniture_symbol_on_drawing",
            "reason": (
                "a furniture name on a DRAWING is a plan-symbol reading, "
                "not an observed object — it supports a function, it does "
                "not establish a space"
            ),
        })

    plan_reading = {
        "contract": "ArchitecturalPlanReadingV1",
        "version": "1.0",
        "building_type": _plan_building_type(
            labels, named_spaces + geometry_spaces + inferred_functions
        ),
        "spaces": spaces,
        "space_count": enclosure_geometry.get("count"),
        "semantic_space_count": len(named_spaces),
        "enclosure_geometry": enclosure_geometry,
        "read_labels": read_labels,
        "provider_label_claims": provider_label_claims,
        "named_spaces": named_spaces,
        "geometry_spaces": geometry_spaces,
        "inferred_functions": inferred_functions,
        "unsupported_relations": unsupported_relations,
        "unsupported_claims": unsupported_claims,
        "furniture_observed": (
            True if local_items else local_plan_reading.get("furniture_observed")
        ) if isinstance(local_plan_reading, dict) else any(
            item.get("usable_for_space_inference") for item in furniture
        ),
        "symbol_analysis_status": (
            local_plan_reading.get("symbol_analysis_status", "unknown")
            if isinstance(local_plan_reading, dict) else "unknown"
        ),
        "evidence_taxonomy": [
            "label", "geometry", "symbol", "furniture", "fixture",
            "relation", "provider_only",
        ],
        "zones": _plan_zones(named_spaces + inferred_functions),
        "walls": walls,
        "wall_reading": _plan_walls(
            elements, named_spaces + geometry_spaces, enclosure_geometry
        ),
        "openings": openings,
        "architectural_elements": grounded_plan_elements(local_plan_reading),
        "element_interpretation": interpret_plan_elements(
            grounded_plan_elements(local_plan_reading), inferred_functions
        ),
        "furniture": furniture,
        "relations": relations,
        "circulation": sorted({
            relation["between"][0]
            for relation in relations
            if relation["kind"] == "circulation"
        } | {
            entry["space"] for entry in (named_spaces + geometry_spaces)
            if entry.get("zone") == "circulation"
        }),
        "readable_labels": labels,
        "local_plan_reading": local_plan_reading,
        "provider_labels_overridden": bool(local_grounded),
        "observation_only": True,
        "geometry_authoritative": False,
        "dimensions_stated": False,
        "orientation_stated": False,
        "materials_stated": False,
        "structure_stated": False,
        "render_requested": False,
        "comfy_invoked": False,
        "llm_used": False,
        "read_only": True,
    }

    # ==================================================
    # W4.1 — ARCHITECTURAL FUNCTION EVIDENCE CONTRACT
    #
    # SHADOW MODE ONLY. Additive: every field above is left byte-identical and
    # nothing is resolved. The evidence structure is the contract the future W4
    # reasoner will consume; it audits what evidence actually exists.
    # ==================================================
    from core.vision.architectural_function_evidence_v1 import (
        build_architectural_function_evidence,
    )

    plan_reading["architectural_function_evidence"] = (
        build_architectural_function_evidence(plan_reading)
    )

    return plan_reading


def _architectural_observations(raw: Dict[str, Any]) -> List[str]:
    # ARCHITECTURAL_VISION_OBSERVATION_V2 — the provider's own furniture
    # and spatial-clue categories are observations too, and were never
    # read here. Without them a furnished plan could only ever yield
    # "wall" and "entrance".
    extras = _observation_extras(raw)
    evidence = (
        _items(raw.get("observed"))
        + _items(raw.get("architectural_elements"))
        + _items(extras.get("furniture_elements"))
        + _items(extras.get("spatial_clues"))
    )
    observed = []
    for phrase in evidence:
        if _is_unsupported_claim(phrase):
            continue
        lowered = phrase.lower()
        for terms, architectural_term in _OBSERVED_MAP:
            if _contains(lowered, terms):
                if architectural_term not in observed:
                    observed.append(architectural_term)
                break
    return observed


def _evidence_text(raw: Dict[str, Any], user_text: str = "") -> str:
    values = []
    for key in ("image_type", "observed", "architectural_elements", "text_labels_if_visible"):
        value = raw.get(key)
        if isinstance(value, (list, tuple)):
            values.extend(_items(value))
        else:
            values.append(_text(value))
    return " ".join(value for value in values if value).lower()


def _space_type(raw: Dict[str, Any], observed: List[str], user_text: str) -> str:
    return _space_type_basis(raw, observed, user_text)[0]


# VISION_OBSERVATION_MODE_SEPARATION_V1 — brief rule 2: a space
# classification needs MULTIPLE evidence sources. A single bed gives the
# conservative "bedroom"; the stronger master-bedroom label needs either
# an explicit master label, or a sleeping element PLUS at least two suite
# elements (dressing/closet, sanitary zone, WC).
_MASTER_SUITE_ELEMENTS = (
    "wardrobe_or_closet",
    "bathroom_or_ensuite",
    "wc",
)


def _master_suite_sources(grounding) -> List[str]:
    """The GROUNDED visible suite elements behind a master-bedroom claim."""

    if not isinstance(grounding, dict):

        return []

    visible = set(grounding.get("visible_elements") or [])

    return [
        element for element in _MASTER_SUITE_ELEMENTS if element in visible
    ]


# ==========================================================
# VISION_SPACE_TYPE_EVIDENCE_DISCIPLINE_V1 — A TERM IS EVIDENCE ONLY
# WHEN IT STANDS AS A WHOLE WORD
#
# The defect this closes was measured on the real saved observation of
# facade A (Neue Nationalgalerie):
#
#     architectural_elements[3] = "one prominent light/whitish ribbed panel"
#
# `_space_type_basis` matched a bare SUBSTRING, so the character sequence
# `bed` inside the word `ribbed` published
#
#     space_type           = "bedroom"
#     possible_function    = ["likely bedroom"]
#     classification_basis = ["bedroom from sleeping element (architectural_elements)"]
#
# A description of architectural texture became evidence of sleeping
# furniture. The same defect exists in Persian: `تخته` (board / panel)
# contains `تخت` (bed), so a boarded wall was a bedroom.
#
# `\w` is Unicode-aware in Python 3 and therefore already covers Persian
# letters — the convention the `مستر` guard used. What a bare `(?!\w)` does
# NOT cover is INFLECTION: "Two beds are present" is still a bed, and
# `تخت‌ها` is still a bed. An English plural (`s` / `es`) and a Persian
# plural (`ها` / `های` / `هایی`, optionally ZWNJ-joined) may therefore
# continue the word. Anything else — `ribbed`, `embedded`, `bedrock`,
# `bedside`, `تخته` — is a DIFFERENT word and never matches.
#
# This is the general matching rule, not a `ribbed` special case: it is
# applied to every term the space-type vocabulary contains.
# ==========================================================

_TERM_TAIL = r"(?:s|es|\u200c?ها(?:ی|یی)?)?"


def _term_pattern(term: str) -> str:
    """The whole-word pattern for one vocabulary term."""

    return r"(?<!\w)" + re.escape(term.lower()) + _TERM_TAIL + r"(?!\w)"


def _matches(text: str, term: str) -> bool:
    return re.search(_term_pattern(term), text) is not None


# The evidence fields a space classification may be READ from, and the only
# fields a classification basis may CITE.
#
# `furniture_elements` is the provider's own furniture list, kept under
# `observation_extras`. A bed reported there is real evidence — and it must
# be cited from THERE. Before this milestone it was not a source at all, so
# a bed reported only as furniture was invisible, while a bed-shaped
# substring in the architectural element list was accepted.
_SPACE_EVIDENCE_FIELDS = (
    "image_type",
    "observed",
    "furniture_elements",
    "architectural_elements",
    "text_labels_if_visible",
)


def _space_type_basis(
    raw: Dict[str, Any], observed: List[str], user_text: str,
    observation: Optional[Dict[str, Any]] = None,
) -> tuple:
    """(space_type, classification_basis) — the basis is auditable.

    ``observation`` — VISION_SPACE_TYPE_SUBJECT_ROLE_SAFETY_V1 — the audited
    architectural observation for the same payload, used ONLY to resolve the
    ROLE a term plays inside an element phrase. It never adds evidence: the
    classification is still read from `raw`, exactly as before. Omitting it
    reproduces the previous behaviour byte for byte.
    """

    image_type = _text(raw.get("image_type")).lower().replace("_", " ")

    extras = _observation_extras(raw)

    field_values = {
        "image_type": [_text(raw.get("image_type"))],
        "observed": _items(raw.get("observed")),
        "furniture_elements": _items(extras.get("furniture_elements")),
        "architectural_elements": _items(raw.get("architectural_elements")),
        "text_labels_if_visible": _items(raw.get("text_labels_if_visible")),
    }

    source_items = []
    for field in _SPACE_EVIDENCE_FIELDS:
        source_items.extend(
            (field, value.lower()) for value in field_values[field] if value
        )

    negation_terms = (
        "no", "not", "without", "absent", "missing", "none", "does not",
        "بدون", "ندارد", "ندارند", "نیست", "نیستند", "دیده نمی",
        "دیده نشد", "مشاهده نشد", "وجود ندارد", "ثبت نشده", "حذف",
    )

    def _is_explicitly_negated(text: str) -> bool:
        return any(
            re.search(
                r"(?<!\w)" + re.escape(term) + r"(?!\w)",
                text,
            )
            for term in negation_terms
        )

    # ==================================================
    # VISION_SPACE_TYPE_SUBJECT_ROLE_SAFETY_V1
    #
    # MEASURED DEFECT: an element named inside the description of ANOTHER
    # element was treated as evidence for the SCENE. Facade C's restored claim
    #
    #   "three stacked levels, each with a dark-glazed rectangular window
    #    behind a projecting balcony ..."
    #
    # is a WINDOW observation. The balcony it mentions is a component of that
    # description, yet it typed the whole elevation as a balcony.
    #
    # The structural signal already exists: every architectural element
    # carries `kind`, and the FIRST kind is the element's own primary
    # classification — the thing the entry IS. A scene type may therefore be
    # read from an `architectural_elements` entry only when that scene type is
    # the entry's own primary kind. A mention inside a different element's
    # phrase is a role, not a subject.
    #
    # This resolves ROLE only. It never adds evidence, never promotes a claim
    # and never suppresses a term globally: an element whose primary kind IS
    # balcony still classifies as a balcony.
    # ==================================================

    primary_kinds: Dict[str, str] = {}

    if isinstance(observation, dict):

        for entry in observation.get("architectural_elements") or []:

            if not isinstance(entry, dict):

                continue

            phrase = _text(entry.get("evidence_phrase")).lower()

            kinds = entry.get("kind")

            primary = kinds[0] if isinstance(kinds, list) and kinds else kinds

            if phrase and isinstance(primary, str) and primary:

                primary_kinds.setdefault(phrase, primary)

    def _positive_sources(terms, scene_type: Optional[str] = None) -> List[str]:
        """The evidence fields that AFFIRMATIVELY carry one of `terms`.

        A field is returned only when it really holds an entry in which the
        term stands as a whole word and that entry is not negated. The
        returned name is therefore a truthful citation: the field contains
        the qualifying observation the basis claims it does.

        `scene_type` — when given, an `architectural_elements` entry counts
        only if that scene type is the entry's OWN primary kind. See the
        subject-role note above.
        """

        sources = []
        for field, text in source_items:
            if field in sources:
                continue
            if _is_explicitly_negated(text):
                continue
            if not any(_matches(text, term) for term in terms):
                continue
            if scene_type and field == "architectural_elements":
                primary = primary_kinds.get(text)
                if primary is not None and primary != scene_type:
                    continue
            sources.append(field)
        return sources

    master_terms = (
        "master bedroom", "اتاق خواب مستر", "مستر",
        # ARCHITECTURAL_VISION_GROUNDING_V1 — the frozen alias map
        # already equates these with MASTER_BEDROOM_SLEEPING, and
        # the reported image carries "اتاق والدین" as its own
        # visible label. Without them the space was typed as a
        # generic bedroom, so the ensuite/closet/WC zones were
        # never even expected.
        "اتاق والدین", "اتاق مستر", "بخش خواب مستر",
        "parents room", "parental bedroom", "parent suite",
    )
    master_sources = _positive_sources(master_terms)
    if master_sources:
        return "master bedroom", [
            "explicit master-bedroom terminology (" + ", ".join(master_sources) + ")"
        ]

    large_bed_terms = ("larger bed", "large bed", "تخت بزرگ")
    larger_opening_terms = (
        "larger glazing", "large glazing", "sitting area", "گشودگی بزرگ", "نشیمن"
    )
    large_bed_sources = _positive_sources(large_bed_terms)
    larger_opening_sources = _positive_sources(larger_opening_terms)
    if large_bed_sources and larger_opening_sources:
        sources = []
        for source in large_bed_sources + larger_opening_sources:
            if source not in sources:
                sources.append(source)
        return "master bedroom", [
            "large bed + larger glazing/sitting-area inference ("
            + ", ".join(sources) + ")"
        ]

    if image_type in ("facade or elevation", "facade"):
        return "facade", ["facade/elevation classification (image_type)"]

    facade_sources = _positive_sources(_TYPE_TERMS["facade"])
    if facade_sources:
        return "facade", [
            "facade/elevation classification (" + ", ".join(facade_sources) + ")"
        ]

    # ==================================================
    # FACADE-03D — A VETOED RENDER IS A FACADE, NOT A PLAN
    #
    # `architectural_render_or_photo` is reachable ONLY through the FACADE-03D
    # veto in `_image_type_evidence` (a weak local plan signal contradicted by
    # the model's own facade/render observation). The interior/exterior
    # decision is taken from the AUDITED ARCHITECTURAL_OBSERVATION_V1
    # discriminator — not a new vocabulary — so an INTERIOR render is never
    # called a facade, and the reading keeps its LOW confidence and unknowns.
    # ==================================================
    if image_type in ("architectural render or photo", "facade or elevation"):

        from core.vision.architectural_observation_v1 import (
            build_architectural_observation,
        )

        composition = build_architectural_observation(raw)

        composition_type = str(composition.get("image_type") or "unknown")

        if composition_type in ("exterior", "mixed"):

            return "facade", [
                "exterior composition (ARCHITECTURAL_OBSERVATION_V1: "
                + composition_type + "); weak local plan evidence vetoed"
            ]

    # A visible sleeping element is sufficient for a conservative bedroom
    # interpretation, but not for the stronger master-bedroom label.
    bedroom_token_sources = _positive_sources(("bedroom", "اتاق خواب"))
    sleeping_sources = _positive_sources(("bed", "تخت"))
    if bedroom_token_sources:
        return "bedroom", [
            "bedroom from space-type token ("
            + ", ".join(bedroom_token_sources) + ")"
        ]
    if sleeping_sources:
        if "observed" in sleeping_sources:
            return "bedroom", ["sleeping element"]
        return "bedroom", [
            "bedroom from sleeping element ("
            + ", ".join(sleeping_sources) + ")"
        ]

    for candidate in ("living room", "kitchen", "bathroom", "corridor", "balcony", "entrance", "garden"):
        # VISION_SPACE_TYPE_SUBJECT_ROLE_SAFETY_V1 — the scene type must be
        # the element's own primary kind, not a term merely mentioned inside
        # another element's description.
        sources = _positive_sources(_TYPE_TERMS[candidate], scene_type=candidate)
        if sources:
            return candidate, [
                "space-type token classification ("
                + ", ".join(sources) + ")"
            ]

    return "unknown", []



def _confidence(raw: Dict[str, Any], space_type: str, observed: List[str]) -> str:
    value = _text(raw.get("confidence")).upper()
    if value not in ("LOW", "MEDIUM", "HIGH"):
        value = "LOW"
    if space_type == "unknown" or not observed:
        return "LOW"
    if space_type in ("master bedroom", "bedroom") and len(observed) >= 2 and value == "LOW":
        return "MEDIUM"
    return value


def _append_unique(target: List[str], *values: str) -> None:
    for value in values:
        if value and value not in target:
            target.append(value)


# ==========================================================
# ARCHITECTURAL_VISION_GROUNDING_V1
#
# The evidence-discipline layer. It never invents an element and never
# invents an absence: every element carries the evidence it was claimed
# with, and anything unsupported stays unknown.
# ==========================================================

def _ground(raw: Dict[str, Any], space_type: str, user_text: str):
    """The grounding contract for this payload, or None."""

    try:

        from core.vision.architectural_vision_grounding_v1 import (
            ground_vision_evidence,
        )

        return ground_vision_evidence(
            raw,
            user_text=user_text,
            space_type=space_type,
        )

    except Exception:

        return None


def _grounded_phrases(grounding) -> List[str]:
    """The architectural phrases of the GROUNDED visible elements."""

    try:

        from core.vision.architectural_vision_grounding_v1 import (
            visible_phrases,
        )

        return visible_phrases(grounding)

    except Exception:

        return []


def _likely_phrases(grounding) -> List[str]:
    """The architectural phrases of the GROUNDED LIKELY elements.

    ARCHITECTURAL_VISION_OBSERVATION_V2 — an element the provider NAMED
    (a readable plan label, or a visible relation between two spaces) but
    did not observe as an object.
    """

    try:

        from core.vision.architectural_vision_grounding_v1 import (
            likely_phrases,
        )

        return likely_phrases(grounding)

    except Exception:

        return []


def phrase_for(element_id: str) -> str:
    """The published phrase of an element id."""

    try:

        from core.vision.architectural_vision_grounding_v1 import ELEMENTS

        return (ELEMENTS.get(element_id) or {}).get("phrase") or str(element_id)

    except Exception:

        return str(element_id)


_PRIVATE_ZONES = (
    ("bathroom_or_ensuite", "private bathroom connection"),
    ("wardrobe_or_closet", "dressing or closet zone"),
)


def _private_zone_lines(grounding, observed: List[str], space_type: str):
    """What to say about the private zones of a bedroom.

    Without grounding: the historical lines (kept reachable verbatim).
    With grounding: the GROUNDED status — a zone that was observed is not
    announced as "not visible" any more, and a zone that was never
    reported is `unknown`, never absent.
    """

    if not isinstance(grounding, dict):

        return (
            "private bathroom connection is not visible",
            "dressing or closet zone is not visible",
        )

    statuses = {
        entry.get("element"): entry.get("status")
        for entry in grounding.get("elements") or []
    }

    lines = []

    for element_id, label in _PRIVATE_ZONES:

        status = statuses.get(element_id)

        if status == "visible":

            continue

        # ARCHITECTURAL_VISION_OBSERVATION_V2 — an element the provider
        # NAMED (a readable plan label, a visible relation) is reported,
        # not missing. Saying "not reported" about a zone the plan itself
        # labels would be a false negative of exactly the kind this phase
        # removes.
        if status == "likely":

            lines.append(
                "the " + label + " is named by the visible evidence (likely)"
            )

            continue

        if status == "denied":

            lines.append(
                "the visible evidence states that the " + label
                + " is not visible"
            )

        elif status in ("unverified", "symbol_reading"):

            lines.append(
                "the " + label + " is reported without sufficient visible"
                + " evidence (unverified)"
            )

        else:

            lines.append(
                "the " + label + " is not reported in the visible evidence"
                + " (unknown, not absent)"
            )

    return tuple(lines)


class ArchitecturalVisionInterpreterV1:
    """Deterministic, read-only projection of validated vision evidence.

    ARCHITECTURAL_VISION_GROUNDING_V1 — when `ground` is on (the default),
    the published `observed_elements` are the elements that passed the
    evidence grounding in `architectural_vision_grounding_v1`: an element
    is visible only when the provider's OBSERVATION field states it as an
    object. A plan-symbol reading or a bare entry in the provider's
    element list stays `unverified`, and an element that was never
    reported is `not_reported` — unknown, never absent.

    `ground=False` keeps the historical behaviour reachable, byte for
    byte, for any caller that still wants it.
    """

    CONTRACT = CONTRACT
    VERSION = VERSION

    def interpret(self, understanding: Any, user_text: str = "",
                  ground: bool = True) -> Dict[str, Any]:
        raw = understanding if isinstance(understanding, dict) else {}

        # ==================================================
        # ARCHITECTURAL_OBSERVATION_V1 — PASS-THROUGH FIRST
        #
        # The visible evidence is captured and published BEFORE any
        # interpretation runs. Nothing below this point can delete it.
        #
        # Observation = "what is visible"   (this contract)
        # Interpretation = "what it may mean" (everything below)
        # The two are never merged: the observation block performs no space
        # classification and no function assignment.
        # ==================================================
        architectural_observation = build_architectural_observation(
            raw,
            provider=raw.get("provider") or "unknown",
            model=raw.get("model") or "unknown",
            image_id=raw.get("image_id"),
            source_type=raw.get("source_type") or "other",
        )
        evidence_raw = _provider_evidence_for_local_plan(raw)
        visible_observations = visible_observations_passthrough(
            evidence_raw, architectural_observation
        )

        # The space type is read from the RAW evidence, so grounding an
        # element list can never change what kind of space this is.
        #
        # VISION_SPACE_TYPE_SUBJECT_ROLE_SAFETY_V1 — the audited observation
        # is passed ONLY so a term can be resolved to its ROLE (the element's
        # own primary kind) instead of being read as the scene. It adds no
        # evidence: every citation still comes from `evidence_raw`.
        legacy_observed = _architectural_observations(evidence_raw)
        space_type, basis = _space_type_basis(
            evidence_raw, legacy_observed, user_text,
            observation=architectural_observation,
        )

        grounding = _ground(evidence_raw, space_type, user_text) if ground else None
        grounding = _apply_local_opening_grounding(
            grounding, raw.get("local_plan_reading")
        )

        # VISION_OBSERVATION_MODE_SEPARATION_V1 — brief rule 2: a single
        # bed is NOT a master bedroom. The stronger label needs the
        # sleeping element PLUS at least two GROUNDED suite elements.
        if space_type == "bedroom" and grounding:

            suite = _master_suite_sources(grounding)

            if len(suite) >= 2:

                space_type = "master bedroom"
                basis = ["grounding-bounded suite upgrade", "sleeping element"] + suite

                # The expected set follows the UPGRADED type, so the
                # ensuite/closet/WC expectations match the classification.
                grounding = _ground(raw, space_type, user_text)

        # ARCHITECTURAL_VISION_OBSERVATION_V2 — the published element list
        # carries the OBSERVED elements AND the LIKELY ones, in that order,
        # so an element the provider NAMED (a readable plan label, a
        # visible relation) is never silently dropped. The two tiers stay
        # distinguishable in the grounding and in the report.
        observed = (
            (_grounded_phrases(grounding) + _likely_phrases(grounding))
            if grounding
            else legacy_observed
        )

        confidence = _confidence(raw, space_type, observed)
        evidence = _evidence_text(raw, user_text)

        architectural_interpretation: List[str] = []
        spatial_relations: List[str] = []
        possible_function: List[str] = []
        unknowns: List[str] = []

        # ARCHITECTURAL_VISION_OBSERVATION_V2 — the plan reading, published
        # only for a drawing (set inside the branch below).
        plan_reading: Optional[Dict[str, Any]] = None

        evidence_tiers: Optional[Dict[str, List[str]]] = None

        if space_type == "facade":
            _append_unique(
                architectural_interpretation,
                "The visible composition is interpreted as an exterior facade plane.",
            )
            if "daylight opening visible" in observed or "opening visible" in observed:
                _append_unique(spatial_relations, "Openings are arranged within the visible facade plane.")
            if "projecting outdoor platform visible" in observed:
                _append_unique(spatial_relations, "The projecting outdoor platform is connected to the facade plane.")
            if "entrance threshold visible" in observed:
                _append_unique(spatial_relations, "The entrance threshold is part of the visible exterior composition.")
            _append_unique(possible_function, "possible building entrance or exterior frontage")
            _append_unique(unknowns, "exact floor count is not determinable from the visible evidence")
            _append_unique(unknowns, "structural system is not determinable from the image")

        elif space_type in ("bedroom", "master bedroom"):
            _append_unique(
                architectural_interpretation,
                "The visible sleeping element supports an enclosed sleeping-space interpretation.",
            )
            if "daylight opening visible" in observed:
                _append_unique(spatial_relations, "The daylight opening is associated with the enclosed sleeping space.")
            if "seating element visible" in observed:
                _append_unique(spatial_relations, "The seating element is located within the same visible room zone.")
            if space_type == "master bedroom":
                _append_unique(possible_function, "possible private couple bedroom")
            else:
                _append_unique(possible_function, "likely bedroom")

            # ARCHITECTURAL_VISION_GROUNDING_V1 — the private zones are
            # reported from their GROUNDED status. The historical lines
            # asserted that they were "not visible" for every bedroom,
            # which contradicted an observed closet and read as a false
            # negative. Without grounding the old wording is kept.
            _append_unique(
                unknowns,
                *_private_zone_lines(grounding, observed, space_type),
            )

        elif space_type == "unknown":
            _append_unique(unknowns, "space type is not determinable from the image")
            _append_unique(unknowns, "functional use is not determinable from the image")
            _append_unique(unknowns, "spatial relations are not determinable from the available evidence")
        else:
            _append_unique(
                architectural_interpretation,
                "The visible elements support a possible " + space_type + " interpretation.",
            )
            _append_unique(possible_function, "possible " + space_type + " function")

        if not observed:
            local_state = (raw.get("local_diagnostics") or {}).get("evidence_state")
            if local_state == "CAPABILITY_UNAVAILABLE":
                reason = "local analysis capability unavailable; image evidence remains unknown"
            elif raw.get("analysis_status") in ("PROVIDER_UNAVAILABLE", "FAILED"):
                reason = "vision provider unavailable or failed; image evidence remains unknown"
            elif local_state == "IMAGE_EVIDENCE_INSUFFICIENT":
                reason = "completed local inspection did not establish grounded architectural evidence"
            elif local_state == "LOCAL_EVIDENCE_PARTIAL":
                reason = "partial local evidence is available; semantic observations remain unknown"
            else:
                reason = "reliable architectural evidence has not been established"
            _append_unique(unknowns, reason)
        if raw.get("unresolved"):
            _append_unique(unknowns, "some provider observations remain unresolved")

        limitations = [
            "interpretation is limited to visible image evidence",
            "observed elements and inferred meanings are kept separate",
            "geometry is non-authoritative",
            "dimensions, hidden geometry, and unseen floors are not inferred",
            "materials and structural systems are not asserted without visible evidence",
        ]

        # ==================================================
        # ARCHITECTURAL_OBSERVATION_V1 — a PLAN is a DRAWING of MANY
        # spaces, never one room. Classifying a whole plan as a single
        # space is the failure this phase removes.
        # ==================================================
        is_drawing = str(raw.get("image_type") or "").lower() in (
            "floor_plan_or_sketch",
            "plan",
            "site_diagram",
            "diagram",
        )

        if is_drawing:

            space_type = "plan"
            basis = ["the image is a drawing of multiple spaces, not one room"]

            architectural_interpretation = [
                line
                for line in architectural_interpretation
                if "possible " not in line
                and "enclosed sleeping-space" not in line
            ]

            _append_unique(
                architectural_interpretation,
                "The image is a plan/drawing: it shows a layout of multiple "
                "spaces rather than a single room.",
            )

            unknowns = [
                item
                for item in unknowns
                if "space type is not determinable" not in str(item)
            ]

            # ==================================================
            # ARCHITECTURAL_VISION_OBSERVATION_V2 — PUBLISH THE PLAN
            #
            # Everything below is ALREADY IN THE OBSERVATION: the readable
            # room labels, the provider's furniture list, its spatial
            # clues and its element list. The old branch dropped all of
            # it — it BLANKED `possible_function` and never filled
            # `spatial_relations`, so a labelled, furnished floor plan
            # answered "not determinable from image" while the evidence
            # sat unread in the same object.
            #
            # This is a projection, not new perception: the two additive
            # V2 layers derive the same reading (`plan_interpretation`).
            # ==================================================
            plan_reading = build_plan_reading(
                architectural_observation,
                grounding=grounding,
            )

            plan_spaces = (
                (plan_reading.get("named_spaces") or [])
                + (plan_reading.get("geometry_spaces") or [])
                + (plan_reading.get("inferred_functions") or [])
            )

            # A plan's spatial relations are the ones the PROVIDER reported
            # between its spaces; the single-room branch's relations were
            # written for one room and do not describe a plan.
            spatial_relations = []

            possible_function = [
                "possible " + entry["space"] + " function"
                for entry in plan_spaces
                if entry.get("space")
            ]

            for relation in plan_reading.get("relations") or []:

                between = relation.get("between") or []

                if relation.get("kind") == "adjacency" and len(between) == 2:

                    _append_unique(
                        spatial_relations,
                        "The visible evidence places " + between[0]
                        + " adjacent to " + between[1] + ".",
                    )

                elif relation.get("kind") == "circulation" and between:

                    _append_unique(
                        spatial_relations,
                        "The visible evidence shows a circulation space ("
                        + between[0] + ").",
                    )

            opening_kinds = {
                opening.get("kind")
                for opening in plan_reading.get("openings") or []
            }

            visible_opening_kinds = {
                opening.get("kind")
                for opening in plan_reading.get("openings") or []
                if opening.get("status") == "visible"
            }

            if "door" in visible_opening_kinds or "entrance" in visible_opening_kinds:

                _append_unique(
                    spatial_relations,
                    "Visible door openings connect the spaces of the plan.",
                )

            if "window" in opening_kinds:

                if "window" in visible_opening_kinds:

                    _append_unique(
                        spatial_relations,
                        "Visible perimeter window openings are grounded by "
                        "local raster geometry.",
                    )

                else:

                    _append_unique(
                        spatial_relations,
                        "Window openings are reported by the provider, but no "
                        "visible opening was grounded.",
                    )

            # ARCHITECTURAL_VISION_EVIDENCE_PRECISION_V1 — only a function
            # supported by a localized symbol AND an independent enclosure
            # may be inferred on a drawing. Provider tokens are insufficient.
            for item in plan_reading.get("inferred_functions") or []:

                space = item.get("space")

                if not space:

                    continue

                _append_unique(
                    possible_function,
                    "possible " + space + " function (visible "
                    + (item.get("evidence") or [""])[0] + ")",
                )

            # ==================================================
            # The three evidence tiers, kept SEPARATE and OUT of the
            # "uncertain" list: OBSERVED, LIKELY (named by a readable
            # label or a visible relation) and UNKNOWN. A plan label is
            # evidence; a plan symbol reading is not; and what the
            # provider never reported stays unknown — never absent.
            # ==================================================
            if isinstance(grounding, dict):

                evidence_tiers = {
                    "observed": _grounded_phrases(grounding),
                    "likely": _likely_phrases(grounding),
                    "unverified": [
                        phrase_for(element_id)
                        for element_id in (
                            (grounding.get("symbol_readings") or [])
                            + (grounding.get("unverified_elements") or [])
                        )
                    ],
                    # UNKNOWN means a zone the space's own corpus expects
                    # and the image never reported. It is NOT a dump of
                    # every element the vocabulary knows about.
                    "unknown": [
                        phrase_for(entry.get("element"))
                        for entry in grounding.get("expected_gaps") or []
                    ],
                }

            # The brief's DO-NOT-INVENT set: stated as UNKNOWN, never
            # guessed and never silently omitted.
            _append_unique(
                unknowns,
                "exact dimensions, room areas, north orientation, materials "
                "and the structural system are not determinable from the "
                "visible evidence",
            )

            for name in plan_reading.get("circulation") or []:

                _append_unique(
                    spatial_relations,
                    "Circulation space named by the plan: " + name + ".",
                )

        result = {
            "contract": CONTRACT,
            "version": VERSION,
            "space_type": space_type,
            # FACADE-03D — the canonical image type is published so the report
            # can say "facade" vs "render/photo" without re-deriving it. It is
            # the SAME value the classification already used; nothing new is
            # asserted here.
            "image_type": _text(raw.get("image_type")),
            "confidence": confidence,
            "observed_elements": observed,
            "architectural_interpretation": architectural_interpretation,
            "spatial_relations": spatial_relations,
            "possible_function": possible_function,
            "unknowns": unknowns,
            "limitations": limitations,
            "geometry_authoritative": False,
            # VISION_OBSERVATION_MODE_SEPARATION_V1 — brief rule 2, made
            # auditable: which evidence sources supported this
            # classification. A single bed is never enough for the master
            # label.
            "classification_basis": basis,
        }

        # ARCHITECTURAL_VISION_OBSERVATION_V2 — the PLAN READING, published
        # for a drawing. It is a projection of the observation (labels,
        # furniture, clues, element list), never a new perception, and it
        # carries no dimension, orientation, material or structure.
        if plan_reading:

            result["plan_reading"] = plan_reading

        if evidence_tiers:

            result["evidence_tiers"] = evidence_tiers

        if grounding:

            result["grounding"] = grounding
            result["unverified_claims"] = [
                phrase_for(element_id)
                for element_id in grounding.get("symbol_readings") or []
            ] + [
                phrase_for(element_id)
                for element_id in grounding.get("unverified_elements") or []
            ]
            result["not_reported_elements"] = [
                phrase_for(element_id)
                for element_id in grounding.get("not_reported_elements") or []
            ]
            result["denied_elements"] = [
                phrase_for(element_id)
                for element_id in grounding.get("denied_elements") or []
            ]
            result["expected_gaps"] = [
                entry.get("element")
                for entry in grounding.get("expected_gaps") or []
            ]
            result["evidence_conflicts"] = grounding.get("conflicts") or []

        # ARCHITECTURAL_UNDERSTANDING_CONTRACT_V1 — transient, additive
        # semantic projection. The existing interpretation and grounding
        # fields remain unchanged; this object is not persisted or promoted.
        result["architectural_understanding"] = (
            build_architectural_understanding(result)
        )
        result["architectural_understanding_v2"] = (
            build_architectural_understanding_v2(result)
        )

        # ==================================================
        # ARCHITECTURAL_OBSERVATION_V1 — published ALONGSIDE the
        # interpretation, never merged with it.
        # ==================================================
        result["architectural_observation"] = architectural_observation
        result["visible_observations"] = visible_observations

        # ==================================================
        # ARCHITECTURAL_KNOWLEDGE_HANDOFF_V1
        #
        # The observation says WHAT is visible; this connects the materials it
        # reports to the EXISTING architectural ontology, so the answer can
        # explain what a term means instead of only listing it.
        #
        # It is published ALONGSIDE the observation, never merged into it, and
        # it never raises the evidence authority: a lookup explains a term, it
        # does not corroborate the image. `verification` stays UNVERIFIED,
        # `authoritative` and `resolves_evidence` stay False.
        # ==================================================
        try:

            from core.vision.observed_material_knowledge_v1 import (
                observed_material_knowledge,
            )

            result["architectural_knowledge"] = observed_material_knowledge(
                architectural_observation
            )

        except Exception as error:

            # Knowledge is an explanation layer; its failure must never break
            # the observation the user is owed.
            result["architectural_knowledge"] = {
                "contract": "ObservedArchitecturalKnowledgeV1",
                "tier": "KNOWLEDGE_LOOKUP",
                "verification": "UNVERIFIED",
                "authoritative": False,
                "resolves_evidence": False,
                "learned": False,
                "materials": [],
                "status": "UNAVAILABLE",
                "error": type(error).__name__,
            }

        # ==================================================
        # ARCHITECTURAL_MATERIAL_KNOWLEDGE_CONNECTION_V1
        #
        # A user-requested material replacement used to remain disconnected
        # from the observed material knowledge published immediately above.
        # Join the two existing owners additively, without merging observation
        # and instruction authority and without exposing an execution route.
        # Non-replacement turns publish no new field, preserving the accepted
        # interpretation contract for those callers.
        # ==================================================
        if str(user_text or "").strip():

            try:

                from core.vision.architectural_material_knowledge_connection_v1 import (
                    build_architectural_material_knowledge_connection,
                )

                material_connection = (
                    build_architectural_material_knowledge_connection(
                        architectural_observation,
                        user_text,
                        observed_knowledge=result["architectural_knowledge"],
                    )
                )

                if material_connection.get("status") != "NO_MATERIAL_REPLACEMENT":

                    result["architectural_material_knowledge_connection"] = (
                        material_connection
                    )

            except Exception as error:

                # This is an additive explanation layer. Its failure cannot
                # remove or upgrade the accepted observation/knowledge.
                result["architectural_material_knowledge_connection"] = {
                    "contract": "ArchitecturalMaterialKnowledgeConnectionV1",
                    "version": "1.0",
                    "status": "UNAVAILABLE",
                    "error": type(error).__name__,
                    "execution_capability": {
                        "status": "NOT_YET_AVAILABLE",
                        "precise_facade_material_transfer": False,
                        "authorized": False,
                    },
                }
        # ARCHITECTURAL_VISUAL_INTERPRETATION_V2 — the meaning layer, built
        # FROM the observation (never from the legacy fields) and published
        # additively. The legacy `space_type` / `observed_elements` /
        # `spatial_relations` above are left byte-identical.
        result["architectural_visual_interpretation_v2"] = (
            build_architectural_visual_interpretation_v2(
                architectural_observation
            )
        )

        # ARCHITECTURAL_SPATIAL_RELATIONSHIP_UNDERSTANDING_V1 — the spatial
        # organization layer, built FROM the observation + the V2
        # interpretation and published additively. Nothing above changes.
        result["architectural_spatial_relationship_understanding_v1"] = (
            build_architectural_spatial_relationship_understanding_v1(
                architectural_observation,
                result["architectural_visual_interpretation_v2"],
            )
        )

        # "Unknown only when evidence is truly absent": an uncertainty the
        # OBSERVATION already answered is not repeated as an unknown.
        if architectural_observation.get("visible_floors"):

            result["unknowns"] = [
                item
                for item in (result.get("unknowns") or [])
                if "floor" not in str(item).lower()
                and "طبقه" not in str(item)
            ]

        if architectural_observation.get("material_observations"):

            result["unknowns"] = [
                item
                for item in (result.get("unknowns") or [])
                if "material" not in str(item).lower()
                and "مصالح" not in str(item)
            ]

        return result


architectural_vision_interpreter = ArchitecturalVisionInterpreterV1()


def interpret_architectural_vision(
    understanding: Any, user_text: str = "", ground: bool = True
) -> Dict[str, Any]:
    return architectural_vision_interpreter.interpret(
        understanding, user_text=user_text, ground=ground
    )
