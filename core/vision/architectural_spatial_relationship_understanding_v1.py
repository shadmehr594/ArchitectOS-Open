# -*- coding: utf-8 -*-
"""ARCHITECTURAL_SPATIAL_RELATIONSHIP_UNDERSTANDING_V1

Visible architectural SPATIAL ORGANIZATION.

    Image
      -> ArchitecturalObservationV1            (what is visible)
      -> ArchitecturalVisualInterpretationV2   (what it may mean)
      -> ArchitecturalSpatialRelationshipUnderstandingV1   (how it is organized)

THIS LAYER OWNS
---------------
spatial organization understanding · observed spatial relationships · visible
access hierarchy · visible circulation organization · exposure/visibility
observation · facade composition relationships.

THIS LAYER DOES NOT OWN
-----------------------
architectural principles · design rules · recommendations · layout generation ·
planning decisions · geometry · CAD/BIM/IFC · rendering.

The separation is structural, not promised:
  * `observation_basis[]` is the ONLY source of visible facts.
  * every interpretation graph must trace back to it (E1/E2).
  * `non_claims` records the explicit refusals.
  * no field can hold a rule, a recommendation or a coordinate.

CONFIDENCE
----------
LOW or MEDIUM only. This layer reasons from a SINGLE image, so nothing can
be HIGH.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


CONTRACT = "ArchitecturalSpatialRelationshipUnderstandingV1"
VERSION = "1.0"

OBSERVATION_CONTRACT = "ArchitecturalObservationV1"
INTERPRETATION_CONTRACT = "ArchitecturalVisualInterpretationV2"


# ==========================================================
# READ-ONLY REUSE — the existing zone vocabulary (NOT modified)
# ==========================================================

from core.curriculum.zone_model_v1 import (  # noqa: E402
    ALL_ZONES,
    ZONE_BEHAVIOUR,
    ZONE_CIRCULATION,
    ZONE_EXTERNAL,
    ZONE_PRIVATE,
    ZONE_PUBLIC,
    ZONE_SEMI_PUBLIC,
    ZONE_SERVICE,
)


CONFIDENCE_LEVELS = ("LOW", "MEDIUM")


# ==========================================================
# closed vocabularies
# ==========================================================

RELATIONSHIP_KINDS = ("adjacency", "separation")

ZONE_RELATION_KINDS = (
    "connected",
    "private_transition",
    "service_relationship",
    "separated",
)

EXPOSURE_MODES = ("direct", "filtered", "blocked")

FACADE_COMPOSITION_KINDS = (
    "floor_stacking",
    "opening_rhythm",
    "balcony_connection",
    "solid_void",
    "material_distribution",
)

UNKNOWN_KINDS = ("missing_evidence", "unavailable_visibility", "unreadable_path")

# the visible ACCESS elements a sequence needs
ACCESS_KINDS = ("door", "entrance", "opening", "corridor", "stair", "ramp")

# the access-chain level order (exterior sits outside the chain)
HIERARCHY_ORDER = (
    ZONE_PUBLIC,
    ZONE_SEMI_PUBLIC,
    ZONE_CIRCULATION,
    ZONE_PRIVATE,
    ZONE_SERVICE,
    ZONE_EXTERNAL,
)

# visible screening elements -> `filtered`
FILTER_KINDS = ("louver", "screen", "canopy", "door")

# a `wall` is a FILTER only when its evidence phrase says it is a partition
PARTITION_PHRASES = (
    "partition", "screen wall", "half wall", "half-wall", "screening wall",
    "divider", "پارتیشن", "دیوار جداکننده", "دیوار جدا",
)

# element kind -> (spatial unit, zone)
UNIT_BY_KIND: Dict[str, Tuple[str, Optional[str]]] = {
    "bed": ("sleeping_area", ZONE_PRIVATE),
    "wardrobe": ("dressing", ZONE_PRIVATE),
    "cabinet": ("dressing", ZONE_PRIVATE),
    "shelf": ("dressing", ZONE_PRIVATE),
    "mirror": ("dressing", ZONE_PRIVATE),
    "sanitary": ("sanitary", ZONE_SERVICE),
    "counter": ("kitchen", ZONE_SERVICE),
    "sofa": ("living_area", ZONE_PUBLIC),
    "chair": ("living_area", ZONE_SEMI_PUBLIC),
    "table": ("living_area", ZONE_SEMI_PUBLIC),
    "screen": ("living_area", ZONE_PUBLIC),
    "rug": ("living_area", ZONE_PUBLIC),
    "lamp": ("living_area", ZONE_PUBLIC),
    "corridor": ("circulation", ZONE_CIRCULATION),
    "stair": ("circulation", ZONE_CIRCULATION),
    "ramp": ("circulation", ZONE_CIRCULATION),
    "door": ("access", ZONE_CIRCULATION),
    "entrance": ("access", ZONE_CIRCULATION),
    "opening": ("access", ZONE_CIRCULATION),
    "window": ("daylight_opening", ZONE_EXTERNAL),
    "facade": ("facade_plane", ZONE_EXTERNAL),
    "balcony": ("balcony", ZONE_EXTERNAL),
    "terrace": ("terrace", ZONE_EXTERNAL),
    "roof": ("roof_plane", ZONE_EXTERNAL),
    "canopy": ("canopy", ZONE_EXTERNAL),
    "louver": ("screening_element", ZONE_EXTERNAL),
    "railing": ("edge_protection", ZONE_EXTERNAL),
    "parapet": ("parapet", ZONE_EXTERNAL),
    "arch": ("arch_opening", ZONE_EXTERNAL),
    "plant": ("landscape", ZONE_EXTERNAL),
    "walkway": ("walkway", ZONE_EXTERNAL),
    "vehicle": ("vehicle_access", ZONE_EXTERNAL),
    "water_feature": ("water_feature", ZONE_EXTERNAL),
    "fence": ("site_boundary", ZONE_EXTERNAL),
    # enclosure / structure: reported as units, but NOT space-bearing
    "wall": ("enclosure_wall", None),
    "floor": ("floor_plane", None),
    "ceiling": ("ceiling_plane", None),
    "column": ("structure", None),
    "beam": ("structure", None),
    # drawing artefacts
    "dimension_line": ("annotation", None),
    "text_label": ("annotation", None),
}

# the AUTHORED vocabulary that must never carry a judgement (E3)
FORBIDDEN_WORDS = (
    "should", "must", "good", "better", "best", "optimal", "ideal",
    "quality", "room_quality", "protected", "recommend",
    "modern", "minimal", "contemporary", "beautiful", "style",
    "privacy is",
)


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


def _conf(value: str) -> str:

    """LOW / MEDIUM only — never HIGH."""

    value = _text(value).upper()

    return value if value in CONFIDENCE_LEVELS else "LOW"


# ==========================================================
# 1. observation_basis[] — THE ONLY SOURCE OF VISIBLE FACTS
# ==========================================================

def _observation_basis(observation: Dict[str, Any]) -> List[Dict[str, Any]]:

    basis: List[Dict[str, Any]] = []

    def add(fact: str, value: Any, evidence: List[str]) -> None:

        evidence = [e for e in evidence if e]

        if not evidence and value in (None, "", [], {}):

            return

        basis.append({
            "fact": fact,
            "value": value,
            "evidence": evidence,
        })

    add("image_type", observation.get("image_type"),
        ["observation.image_type = " + str(observation.get("image_type"))])

    for bucket, fact in (
        ("architectural_elements", "element_visible"),
        ("furniture_elements", "element_visible"),
        ("object_elements", "element_visible"),
        ("unclassified_observations", "observation_visible"),
    ):

        for entry in observation.get(bucket) or []:

            for kind in entry.get("kind") or []:

                add(fact, kind, [entry.get("evidence_phrase")])

    for clue in observation.get("spatial_clues") or []:

        add("clue_visible", clue.get("kind"), [clue.get("evidence_phrase")])

    floors = observation.get("visible_floors")

    if isinstance(floors, dict):

        add("floor_visible", floors.get("count"), [floors.get("evidence_phrase")])

    for entry in observation.get("material_observations") or []:

        for material in entry.get("materials") or []:

            add("material_visible", material,
                [entry.get("descriptor") or entry.get("evidence_phrase")])

    for label in observation.get("text_labels_if_visible") or []:

        add("label_visible", label, [label])

    return basis


def _basis_phrases(basis: List[Dict[str, Any]]) -> List[str]:

    phrases: List[str] = []

    for entry in basis:

        for phrase in entry.get("evidence") or []:

            if phrase and phrase not in phrases:

                phrases.append(phrase)

    return phrases


def _basis_kinds(basis: List[Dict[str, Any]]) -> Dict[str, List[str]]:

    """kind -> the visible phrases that carried it."""

    kinds: Dict[str, List[str]] = {}

    for entry in basis:

        if entry.get("fact") not in ("element_visible", "clue_visible"):

            continue

        value = entry.get("value")

        if not value:

            continue

        kinds.setdefault(str(value), [])

        for phrase in entry.get("evidence") or []:

            if phrase and phrase not in kinds[str(value)]:

                kinds[str(value)].append(phrase)

    return kinds


# ==========================================================
# 2. spatial_units[]
# ==========================================================

def _spatial_units(
    observation: Dict[str, Any],
    interpretation: Dict[str, Any],
    kinds: Dict[str, List[str]],
) -> List[Dict[str, Any]]:

    units: List[Dict[str, Any]] = []

    seen: List[str] = []

    for kind in sorted(kinds):

        mapped = UNIT_BY_KIND.get(kind)

        if not mapped:

            continue

        unit, zone = mapped

        if unit in seen:

            continue

        seen.append(unit)

        units.append({
            "unit": unit,
            "zone": zone,
            "evidence": list(kinds[kind]),
            "confidence": _conf("MEDIUM"),
            "reasoning_source": "observation element '%s' -> spatial unit" % kind,
        })

    # readable plan labels become units too (reusing V2's plan interpretation)
    plan = interpretation.get("plan_interpretation") or {}

    for entry in plan.get("spaces") or []:

        unit = entry.get("space")

        if not unit or unit in seen:

            continue

        seen.append(unit)

        units.append({
            "unit": unit,
            "zone": _ZONE_BY_PLAN_ZONE.get(entry.get("zone")) or None,
            "evidence": list(entry.get("evidence") or []),
            "confidence": _conf("LOW"),
            "reasoning_source": "interpretation.plan_interpretation label -> spatial unit",
        })

    return units


_ZONE_BY_PLAN_ZONE = {
    "public": ZONE_PUBLIC,
    "semi_public": ZONE_SEMI_PUBLIC,
    "private": ZONE_PRIVATE,
    "service": ZONE_SERVICE,
    "circulation": ZONE_CIRCULATION,
    "external": ZONE_EXTERNAL,
}


# ==========================================================
# 3. relationships[] — unit-to-unit only
# ==========================================================

def _relationships(
    units: List[Dict[str, Any]],
    kinds: Dict[str, List[str]],
) -> List[Dict[str, Any]]:

    relationships: List[Dict[str, Any]] = []

    def has(unit: str) -> bool:

        return any(u.get("unit") == unit for u in units)

    def ev(*unit_names: str) -> List[str]:

        out: List[str] = []

        for u in units:

            if u.get("unit") in unit_names:

                for phrase in u.get("evidence") or []:

                    if phrase not in out:

                        out.append(phrase)

        return out

    # adjacency — two units visible together
    for a, b in (("sleeping_area", "dressing"), ("dressing", "sanitary"),
                 ("living_area", "kitchen"), ("access", "circulation")):

        if has(a) and has(b):

            relationships.append({
                "kind": "adjacency",
                "from": a,
                "to": b,
                "evidence": ev(a, b),
                "confidence": _conf("MEDIUM"),
                "reasoning_source": "observation evidence: %s + %s (both visible)" % (a, b),
            })

    # separation — a visible enclosure element between two units
    enclosure = [
        phrase
        for phrase in (kinds.get("wall") or [])
        if not any(p in _norm(phrase) for p in PARTITION_PHRASES)
    ]

    if enclosure:

        for a, b in (("access", "sleeping_area"), ("access", "sanitary")):

            if has(a) and has(b):

                relationships.append({
                    "kind": "separation",
                    "from": a,
                    "to": b,
                    "evidence": ev(a, b) + enclosure,
                    "confidence": _conf("LOW"),
                    "reasoning_source": "observation evidence: %s + %s (physical separation)" % (a, b),
                })

    return relationships


# ==========================================================
# 4. zone_graph[] — zone-to-zone organization
# ==========================================================

_ZONE_PAIR_RELATION = {
    (ZONE_PUBLIC, ZONE_SEMI_PUBLIC): "connected",
    (ZONE_PUBLIC, ZONE_CIRCULATION): "connected",
    (ZONE_SEMI_PUBLIC, ZONE_CIRCULATION): "connected",
    (ZONE_CIRCULATION, ZONE_PRIVATE): "private_transition",
    (ZONE_SEMI_PUBLIC, ZONE_PRIVATE): "private_transition",
    (ZONE_PRIVATE, ZONE_SERVICE): "service_relationship",
    (ZONE_CIRCULATION, ZONE_SERVICE): "service_relationship",
    (ZONE_PUBLIC, ZONE_PRIVATE): "separated",
    (ZONE_EXTERNAL, ZONE_PRIVATE): "separated",
}


def _zone_graph(units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

    by_zone: Dict[str, List[Dict[str, Any]]] = {}

    for unit in units:

        zone = unit.get("zone")

        if zone:

            by_zone.setdefault(zone, []).append(unit)

    zones = sorted(by_zone)

    graph: List[Dict[str, Any]] = []

    for i, a in enumerate(zones):

        for b in zones[i + 1:]:

            relation = _ZONE_PAIR_RELATION.get((a, b)) or _ZONE_PAIR_RELATION.get((b, a))

            if not relation:

                continue

            evidence: List[str] = []

            for unit in by_zone[a] + by_zone[b]:

                for phrase in unit.get("evidence") or []:

                    if phrase not in evidence:

                        evidence.append(phrase)

            graph.append({
                "from_zone": a,
                "to_zone": b,
                "relation": relation,
                "evidence": evidence[:6],
                "confidence": _conf("LOW"),
                "reasoning_source": "zone pair (%s -> %s) derived from the visible units" % (a, b),
            })

    return graph


# ==========================================================
# 5. visibility_graph[] — ALL exposure information
# ==========================================================

def _exposure(kinds: Dict[str, List[str]]) -> Tuple[str, List[str]]:

    """direct / filtered / blocked — from VISIBLE elements only."""

    filters: List[str] = []

    for kind in FILTER_KINDS:

        for phrase in kinds.get(kind) or []:

            if phrase not in filters:

                filters.append(phrase)

    for phrase in kinds.get("wall") or []:

        if any(p in _norm(phrase) for p in PARTITION_PHRASES):

            if phrase not in filters:

                filters.append(phrase)

    if filters:

        return "filtered", filters

    blockers = [
        phrase
        for phrase in (kinds.get("wall") or [])
        if not any(p in _norm(phrase) for p in PARTITION_PHRASES)
    ]

    if blockers:

        return "blocked", blockers

    return "direct", []


def _visibility_graph(
    units: List[Dict[str, Any]],
    kinds: Dict[str, List[str]],
) -> List[Dict[str, Any]]:

    access_units = [u for u in units if u.get("unit") == "access"]

    if not access_units:

        return []

    targets = [
        u for u in units
        if u.get("zone") in (ZONE_PRIVATE, ZONE_SERVICE)
    ]

    graph: List[Dict[str, Any]] = []

    mode, mode_evidence = _exposure(kinds)

    for source in access_units:

        for target in targets:

            graph.append({
                "from": source.get("unit"),
                "to": target.get("unit"),
                "mode": mode,
                "mode_evidence": list(mode_evidence),
                "confidence": _conf("MEDIUM" if mode_evidence else "LOW"),
                "reasoning_source": (
                    "exposure mode from visible %s"
                    % (", ".join(mode_evidence) if mode_evidence else "elements (no filter, no blocker)")
                ),
            })

    return graph


# ==========================================================
# 6. hierarchy[] — access order (UNORDERED sets, never a path)
# ==========================================================

def _hierarchy(units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

    by_zone: Dict[str, List[str]] = {}

    evidence: Dict[str, List[str]] = {}

    for unit in units:

        zone = unit.get("zone")

        if not zone:

            continue

        by_zone.setdefault(zone, [])

        if unit.get("unit") not in by_zone[zone]:

            by_zone[zone].append(unit.get("unit"))

        evidence.setdefault(zone, [])

        for phrase in unit.get("evidence") or []:

            if phrase not in evidence[zone]:

                evidence[zone].append(phrase)

    def affinity(zone: str) -> int:

        behaviour = ZONE_BEHAVIOUR.get(zone) or {}

        value = behaviour.get("access_affinity")

        return int(value) if isinstance(value, int) else 0

    # the level order: the access chain first, the exterior last.
    # `access_affinity` (the existing zone vocabulary) is REPORTED per level.
    ordered = [zone for zone in HIERARCHY_ORDER if zone in by_zone]

    hierarchy: List[Dict[str, Any]] = []

    for level, zone in enumerate(ordered, start=1):

        hierarchy.append({
            "level": level,
            "zone": zone,
            # UNORDERED — this is a level grouping, NOT a path
            "units": sorted(by_zone[zone]),
            "access_affinity": affinity(zone),
            "evidence": evidence[zone][:6],
            "confidence": _conf("LOW"),
            "reasoning_source": "zone access_affinity from the existing zone vocabulary (level grouping, not a path)",
        })

    return hierarchy


# ==========================================================
# 7. sequences[] — ordered visible access chains
# ==========================================================

def _sequences(
    units: List[Dict[str, Any]],
    kinds: Dict[str, List[str]],
) -> Tuple[List[Dict[str, Any]], bool]:

    """Returns (sequences, path_unreadable)."""

    access_visible = [kind for kind in ACCESS_KINDS if kinds.get(kind)]

    if len(units) < 2 or not access_visible:

        return [], True

    def depth(zone: Optional[str]) -> int:

        """The access-chain depth — the SAME order the hierarchy uses."""

        try:

            return HIERARCHY_ORDER.index(zone)

        except ValueError:

            return len(HIERARCHY_ORDER)

    access_units = [u for u in units if u.get("unit") == "access"]

    # the visible screening element is part of the chain (the brief's filter)
    filter_units = [u for u in units if u.get("unit") == "screening_element"]

    space_units = [
        u for u in units
        if u.get("unit") not in ("access", "screening_element") and u.get("zone")
    ]

    # ordered reading: the visible access element, then the visible filter,
    # then the space units by access-chain depth (public -> private -> service)
    ordered_units = (
        access_units
        + filter_units
        + sorted(space_units, key=lambda u: (depth(u.get("zone")), str(u.get("unit"))))
    )

    sequence: List[str] = []

    evidence: List[str] = []

    for unit in ordered_units:

        name = unit.get("unit")

        if name and name not in sequence:

            sequence.append(name)

        for phrase in unit.get("evidence") or []:

            if phrase not in evidence:

                evidence.append(phrase)

    return [{
        "sequence": sequence,
        "evidence": evidence[:8],
        "confidence": _conf("LOW"),
        "reasoning_source": (
            "visible access element(s) %s + the space units visible in the same image, "
            "arranged by the access-chain level (an ordered reading, not a drawn path)"
            % ", ".join(access_visible)
        ),
    }], False


# ==========================================================
# 8. facade_composition_graph[]
# ==========================================================

def _facade_composition_graph(
    observation: Dict[str, Any],
    units: List[Dict[str, Any]],
    kinds: Dict[str, List[str]],
    image_category: Optional[str] = None,
) -> List[Dict[str, Any]]:

    graph: List[Dict[str, Any]] = []

    # ONLY an exterior view has a facade composition. An interior or a
    # drawing must never produce one.
    if image_category != "exterior_facade":

        return graph

    def ev(*names: str) -> List[str]:

        out: List[str] = []

        for name in names:

            for phrase in kinds.get(name) or []:

                if phrase not in out:

                    out.append(phrase)

        return out

    floors = observation.get("visible_floors")

    if isinstance(floors, dict) and floors.get("evidence_phrase"):

        graph.append({
            "kind": "floor_stacking",
            "between": ["ground_level", "upper_level"],
            "evidence": [floors.get("evidence_phrase")],
            "confidence": _conf(floors.get("confidence") or "LOW"),
            "reasoning_source": "observation.visible_floors",
        })

    openings = ev("window", "opening", "door")

    if openings:

        graph.append({
            "kind": "opening_rhythm",
            "between": ["opening", "opening"],
            "evidence": openings[:4],
            "confidence": _conf("LOW"),
            "reasoning_source": "visible openings on the same plane",
        })

    if kinds.get("balcony") and (kinds.get("window") or kinds.get("opening")):

        graph.append({
            "kind": "balcony_connection",
            "between": ["balcony", "daylight_opening"],
            "evidence": ev("balcony", "window", "opening")[:4],
            "confidence": _conf("MEDIUM"),
            "reasoning_source": "observation evidence: balcony + opening",
        })

    solid = ev("facade", "wall", "roof", "parapet")

    if solid and openings:

        graph.append({
            "kind": "solid_void",
            "between": ["solid_surface", "opening"],
            "evidence": (solid + openings)[:5],
            "confidence": _conf("MEDIUM"),
            "reasoning_source": "a solid surface and an opening are both visible",
        })

    materials = [
        material
        for entry in observation.get("material_observations") or []
        for material in entry.get("materials") or []
    ]

    if materials:

        graph.append({
            "kind": "material_distribution",
            "between": ["envelope_surface", "material"],
            "evidence": [
                entry.get("descriptor") or entry.get("evidence_phrase")
                for entry in observation.get("material_observations") or []
            ][:5],
            "confidence": _conf("MEDIUM"),
            "reasoning_source": "observation.material_observations",
        })

    return graph


# ==========================================================
# 9. unknowns[]
# ==========================================================

def _unknowns(
    observation: Dict[str, Any],
    path_unreadable: bool,
    units: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    unknowns: List[Dict[str, Any]] = []

    for entry in observation.get("unknowns") or []:

        unknowns.append({
            "kind": "missing_evidence",
            "name": entry.get("name"),
            "source": "observation.unknowns",
        })

    if path_unreadable:

        unknowns.append({
            "kind": "unreadable_path",
            "name": "circulation",
            "source": "no visible access element (door / entrance / corridor / opening / stair / ramp)",
        })

    if not units:

        unknowns.append({
            "kind": "missing_evidence",
            "name": "spatial units",
            "source": "no spatial unit could be derived from the observation",
        })

    return unknowns


# ==========================================================
# 10. the forbidden-vocabulary scan (E3)
# ==========================================================

def _authored_strings(payload: Dict[str, Any]) -> List[str]:

    """The AUTHORED vocabulary only — never the quoted observation."""

    out: List[str] = []

    for unit in payload.get("spatial_units") or []:

        out.append(str(unit.get("unit")))
        out.append(str(unit.get("reasoning_source")))

    for rel in payload.get("relationships") or []:

        out.append(str(rel.get("kind")))
        out.append(str(rel.get("reasoning_source")))

    for entry in payload.get("zone_graph") or []:

        out.append(str(entry.get("relation")))
        out.append(str(entry.get("reasoning_source")))

    for entry in payload.get("visibility_graph") or []:

        out.append(str(entry.get("mode")))
        out.append(str(entry.get("reasoning_source")))

    for entry in payload.get("hierarchy") or []:

        out.append(str(entry.get("reasoning_source")))

    for entry in payload.get("sequences") or []:

        out.append(str(entry.get("reasoning_source")))

    for entry in payload.get("facade_composition_graph") or []:

        out.append(str(entry.get("kind")))
        out.append(str(entry.get("reasoning_source")))

    for entry in payload.get("unknowns") or []:

        out.append(str(entry.get("kind")))
        out.append(str(entry.get("source")))

    return out


def forbidden_vocabulary_hits(payload: Dict[str, Any]) -> List[str]:

    hits: List[str] = []

    for text in _authored_strings(payload):

        low = _norm(text)

        for word in FORBIDDEN_WORDS:

            if _norm(word) in low and word not in hits:

                hits.append(word)

    return hits


# ==========================================================
# 11. traceability (E1 / E2)
# ==========================================================

def _traceability_violations(payload: Dict[str, Any]) -> List[str]:

    """Every interpretation evidence phrase must exist in observation_basis."""

    allowed = set(_basis_phrases(payload.get("observation_basis") or []))

    violations: List[str] = []

    def check(container: str, phrases: List[str]) -> None:

        for phrase in phrases or []:

            if phrase and phrase not in allowed:

                violations.append("%s: %s" % (container, phrase))

    for unit in payload.get("spatial_units") or []:

        check("spatial_units", unit.get("evidence"))

    for rel in payload.get("relationships") or []:

        check("relationships", rel.get("evidence"))

    for entry in payload.get("zone_graph") or []:

        check("zone_graph", entry.get("evidence"))

    for entry in payload.get("visibility_graph") or []:

        check("visibility_graph", entry.get("mode_evidence"))

    for entry in payload.get("hierarchy") or []:

        check("hierarchy", entry.get("evidence"))

    for entry in payload.get("sequences") or []:

        check("sequences", entry.get("evidence"))

    for entry in payload.get("facade_composition_graph") or []:

        check("facade_composition_graph", entry.get("evidence"))

    return violations


# ==========================================================
# THE BUILDER
# ==========================================================

def build_architectural_spatial_relationship_understanding_v1(
    observation: Any,
    interpretation: Any = None,
) -> Dict[str, Any]:

    """Observation + Interpretation -> visible spatial organization."""

    observation = observation if isinstance(observation, dict) else {}

    interpretation = interpretation if isinstance(interpretation, dict) else {}

    basis = _observation_basis(observation)

    kinds = _basis_kinds(basis)

    units = _spatial_units(observation, interpretation, kinds)

    relationships = _relationships(units, kinds)

    zone_graph = _zone_graph(units)

    visibility_graph = _visibility_graph(units, kinds)

    hierarchy = _hierarchy(units)

    sequences, path_unreadable = _sequences(units, kinds)

    image_category = (
        (interpretation.get("image_category") or {}).get("value")
        if isinstance(interpretation.get("image_category"), dict)
        else None
    )

    facade = _facade_composition_graph(observation, units, kinds, image_category)

    unknowns = _unknowns(observation, path_unreadable, units)

    provenance_in = observation.get("provenance") or {}

    payload: Dict[str, Any] = {
        "contract": CONTRACT,
        "version": VERSION,

        "source_observation_contract": observation.get("contract"),
        "source_interpretation_contract": interpretation.get("contract"),

        "provenance": {
            "provider": provenance_in.get("provider"),
            "model": provenance_in.get("model"),
            "prompt_version": provenance_in.get("prompt_version"),
            "image_id": provenance_in.get("image_id"),
        },

        "observation_basis": basis,

        "spatial_units": units,
        "relationships": relationships,
        "zone_graph": zone_graph,
        "visibility_graph": visibility_graph,
        "hierarchy": hierarchy,
        "sequences": sequences,
        "facade_composition_graph": facade,
        "unknowns": unknowns,

        "non_claims": {
            "principle_asserted": False,
            "design_generated": False,
            "plan_generated": False,
            "geometry_authoritative": False,
            "render_requested": False,
            "observation_only": True,
        },
    }

    payload["traceability_violations"] = _traceability_violations(payload)
    payload["forbidden_vocabulary_hits"] = forbidden_vocabulary_hits(payload)

    return payload


# ==========================================================
# THE CLASS
# ==========================================================

class ArchitecturalSpatialRelationshipUnderstandingV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    REQUIRES_OBSERVATION = True
    GENERATES_DESIGN = False
    GENERATES_PLAN = False
    GENERATES_GEOMETRY = False
    RENDERS = False
    ASSERTS_PRINCIPLES = False
    MAX_CONFIDENCE = "MEDIUM"

    def understand(self, observation, interpretation=None):

        return build_architectural_spatial_relationship_understanding_v1(
            observation, interpretation
        )

    def scan(self, payload):

        return forbidden_vocabulary_hits(payload)


architectural_spatial_relationship_understanding_v1 = (
    ArchitecturalSpatialRelationshipUnderstandingV1()
)
