# -*- coding: utf-8 -*-
"""ARCHITECTURAL_VISUAL_INTERPRETATION_V2

Architectural Observation -> Architectural Meaning.

    Image
      -> ArchitecturalObservationV1          (what is visible)
      -> ArchitecturalVisualInterpretationV2 (what it may mean)   <- this module

CORE RULE
---------
This layer consumes **ArchitecturalObservationV1 as its PRIMARY SOURCE**.
It never rebuilds meaning from the legacy understanding fields. If the
observation does not carry it, this layer does not claim it.

OBSERVATION vs INTERPRETATION
-----------------------------
Observation  = "what is visible"   (the observation contract, unchanged)
Interpretation = "what it may mean" (this contract)

They are never merged: this layer never mutates, drops or rewrites an
observation, and every claim it makes cites the observation phrase it came
from.

WHAT THIS LAYER IS NOT
----------------------
Not design, not generation. It creates no plan, no layout, no geometry, no
SVG/PNG, no CAD/BIM/IFC, and it never renders.

EVERY CLAIM CARRIES
-------------------
    value · evidence[] · confidence · reasoning_source

No invention: a claim with no observation behind it is not emitted.
No absolute style claims: style is reported as INDICATORS with confidence.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


CONTRACT = "ArchitecturalVisualInterpretationV2"
VERSION = "1.0"

OBSERVATION_CONTRACT = "ArchitecturalObservationV1"


# ==========================================================
# image category
# ==========================================================

IMAGE_CATEGORIES = (
    "exterior_facade",
    "interior_space",
    "architectural_plan",
    "diagram",
    "mixed",
    "unknown",
)

_OBSERVATION_IMAGE_TYPE_TO_CATEGORY = {
    "exterior": "exterior_facade",
    "interior": "interior_space",
    "plan": "architectural_plan",
    "diagram": "diagram",
    "mixed": None,          # decided from the evidence below
    "unknown": "unknown",
}

# architectural element kinds that indicate the OUTSIDE of a building
_EXTERIOR_ELEMENT_KINDS = {
    "facade", "balcony", "roof", "louver", "railing", "parapet",
    "canopy", "entrance",
}

# element kinds that indicate an ENCLOSED interior
_INTERIOR_ELEMENT_KINDS = {"ceiling", "wall", "floor"}

_EXTERIOR_TEXT = (
    "facade", "elevation", "exterior", "outside", "outdoor", "roof",
    "balcony", "terrace", "garden", "landscape", "walkway", "street",
    "نما", "بیرونی", "بام", "بالکن", "تراس", "محوطه", "حیاط",
)

_INTERIOR_TEXT = (
    "interior", "indoor", "inside", "ceiling", "room", "furniture",
    "داخلی", "اتاق", "سقف", "مبلمان",
)


# ==========================================================
# building type
# ==========================================================

BUILDING_TYPES = ("residential", "commercial", "mixed_use", "unknown")

_BUILDING_TYPE_MARKERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("mixed_use", (
        "mixed-use", "mixed use", "mixeduse", "چندکاربری", "چند کاربری",
    )),
    ("commercial", (
        "commercial", "office building", "office", "retail", "shop",
        "hotel", "restaurant", "تجاری", "اداری", "فروشگاه", "هتل",
    )),
    ("residential", (
        "residential", "house", "home", "villa", "apartment", "housing",
        "dwelling", "مسکونی", "خانه", "ویلا", "آپارتمان", "منزل",
    )),
)


# ==========================================================
# element -> meaning
# ==========================================================

ELEMENT_MEANINGS: Dict[str, str] = {
    "bed": "sleeping area indicator",
    "sofa": "seating / social area indicator",
    "chair": "seating indicator",
    "table": "dining or work surface indicator",
    "desk": "work surface indicator",
    "wardrobe": "storage / dressing indicator",
    "cabinet": "storage indicator",
    "shelf": "storage indicator",
    "mirror": "dressing / grooming indicator",
    "rug": "floor covering indicator",
    "lamp": "artificial lighting indicator",
    "sanitary": "sanitary zone indicator",
    "counter": "food preparation indicator",
    "screen": "media / entertainment indicator",
    "window": "daylight opening indicator",
    "door": "access / threshold indicator",
    "opening": "aperture indicator",
    "wall": "spatial enclosure indicator",
    "floor": "horizontal surface indicator",
    "ceiling": "overhead surface indicator",
    "roof": "top enclosure indicator",
    "facade": "building envelope indicator",
    "balcony": "outdoor amenity indicator",
    "terrace": "outdoor amenity indicator",
    "stair": "vertical circulation indicator",
    "column": "structural support indicator",
    "beam": "structural span indicator",
    "arch": "curved opening indicator",
    "railing": "edge protection indicator",
    "louver": "screening / shading indicator",
    "canopy": "shading indicator",
    "corridor": "circulation indicator",
    "ramp": "graded access indicator",
    "parapet": "roof edge indicator",
    "entrance": "arrival / access indicator",
    "plant": "landscape indicator",
    "walkway": "pedestrian access indicator",
    "vehicle": "vehicle access indicator",
    "water_feature": "water feature indicator",
    "fence": "boundary indicator",
    "dimension_line": "drawing annotation indicator",
    "text_label": "annotation indicator",
}


# ==========================================================
# ARCHITECTURAL VISUAL MEANING EXTENSION V1
#
# A deeper, PROBABILISTIC architectural profile per element kind.
#
# RULES
#   * probabilistic: every role is an INDICATOR and every relationship is
#     POSSIBLE. No element ever becomes an architectural absolute.
#   * a relationship is a CANDIDATE. It is emitted ONLY when its co-evidence
#     is actually visible in the observation. With no evidence the
#     relationship is EMPTY — never inferred.
#   * `candidate_relationships` is a tuple of (relationship, required_kinds).
#     An EMPTY `required_kinds` means the relationship needs no co-evidence.
# ==========================================================

ELEMENT_ARCHITECTURAL_PROFILES: Dict[str, Dict[str, Any]] = {

    # ---------------- private / sleeping ----------------
    "bed": {
        "function": "sleeping",
        "architectural_role": "private_space_indicator",
        "context": ("bedroom", "master_bedroom"),
        "exceptions": (
            "a bed is not exclusive to a dwelling (hotel, hospital, dormitory)",
        ),
        "candidate_relationships": (
            # privacy is established by a CONTROLLED ACCESS — without a
            # visible entrance/door there is no privacy evidence at all
            ("privacy", ("entrance", "door")),
            ("entrance_visibility", ("entrance", "door")),
            ("daylight", ("window", "opening")),
            ("circulation", ("corridor", "stair", "ramp", "door")),
        ),
    },
    "wardrobe": {
        "function": "storage / dressing",
        "architectural_role": "support_private_space",
        "context": ("bedroom", "master_bedroom", "dressing_room"),
        "exceptions": (
            "a wardrobe also appears in an entrance hall or a utility room",
        ),
        "candidate_relationships": (
            ("connection_with_bathroom", ("sanitary",)),
            ("dressing_sequence", ("bed",)),
            ("privacy", ("entrance", "door")),
        ),
    },
    "cabinet": {
        "function": "storage",
        "architectural_role": "support_private_space",
        "context": ("bedroom", "kitchen", "utility"),
        "exceptions": ("cabinetry also appears in public and service spaces",),
        "candidate_relationships": (
            ("storage_sequence", ("counter",)),
        ),
    },
    "shelf": {
        "function": "storage / display",
        "architectural_role": "support_space",
        "context": ("living_room", "study", "bedroom"),
        "exceptions": ("open shelving is not a closed storage volume",),
        "candidate_relationships": (
            ("storage_sequence", ("counter", "cabinet")),
        ),
    },
    "mirror": {
        "function": "dressing / grooming",
        "architectural_role": "support_private_space",
        "context": ("bedroom", "dressing_room", "bathroom"),
        "exceptions": ("a mirror may be purely decorative",),
        "candidate_relationships": (
            ("dressing_sequence", ("wardrobe", "cabinet")),
            ("daylight", ("window",)),
        ),
    },

    # ---------------- social / living ----------------
    "sofa": {
        "function": "seating / social",
        "architectural_role": "social_space_indicator",
        "context": ("living_room", "lounge"),
        "exceptions": ("a sofa also appears in a lobby or a waiting area",),
        "candidate_relationships": (
            ("seating_group", ("chair", "table")),
            ("daylight", ("window", "opening")),
            ("circulation", ("corridor", "door", "opening")),
        ),
    },
    "chair": {
        "function": "seating",
        "architectural_role": "support_space",
        "context": ("living_room", "dining", "study"),
        "exceptions": ("a chair is not by itself a space indicator",),
        "candidate_relationships": (
            ("seating_group", ("table", "sofa")),
        ),
    },
    "table": {
        "function": "dining / work surface",
        "architectural_role": "support_space",
        "context": ("dining", "living_room", "study"),
        "exceptions": ("a table may be a work, dining or display surface",),
        "candidate_relationships": (
            ("seating_group", ("chair", "sofa")),
            ("daylight", ("window",)),
        ),
    },
    "desk": {
        "function": "work surface",
        "architectural_role": "support_space",
        "context": ("study", "bedroom", "office"),
        "exceptions": ("a desk also appears in a shared workspace",),
        "candidate_relationships": (
            ("seating_group", ("chair",)),
            ("daylight", ("window",)),
        ),
    },
    "screen": {
        "function": "media / entertainment",
        "architectural_role": "support_space",
        "context": ("living_room", "bedroom"),
        "exceptions": ("a screen may be a monitor rather than a television",),
        "candidate_relationships": (
            ("seating_group", ("sofa", "chair")),
        ),
    },
    "rug": {
        "function": "floor covering",
        "architectural_role": "support_space",
        "context": ("living_room", "bedroom"),
        "exceptions": ("a rug is not a spatial boundary",),
        "candidate_relationships": (
            ("seating_group", ("sofa", "chair", "table")),
        ),
    },
    "lamp": {
        "function": "artificial lighting",
        "architectural_role": "environmental_element",
        "context": ("any_space",),
        "exceptions": ("a lamp is not a substitute for a daylight opening",),
        "candidate_relationships": (
            ("room_quality", ("bed", "sofa", "counter")),
        ),
    },

    # ---------------- service / sanitary ----------------
    "sanitary": {
        "function": "sanitary / hygiene",
        "architectural_role": "service_space_indicator",
        "context": ("bathroom", "wc"),
        "exceptions": ("a sanitary fixture may sit in a shared or public facility",),
        "candidate_relationships": (
            ("privacy", ("entrance", "door")),
            ("wet_zone_sequence", ("counter", "wardrobe")),
            ("ventilation", ("window", "opening")),
        ),
    },
    "counter": {
        "function": "food preparation",
        "architectural_role": "service_space_indicator",
        "context": ("kitchen", "utility"),
        "exceptions": ("a counter also appears in a bathroom or a workshop",),
        "candidate_relationships": (
            ("work_sequence", ("cabinet", "shelf")),
            ("daylight", ("window",)),
            ("ventilation", ("window", "opening")),
        ),
    },

    # ---------------- envelope / openings ----------------
    "window": {
        "function": "daylight / ventilation",
        "architectural_role": "environmental_element",
        "context": ("any_space",),
        "exceptions": ("a window may be a fixed pane with no ventilation",),
        "candidate_relationships": (
            # a daylight opening intrinsically carries a daylight relation
            ("natural_light", ()),
            ("room_quality", ("bed", "sofa", "counter", "table", "desk")),
            ("privacy_control", ("bed", "sanitary")),
        ),
    },
    "door": {
        "function": "access",
        "architectural_role": "circulation_bearing",
        "context": ("any_space",),
        "exceptions": ("a door may be a cabinet front rather than a room access",),
        "candidate_relationships": (
            ("access_control", ()),
            ("circulation", ("corridor", "stair", "ramp")),
            ("privacy", ("bed", "sanitary")),
        ),
    },
    "opening": {
        "function": "aperture / connection",
        "architectural_role": "circulation_bearing",
        "context": ("any_space",),
        "exceptions": ("an opening may be a structural recess, not a passage",),
        "candidate_relationships": (
            ("spatial_connection", ()),
            ("daylight", ("window",)),
            ("circulation", ("corridor", "door")),
        ),
    },
    "entrance": {
        "function": "arrival / access",
        "architectural_role": "circulation_bearing",
        "context": ("entrance_hall", "exterior_facade"),
        "exceptions": ("a threshold may be a secondary or service entry",),
        "candidate_relationships": (
            ("access_control", ()),
            ("circulation", ("corridor", "stair", "ramp")),
            ("privacy", ("bed", "sanitary")),
        ),
    },
    "wall": {
        "function": "enclosure / separation",
        "architectural_role": "spatial_enclosure",
        "context": ("any_space",),
        "exceptions": ("a wall may be a partition or a free-standing screen",),
        "candidate_relationships": (
            ("spatial_separation", ()),
            ("privacy", ("bed", "sanitary")),
        ),
    },
    "floor": {
        "function": "horizontal surface",
        "architectural_role": "spatial_enclosure",
        "context": ("any_space",),
        "exceptions": ("a floor plane may be an outdoor deck",),
        "candidate_relationships": (
            ("level_surface", ()),
        ),
    },
    "ceiling": {
        "function": "overhead surface",
        "architectural_role": "spatial_enclosure",
        "context": ("interior_space",),
        "exceptions": ("a ceiling may be an exposed structure",),
        "candidate_relationships": (
            ("enclosure", ()),
        ),
    },
    "roof": {
        "function": "top enclosure",
        "architectural_role": "envelope",
        "context": ("exterior_facade",),
        "exceptions": ("a roof may be a roof terrace",),
        "candidate_relationships": (
            ("envelope_composition", ("facade",)),
        ),
    },
    "facade": {
        "function": "building envelope",
        "architectural_role": "envelope",
        "context": ("exterior_facade",),
        "exceptions": ("a visible plane may be a party wall, not the frontage",),
        "candidate_relationships": (
            ("envelope_composition", ()),
            ("opening_composition", ("window", "opening", "balcony")),
        ),
    },
    "balcony": {
        "function": "outdoor amenity",
        "architectural_role": "amenity",
        "context": ("exterior_facade", "living_room", "bedroom"),
        "exceptions": ("a projecting platform may be a service ledge",),
        "candidate_relationships": (
            ("indoor_outdoor_connection", ("door", "window", "opening")),
            ("envelope_composition", ("facade",)),
        ),
    },
    "terrace": {
        "function": "outdoor amenity",
        "architectural_role": "amenity",
        "context": ("exterior_facade", "ground_floor"),
        "exceptions": ("a terrace may be a shared or public surface",),
        "candidate_relationships": (
            ("indoor_outdoor_connection", ("door", "window", "opening")),
        ),
    },
    "canopy": {
        "function": "shading",
        "architectural_role": "environmental_element",
        "context": ("exterior_facade",),
        "exceptions": ("a canopy may be a decorative projection",),
        "candidate_relationships": (
            ("envelope_composition", ("facade",)),
            ("solar_control", ("window", "opening")),
        ),
    },
    "louver": {
        "function": "screening / shading",
        "architectural_role": "environmental_element",
        "context": ("exterior_facade", "interior_space"),
        "exceptions": ("louvers may be purely compositional",),
        "candidate_relationships": (
            ("solar_control", ("window", "opening")),
            ("privacy_control", ("bed", "sanitary")),
            ("envelope_composition", ("facade",)),
        ),
    },
    "railing": {
        "function": "edge protection",
        "architectural_role": "safety_element",
        "context": ("balcony", "stair", "terrace"),
        "exceptions": ("a railing may be a decorative balustrade",),
        "candidate_relationships": (
            ("edge_protection", ()),
            ("vertical_connection", ("stair", "ramp")),
        ),
    },
    "parapet": {
        "function": "roof edge",
        "architectural_role": "envelope",
        "context": ("exterior_facade",),
        "exceptions": ("a parapet may conceal roof services",),
        "candidate_relationships": (
            ("envelope_composition", ("facade", "roof")),
        ),
    },

    # ---------------- circulation / structure ----------------
    "stair": {
        "function": "vertical circulation",
        "architectural_role": "circulation_bearing",
        "context": ("any_space", "multi_level"),
        "exceptions": ("a stair may be an exterior or fire escape",),
        "candidate_relationships": (
            ("vertical_connection", ()),
            ("circulation", ("corridor", "door", "opening")),
        ),
    },
    "corridor": {
        "function": "circulation",
        "architectural_role": "circulation_bearing",
        "context": ("any_space",),
        "exceptions": ("a corridor may be an external walkway",),
        "candidate_relationships": (
            ("circulation", ()),
            ("access_distribution", ("door", "opening", "entrance")),
        ),
    },
    "ramp": {
        "function": "graded access",
        "architectural_role": "circulation_bearing",
        "context": ("exterior_facade", "entrance_hall"),
        "exceptions": ("a ramp may be a vehicle ramp",),
        "candidate_relationships": (
            ("accessible_access", ()),
            ("circulation", ("entrance", "door")),
        ),
    },
    "column": {
        "function": "structural support",
        "architectural_role": "structural",
        "context": ("any_space",),
        "exceptions": ("a visible vertical may be a service duct",),
        "candidate_relationships": (
            ("structural_expression", ()),
        ),
    },
    "beam": {
        "function": "structural span",
        "architectural_role": "structural",
        "context": ("any_space",),
        "exceptions": ("a horizontal element may be a suspended ceiling",),
        "candidate_relationships": (
            ("structural_expression", ("column",)),
        ),
    },
    "arch": {
        "function": "curved opening",
        "architectural_role": "envelope",
        "context": ("exterior_facade", "interior_space"),
        "exceptions": ("an arch may be a decorative recess",),
        "candidate_relationships": (
            ("opening_composition", ("door", "window", "opening")),
            ("envelope_composition", ("facade",)),
        ),
    },

    # ---------------- landscape / context ----------------
    "plant": {
        "function": "landscape",
        "architectural_role": "landscape_element",
        "context": ("exterior_facade", "interior_space"),
        "exceptions": ("a plant may be a potted interior object",),
        "candidate_relationships": (
            ("landscape_setting", ("walkway", "fence")),
        ),
    },
    "walkway": {
        "function": "pedestrian access",
        "architectural_role": "circulation_bearing",
        "context": ("exterior_facade",),
        "exceptions": ("a walkway may be a public pavement",),
        "candidate_relationships": (
            ("approach_sequence", ("entrance", "door")),
            ("landscape_setting", ("plant",)),
        ),
    },
    "vehicle": {
        "function": "vehicle access",
        "architectural_role": "circulation_bearing",
        "context": ("exterior_facade", "parking"),
        "exceptions": ("a vehicle is a transient object, not a building element",),
        "candidate_relationships": (
            ("vehicle_access", ("entrance", "opening")),
        ),
    },
    "water_feature": {
        "function": "water amenity",
        "architectural_role": "amenity",
        "context": ("exterior_facade",),
        "exceptions": ("a water surface may be a reflection, not a pool",),
        "candidate_relationships": (
            ("landscape_setting", ("plant", "walkway")),
        ),
    },
    "fence": {
        "function": "boundary",
        "architectural_role": "envelope",
        "context": ("exterior_facade",),
        "exceptions": ("a boundary may be a low visual screen",),
        "candidate_relationships": (
            ("site_boundary", ("walkway", "entrance")),
        ),
    },

    # ---------------- drawing annotations ----------------
    "dimension_line": {
        "function": "drawing annotation",
        "architectural_role": "annotation",
        "context": ("architectural_plan",),
        "exceptions": ("a dimension line is a drawing artefact, not a building element",),
        "candidate_relationships": (),
    },
    "text_label": {
        "function": "annotation / readable label",
        "architectural_role": "annotation",
        "context": ("architectural_plan",),
        "exceptions": ("a label may be a watermark or a drawing title",),
        "candidate_relationships": (),
    },
}


# ==========================================================
# space understanding
# ==========================================================

SPACE_UNDERSTANDINGS = (
    "bedroom", "master bedroom", "living room", "kitchen", "bathroom",
    "circulation", "facade", "unknown",
)

# the suite elements that support a MASTER-bedroom possibility
_SUITE_KINDS = ("wardrobe", "sanitary", "cabinet", "shelf")


# ==========================================================
# spatial relationships
# ==========================================================

RELATIONSHIP_KINDS = (
    "adjacency",
    "separation",
    "circulation_path",
    "privacy_clue",
    "visibility",
)

# observation spatial_clue kind -> relationship kind
_CLUE_TO_RELATIONSHIP = {
    "adjacency": "adjacency",
    "access": "circulation_path",
    "visibility": "visibility",
    "circulation": "circulation_path",
}


# ==========================================================
# plan interpretation
# ==========================================================

# readable plan label -> (space name, zone)
PLAN_LABEL_MEANINGS: Dict[str, Tuple[str, str]] = {
    "اتاق خواب": ("bedroom", "private"),
    "اتاق خواب مستر": ("master bedroom", "private"),
    "اتاق والدین": ("master bedroom", "private"),
    "bedroom": ("bedroom", "private"),
    "نشیمن": ("living room", "public"),
    "پذیرایی": ("living room", "public"),
    "living room": ("living room", "public"),
    "آشپزخانه": ("kitchen", "service"),
    "kitchen": ("kitchen", "service"),
    "حمام": ("bathroom", "service"),
    "bathroom": ("bathroom", "service"),
    "سرویس": ("wc", "service"),
    "wc": ("wc", "service"),
    "دستشویی": ("wc", "service"),
    "دالان": ("corridor", "circulation"),
    "راهرو": ("corridor", "circulation"),
    "corridor": ("corridor", "circulation"),
    "آبدارخانه": ("pantry", "service"),
    "انبار": ("storage", "service"),
    "پارکینگ": ("parking", "service"),
    "parking": ("parking", "service"),
    "تراس": ("terrace", "semi_public"),
    "بالکن": ("balcony", "semi_public"),
    "بالکن/تراس": ("balcony", "semi_public"),
    "ورودی": ("entrance", "public"),
    "entrance": ("entrance", "public"),
    "حیاط": ("courtyard", "semi_public"),
}

ZONES = ("public", "semi_public", "private", "service", "circulation")


# ==========================================================
# helpers
# ==========================================================

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


def _claim(
    value: Any,
    evidence: List[str],
    confidence: str,
    reasoning_source: str,
) -> Dict[str, Any]:

    """Every interpretation claim carries evidence + confidence + source."""

    return {
        "value": value,
        "evidence": [e for e in evidence if e],
        "confidence": confidence,
        "reasoning_source": reasoning_source,
    }


def _observation_phrases(observation: Dict[str, Any]) -> List[str]:

    """Every phrase the observation carries (never re-derived from legacy)."""

    phrases: List[str] = []

    for bucket in (
        "architectural_elements",
        "furniture_elements",
        "object_elements",
        "unclassified_observations",
    ):

        for entry in observation.get(bucket) or []:

            phrase = entry.get("evidence_phrase")

            if phrase and phrase not in phrases:

                phrases.append(phrase)

    for entry in observation.get("material_observations") or []:

        phrase = entry.get("descriptor") or entry.get("evidence_phrase")

        if phrase and phrase not in phrases:

            phrases.append(phrase)

    for entry in observation.get("texture_color_observations") or []:

        phrase = entry.get("descriptor") or entry.get("evidence_phrase")

        if phrase and phrase not in phrases:

            phrases.append(phrase)

    for entry in observation.get("style_indicators") or []:

        phrase = entry.get("descriptor") or entry.get("evidence_phrase")

        if phrase and phrase not in phrases:

            phrases.append(phrase)

    for entry in observation.get("spatial_clues") or []:

        phrase = entry.get("evidence_phrase")

        if phrase and phrase not in phrases:

            phrases.append(phrase)

    for phrase in observation.get("text_labels_if_visible") or []:

        if phrase not in phrases:

            phrases.append(phrase)

    return phrases


def _element_kinds(observation: Dict[str, Any]) -> Dict[str, List[str]]:

    """kind -> the observation phrases that carried it."""

    kinds: Dict[str, List[str]] = {}

    for bucket in ("architectural_elements", "furniture_elements", "object_elements"):

        for entry in observation.get(bucket) or []:

            phrase = entry.get("evidence_phrase") or ""

            for kind in entry.get("kind") or []:

                kinds.setdefault(kind, [])

                if phrase and phrase not in kinds[kind]:

                    kinds[kind].append(phrase)

    return kinds


# ==========================================================
# 1. image category
# ==========================================================

def _image_category(observation: Dict[str, Any]) -> Dict[str, Any]:

    obs_type = _norm(observation.get("image_type"))

    mapped = _OBSERVATION_IMAGE_TYPE_TO_CATEGORY.get(obs_type)

    evidence: List[str] = ["observation.image_type = " + (obs_type or "unknown")]

    if mapped:

        confidence = "HIGH" if obs_type in ("interior", "exterior", "plan") else "LOW"

        return _claim(mapped, evidence, confidence, "observation.image_type")

    # `mixed` — decide from the observation's own evidence
    kinds = _element_kinds(observation)

    phrases = _observation_phrases(observation)

    exterior_hits: List[str] = []

    interior_hits: List[str] = []

    for kind in _EXTERIOR_ELEMENT_KINDS:

        if kind in kinds:

            exterior_hits.extend(kinds[kind])

    for kind in _INTERIOR_ELEMENT_KINDS:

        if kind in kinds:

            interior_hits.extend(kinds[kind])

    for phrase in phrases:

        low = _norm(phrase)

        if any(_norm(m) in low for m in _EXTERIOR_TEXT):

            exterior_hits.append(phrase)

        if any(_norm(m) in low for m in _INTERIOR_TEXT):

            interior_hits.append(phrase)

    if observation.get("visible_floors"):

        exterior_hits.append(
            "visible_floors: " + str(observation["visible_floors"].get("evidence_phrase"))
        )

    # furniture seen THROUGH glazing is weak interior evidence; a facade /
    # balcony / roof / floor count is strong exterior evidence.
    exterior_score = len(set(exterior_hits))

    interior_score = len(set(interior_hits)) * 0.5

    if exterior_score > interior_score and exterior_score > 0:

        evidence.extend(sorted(set(exterior_hits))[:6])

        return _claim(
            "exterior_facade",
            evidence,
            "MEDIUM",
            "observation evidence: exterior elements outweigh interior elements",
        )

    if interior_score > exterior_score and interior_score > 0:

        evidence.extend(sorted(set(interior_hits))[:6])

        return _claim(
            "interior_space",
            evidence,
            "MEDIUM",
            "observation evidence: interior elements outweigh exterior elements",
        )

    return _claim("mixed", evidence, "LOW", "observation evidence is balanced")


# ==========================================================
# 2. architectural meaning
# ==========================================================

def _building_type(observation: Dict[str, Any]) -> Dict[str, Any]:

    phrases = _observation_phrases(observation)

    # the observation preserves the provider output verbatim — its
    # `inferred` claims are legitimate EVIDENCE for a POSSIBILITY.
    raw = observation.get("raw_observations") or {}

    for key in ("observed", "inferred", "architectural_elements"):

        for phrase in _as_list(raw.get(key)):

            if phrase not in phrases:

                phrases.append(phrase)

    for value in (raw.get("building_type"),):

        if value:

            phrases.append(_text(value))

    hits: Dict[str, List[str]] = {}

    for building, markers in _BUILDING_TYPE_MARKERS:

        for phrase in phrases:

            low = _norm(phrase)

            if any(_norm(m) in low for m in markers):

                hits.setdefault(building, [])

                if phrase not in hits[building]:

                    hits[building].append(phrase)

    if not hits:

        return _claim("unknown", [], "LOW", "no building-type evidence in the observation")

    # mixed_use / commercial outrank residential when both appear
    for building in ("mixed_use", "commercial", "residential"):

        if building in hits:

            return _claim(
                building,
                hits[building][:4],
                "LOW",  # a POSSIBILITY, never an assertion
                "observation phrases naming a building type",
            )

    return _claim("unknown", [], "LOW", "no building-type evidence in the observation")


def _space_understanding(
    observation: Dict[str, Any],
    kinds: Dict[str, List[str]],
    category: str = "",
) -> Dict[str, Any]:

    has = lambda kind: kind in kinds  # noqa: E731

    # On an EXTERIOR view the reading is the building envelope. Furniture
    # seen THROUGH glazing must not turn a facade into a living room.
    if category == "exterior_facade":

        return _claim(
            "facade",
            [
                phrase
                for kind in ("facade", "balcony", "roof", "louver", "railing", "canopy")
                for phrase in kinds.get(kind, [])
            ][:5],
            "MEDIUM",
            "image category is exterior_facade; envelope elements are the subject",
        )

    def ev(*names: str) -> List[str]:

        out: List[str] = []

        for name in names:

            for phrase in kinds.get(name, []):

                if phrase not in out:

                    out.append(phrase)

        return out

    # a plan is not one space
    if _norm(observation.get("image_type")) == "plan":

        return _claim(
            "unknown",
            ["observation.image_type = plan"],
            "LOW",
            "a plan is a drawing of many spaces, not one space",
        )

    suite = [name for name in _SUITE_KINDS if has(name)]

    if has("bed") and has("sanitary") and len(suite) >= 1:

        return _claim(
            "master bedroom",
            ev("bed", "sanitary", "wardrobe", "cabinet", "shelf"),
            "LOW",
            "observation evidence: sleeping + sanitary + storage elements",
        )

    if has("bed"):

        return _claim(
            "bedroom",
            ev("bed"),
            "MEDIUM",
            "observation evidence: sleeping element",
        )

    if has("sanitary") and not has("sofa") and not has("bed"):

        return _claim(
            "bathroom",
            ev("sanitary"),
            "MEDIUM",
            "observation evidence: sanitary element",
        )

    if has("counter") or has("kitchen"):

        return _claim(
            "kitchen",
            ev("counter", "kitchen"),
            "MEDIUM",
            "observation evidence: food-preparation element",
        )

    if has("sofa") or has("seating"):

        return _claim(
            "living room",
            ev("sofa", "seating", "chair"),
            "LOW",
            "observation evidence: seating element",
        )

    if has("corridor") or has("stair") or has("ramp"):

        return _claim(
            "circulation",
            ev("corridor", "stair", "ramp"),
            "MEDIUM",
            "observation evidence: circulation element",
        )

    if has("facade") or has("balcony") or has("roof"):

        return _claim(
            "facade",
            ev("facade", "balcony", "roof", "louver", "railing"),
            "MEDIUM",
            "observation evidence: building-envelope elements",
        )

    return _claim(
        "unknown",
        [],
        "LOW",
        "no space evidence in the observation",
    )


# ==========================================================
# 3. element meaning
# ==========================================================

def _element_relationships(
    kind: str,
    profile: Dict[str, Any],
    kinds: Dict[str, List[str]],
    phrases: List[str],
    observed_phrases: List[str],
) -> List[Dict[str, Any]]:

    """The POSSIBLE relationships for one element.

    A relationship is emitted ONLY when its co-evidence is actually visible.
    With no evidence it is EMPTY — never inferred (rule 3).
    """

    relationships: List[Dict[str, Any]] = []

    for name, requires in profile.get("candidate_relationships") or ():

        if requires:

            present = [required for required in requires if required in kinds]

            if not present:

                # no evidence for this relationship -> do not emit it
                continue

            evidence: List[str] = []

            for phrase in phrases:

                if phrase not in evidence:

                    evidence.append(phrase)

            for required in present:

                for phrase in kinds.get(required) or []:

                    if phrase not in evidence:

                        evidence.append(phrase)

            confidence = (
                "MEDIUM"
                if any(phrase in observed_phrases for phrase in evidence)
                else "LOW"
            )

            source = "observation evidence: %s + %s" % (
                kind, ", ".join(present)
            )

        else:

            evidence = list(phrases)

            confidence = (
                "MEDIUM"
                if any(phrase in observed_phrases for phrase in evidence)
                else "LOW"
            )

            source = "observation evidence: %s (intrinsic to the element)" % kind

        relationships.append({
            "relationship": name,
            "evidence": evidence,
            "confidence": confidence,
            "reasoning_source": source,
        })

    return relationships


def _element_meaning(
    observation: Dict[str, Any],
    kinds: Dict[str, List[str]],
    image_category: str = "",
) -> List[Dict[str, Any]]:

    meanings: List[Dict[str, Any]] = []

    observed_phrases = (observation.get("raw_observations") or {}).get("observed", [])

    for kind in sorted(kinds):

        meaning = ELEMENT_MEANINGS.get(kind)

        if not meaning:

            continue

        phrases = kinds[kind]

        confidence = "MEDIUM" if any(
            phrase in observed_phrases for phrase in phrases
        ) else "LOW"

        # ARCHITECTURAL VISUAL MEANING EXTENSION V1 — a PROBABILISTIC
        # architectural profile. A kind with no profile gets empty values;
        # nothing is ever fabricated.
        profile = ELEMENT_ARCHITECTURAL_PROFILES.get(kind) or {}

        element = phrases[0] if phrases else kind

        meanings.append({
            # ---- preserved (unchanged) ----
            "observed": element,
            "element_kind": kind,
            "meaning": meaning,
            "evidence": phrases,
            "confidence": confidence,
            "reasoning_source": "observation element -> architectural meaning table",

            # ---- ADDED by the meaning extension ----
            "element": element,
            "function": profile.get("function"),
            "architectural_role": profile.get("architectural_role"),
            "possible_relationships": _element_relationships(
                kind, profile, kinds, phrases, observed_phrases
            ),
            "context": list(profile.get("context") or ()),
            "image_context": image_category,
            "exceptions": list(profile.get("exceptions") or ()),

            # a role is an INDICATOR and a relationship is POSSIBLE —
            # nothing here is an architectural absolute
            "probabilistic": True,
            "certainty": "POSSIBLE",
        })

    return meanings


# ==========================================================
# 4. spatial relationships
# ==========================================================

def _space_relationships(
    observation: Dict[str, Any],
    kinds: Dict[str, List[str]],
) -> List[Dict[str, Any]]:

    relationships: List[Dict[str, Any]] = []

    # (a) relationships the OBSERVATION already stated
    for clue in observation.get("spatial_clues") or []:

        kind = _CLUE_TO_RELATIONSHIP.get(_norm(clue.get("kind")))

        if not kind:

            continue

        relationships.append({
            "kind": kind,
            "between": [],
            "evidence": [clue.get("evidence_phrase")],
            "confidence": clue.get("confidence") or "LOW",
            "reasoning_source": "observation.spatial_clues",
        })

    # (b) relationships COMPOSED from observation elements (never invented)
    def ev(*names: str) -> List[str]:

        out: List[str] = []

        for name in names:

            for phrase in kinds.get(name, []):

                if phrase not in out:

                    out.append(phrase)

        return out

    if "bed" in kinds and "wardrobe" in kinds:

        relationships.append({
            "kind": "adjacency",
            "between": ["sleeping area", "storage / dressing"],
            "evidence": ev("bed", "wardrobe"),
            "confidence": "LOW",
            "reasoning_source": "observation elements: sleeping + storage",
        })

    if "bed" in kinds and "sanitary" in kinds:

        relationships.append({
            "kind": "privacy_clue",
            "between": ["sleeping area", "sanitary zone"],
            "evidence": ev("bed", "sanitary"),
            "confidence": "LOW",
            "reasoning_source": "observation elements: sleeping + sanitary",
        })

    if "bed" in kinds and "window" in kinds:

        relationships.append({
            "kind": "visibility",
            "between": ["sleeping area", "daylight opening"],
            "evidence": ev("bed", "window"),
            "confidence": "LOW",
            "reasoning_source": "observation elements: sleeping + daylight opening",
        })

    if "corridor" in kinds and ("door" in kinds or "opening" in kinds):

        relationships.append({
            "kind": "circulation_path",
            "between": ["circulation", "access opening"],
            "evidence": ev("corridor", "door", "opening"),
            "confidence": "LOW",
            "reasoning_source": "observation elements: circulation + access",
        })

    if "entrance" in kinds and ("facade" in kinds or "wall" in kinds):

        relationships.append({
            "kind": "separation",
            "between": ["exterior envelope", "entrance threshold"],
            "evidence": ev("entrance", "facade", "wall"),
            "confidence": "LOW",
            "reasoning_source": "observation elements: envelope + entrance",
        })

    return relationships


# ==========================================================
# 5. facade interpretation
# ==========================================================

def _facade_interpretation(
    observation: Dict[str, Any],
    kinds: Dict[str, List[str]],
) -> Optional[Dict[str, Any]]:

    if not ({"facade", "balcony", "roof", "louver", "railing", "parapet", "canopy"} & set(kinds)):

        return None

    def ev(*names: str) -> List[str]:

        out: List[str] = []

        for name in names:

            for phrase in kinds.get(name, []):

                if phrase not in out:

                    out.append(phrase)

        return out

    floors = observation.get("visible_floors")

    floor_organization = _claim(
        (
            {"count": floors.get("count"), "descriptor": floors.get("descriptor")}
            if isinstance(floors, dict)
            else None
        ),
        [floors.get("evidence_phrase")] if isinstance(floors, dict) else [],
        (floors or {}).get("confidence", "LOW") if isinstance(floors, dict) else "LOW",
        "observation.visible_floors",
    )

    openings = _claim(
        [kind for kind in ("window", "door", "opening", "balcony") if kind in kinds],
        ev("window", "door", "opening", "balcony"),
        "MEDIUM" if ("window" in kinds or "opening" in kinds) else "LOW",
        "observation architectural elements: openings",
    )

    massing_phrases = [
        entry.get("descriptor")
        for entry in observation.get("style_indicators") or []
        if _norm(entry.get("kind")) in ("form", "proportion")
    ]

    spatial = [
        clue.get("evidence_phrase")
        for clue in observation.get("spatial_clues") or []
    ]

    massing = _claim(
        massing_phrases or [p for p in spatial if p],
        (massing_phrases or spatial)[:4],
        "LOW",
        "observation.style_indicators (form/proportion) + spatial_clues",
    )

    materials = []
    for entry in observation.get("material_observations") or []:

        for material in entry.get("materials") or []:

            if material not in materials:

                materials.append(material)

    material_composition = _claim(
        materials,
        [
            entry.get("descriptor") or entry.get("evidence_phrase")
            for entry in observation.get("material_observations") or []
        ][:6],
        "MEDIUM" if materials else "LOW",
        "observation.material_observations",
    )

    # INDICATORS, never an absolute style claim
    style_indicators = [
        {
            "kind": entry.get("kind"),
            "descriptor": entry.get("descriptor"),
            "evidence": [entry.get("evidence_phrase") or entry.get("descriptor")],
            "confidence": entry.get("confidence") or "LOW",
            "reasoning_source": "observation.style_indicators (reported as indicators only)",
        }
        for entry in observation.get("style_indicators") or []
    ]

    return {
        "floor_organization": floor_organization,
        "openings": openings,
        "massing": massing,
        "material_composition": material_composition,
        "style_indicators": style_indicators,
        "absolute_style_claim": False,
    }


# ==========================================================
# 6. plan interpretation
# ==========================================================

def _plan_interpretation(
    observation: Dict[str, Any],
    kinds: Dict[str, List[str]],
) -> Optional[Dict[str, Any]]:

    labels = _as_list(observation.get("text_labels_if_visible"))

    is_plan = _norm(observation.get("image_type")) == "plan"

    if not is_plan and not labels:

        return None

    spaces: List[Dict[str, Any]] = []

    seen: List[str] = []

    for label in labels:

        key = _norm(label).strip()

        hit = PLAN_LABEL_MEANINGS.get(key)

        if hit is None:

            # a label may carry extra words ("اتاق خواب مستر شمالی")
            for surface, value in PLAN_LABEL_MEANINGS.items():

                if _norm(surface) in key:

                    hit = value

                    break

        if hit is None:

            continue

        space, zone = hit

        if space in seen:

            continue

        seen.append(space)

        spaces.append({
            "space": space,
            "zone": zone,
            "evidence": [label],
            "confidence": "MEDIUM",
            "reasoning_source": "observation.text_labels_if_visible -> plan label table",
        })

    # an element-only plan still yields spaces from its symbols
    symbol_spaces = []

    for kind, space in (("corridor", "corridor"), ("sanitary", "bathroom"),
                        ("counter", "kitchen"), ("bed", "bedroom")):

        if kind in kinds and space not in seen:

            seen.append(space)

            symbol_spaces.append({
                "space": space,
                "zone": {
                    "corridor": "circulation",
                    "bathroom": "service",
                    "kitchen": "service",
                    "bedroom": "private",
                }[space],
                "evidence": list(kinds.get(kind) or []),
                "confidence": "LOW",
                "reasoning_source": "observation element symbol -> space",
            })

    spaces.extend(symbol_spaces)

    if not spaces and not is_plan:

        return None

    organisation: Dict[str, List[str]] = {zone: [] for zone in ZONES}

    for entry in spaces:

        organisation.setdefault(entry["zone"], []).append(entry["space"])

    circulation = []

    if "corridor" in seen:

        circulation.append("corridor")

    if "stair" in kinds:

        circulation.append("stair")

    return {
        "spaces": spaces,
        "space_count": len(spaces),
        "walls": _claim(
            [kind for kind in ("wall", "partition") if kind in kinds],
            list(kinds.get("wall") or []),
            "MEDIUM" if "wall" in kinds else "LOW",
            "observation architectural elements: walls",
        ),
        "openings": _claim(
            [kind for kind in ("door", "window", "opening") if kind in kinds],
            list(kinds.get("door") or []) + list(kinds.get("window") or []),
            "MEDIUM" if ("door" in kinds or "window" in kinds) else "LOW",
            "observation architectural elements: openings",
        ),
        "circulation": _claim(
            circulation,
            list(kinds.get("corridor") or []) + list(kinds.get("stair") or []),
            "MEDIUM" if circulation else "LOW",
            "observation elements + readable plan labels",
        ),
        "public_private_service": organisation,
        "single_room_classification": False,
    }


# ==========================================================
# 7. the builder
# ==========================================================

def build_architectural_visual_interpretation_v2(
    observation: Any,
) -> Dict[str, Any]:

    """Observation -> Meaning. The observation is the PRIMARY SOURCE."""

    if not isinstance(observation, dict):

        observation = {}

    source_ok = observation.get("contract") == OBSERVATION_CONTRACT

    kinds = _element_kinds(observation)

    category = _image_category(observation)

    building = _building_type(observation)

    space = _space_understanding(observation, kinds, category.get("value"))

    elements = _element_meaning(observation, kinds, category.get("value") or "")

    relationships = _space_relationships(observation, kinds)

    facade = (
        _facade_interpretation(observation, kinds)
        if category.get("value") == "exterior_facade"
        else None
    )

    plan = (
        _plan_interpretation(observation, kinds)
        if category.get("value") == "architectural_plan"
        else None
    )

    # ---- 7. uncertainty: nothing is dropped silently -------------------
    unknowns: List[Dict[str, Any]] = []

    for entry in observation.get("unknowns") or []:

        unknowns.append({
            "name": entry.get("name"),
            "status": entry.get("status"),
            "source": "observation.unknowns",
        })

    if space.get("value") == "unknown":

        unknowns.append({
            "name": "space understanding",
            "status": "no space evidence in the observation",
            "source": "interpretation",
        })

    if building.get("value") == "unknown":

        unknowns.append({
            "name": "building type",
            "status": "no building-type evidence in the observation",
            "source": "interpretation",
        })

    if category.get("value") == "architectural_plan" and plan and not plan["spaces"]:

        unknowns.append({
            "name": "plan spaces",
            "status": "no readable room label or space symbol",
            "source": "interpretation",
        })

    claims = [category, building, space]

    return {
        "contract": CONTRACT,
        "version": VERSION,

        "source_observation_contract": observation.get("contract"),
        "source_observation_is_primary": source_ok,

        # 1
        "image_category": category,

        # 2
        "architectural_meaning": {
            "building_type": building,
            "space_understanding": space,
        },

        # 3
        "element_meaning": elements,

        # 4
        "space_relationships": relationships,

        # 5
        "facade_interpretation": facade,

        # 6
        "plan_interpretation": plan,

        # 7
        "claims": claims,
        "unknowns": unknowns,

        # safety / boundaries
        "observation_mutated": False,
        "interpretation_merged_with_observation": False,
        "absolute_style_claim": False,
        "geometry_authoritative": False,
        "plan_generated": False,
        "design_generated": False,
        "render_requested": False,
        "comfy_invoked": False,
        "llm_used": False,
        "read_only": True,
    }


# ==========================================================
# THE CLASS
# ==========================================================

class ArchitecturalVisualInterpretationV2:

    CONTRACT = CONTRACT
    VERSION = VERSION

    REQUIRES_OBSERVATION = True
    USES_LEGACY_FIELDS = False
    GENERATES_DESIGN = False
    GENERATES_GEOMETRY = False
    GENERATES_PLAN = False
    RENDERS = False
    DROPS_CLAIMS = False

    def interpret(self, observation):

        return build_architectural_visual_interpretation_v2(observation)


architectural_visual_interpretation_v2 = ArchitecturalVisualInterpretationV2()
