"""W4.1 — ARCHITECTURAL FUNCTION EVIDENCE CONTRACT.

READ-ONLY / SHADOW MODE. Provider-independent, model-independent.

WHAT THIS MODULE IS
-------------------
A single, auditable evidence contract that a FUTURE W4 reasoner will consume.
It COLLECTS architectural evidence, CLASSIFIES it by type and strength, records
its provenance, and exposes the independence structure of that evidence.

WHAT THIS MODULE IS NOT
-----------------------
It never resolves a room function. Every region is published with
``resolved_function: None`` and the envelope carries ``resolves_functions:
False`` / ``resolution_withheld: True``. A/B/C/D behaviour is unchanged: this
module is attached additively and reads the already-published plan reading
without mutating it.

Frozen surfaces deliberately untouched: render, ComfyUI, BIM/IFC/CAD,
structure, voice, teaching, knowledge promotion, W1 enclosure semantics, W2
axis semantics, W3 role taxonomy, W3R graphic OCR gate, W3.5 runtime policy,
column/door/unit/lightwell/elevator detectors, parcel-edge and
expansion-joint reasoning.

ARCHITECTURAL PRINCIPLE
-----------------------
UNKNOWN IS BETTER THAN AN UNSUPPORTED GUESS. No region receives a function
because its proportions or its position on the sheet look plausible. Absence of
furniture never implies a function. Geometry alone never determines a function.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Optional, Tuple

CONTRACT = "ArchitecturalFunctionEvidenceV1"
VERSION = "w4.1-architectural-function-evidence-v1"

MODE = "shadow"

# ==================================================
# GUARANTEES — asserted by the W4.1 contract tests.
# ==================================================

READ_ONLY = True
PROVIDER_INDEPENDENT = True
MODEL_INDEPENDENT = True
RESOLVES_FUNCTIONS = False
RESOLUTION_WITHHELD = True
CHANGES_INFERRED_FUNCTIONS = False
CHANGES_NAMED_SPACES = False
CHANGES_UNIT_COUNT = False
CHANGES_ROLE_CLASSIFICATION = False
CREATES_REGION_BINDINGS = False
CREATES_CORRESPONDENCES = False

# ==================================================
# PART 2 — EVIDENCE TYPES
# ==================================================

DIRECT_SEMANTIC = "direct_semantic"
FURNITURE = "furniture"
FIXTURE = "fixture"
OPENING_ACCESS = "opening_access"
ADJACENCY = "adjacency"
CIRCULATION = "circulation"
GEOMETRY = "geometry"
CORRESPONDING_PANEL = "corresponding_panel"
NEGATIVE_OR_CONFLICTING = "negative_or_conflicting"

EVIDENCE_TYPES = (
    DIRECT_SEMANTIC,
    FURNITURE,
    FIXTURE,
    OPENING_ACCESS,
    ADJACENCY,
    CIRCULATION,
    GEOMETRY,
    CORRESPONDING_PANEL,
    NEGATIVE_OR_CONFLICTING,
)

# ==================================================
# PART 3 — EVIDENCE STRENGTH
#
# The strengths are NOT interchangeable. A single object is never STRONG, and a
# weak signal is never promoted because it happens to sit next to a strong one.
# ==================================================

DIRECT = "DIRECT"
STRONG = "STRONG"
SUPPORTING = "SUPPORTING"
WEAK = "WEAK"
CONTRADICTING = "CONTRADICTING"

EVIDENCE_STRENGTHS = (DIRECT, STRONG, SUPPORTING, WEAK, CONTRADICTING)

_STRENGTH_RANK = {WEAK: 0, SUPPORTING: 1, STRONG: 2, DIRECT: 3}

# ==================================================
# PART 8 — RESOLUTION STATES
#
# Representable by the contract; NEVER applied by W4.1. `resolved_function` is
# always None and `resolution_withheld` is always True.
# ==================================================

SUPPORTED = "SUPPORTED"
PROBABLE = "PROBABLE"
AMBIGUOUS = "AMBIGUOUS"
CONFLICTED = "CONFLICTED"
INSUFFICIENT = "INSUFFICIENT"
UNKNOWN = "UNKNOWN"

RESOLUTION_STATES = (
    SUPPORTED,
    PROBABLE,
    AMBIGUOUS,
    CONFLICTED,
    INSUFFICIENT,
    UNKNOWN,
)

# ==================================================
# GROUNDING / TRANSPORT STATUS
# ==================================================

GROUNDING_GROUNDED = "grounded"
GROUNDING_GROUNDED_UNBOUND = "grounded_label_without_recorded_enclosure_binding"
GROUNDING_SYMBOL = "local_symbol_reading"
GROUNDING_TRANSPORTED_UNBOUND = "transported_symbol_without_trusted_region_identity"
GROUNDING_GEOMETRY = "geometry_only"
GROUNDING_RELATION = "published_relation"
GROUNDING_PROVIDER_ONLY = "provider_only"

TRANSPORT_NATIVE = "native"
TRANSPORT_TRANSPORTED = "transported"
TRANSPORT_NOT_TRANSPORTED = "not_transported"

REGION_ATTRIBUTION_BOUND = "bound"
REGION_ATTRIBUTION_NOT_RECORDED = "not_recorded_in_trusted_data"
REGION_ATTRIBUTION_NOT_TRANSPORTED = "not_transported"

# ==================================================
# ARCHITECTURAL SIGNALS
# ==================================================

SIGNAL_GROUNDED_ROOM_LABEL = "grounded_room_label"
SIGNAL_FURNITURE_SYMBOL = "furniture_symbol"
SIGNAL_FIXTURE_SYMBOL = "fixture_symbol"
SIGNAL_OPENING_OR_ACCESS = "opening_or_access"
SIGNAL_ADJACENCY_RELATION = "adjacency_relation"
SIGNAL_CIRCULATION_SPACE = "circulation_space"
SIGNAL_ENCLOSURE_GEOMETRY = "enclosure_geometry"
SIGNAL_CORRESPONDING_PANEL_TRANSFER = "corresponding_panel_transfer"
SIGNAL_INCOMPATIBLE_EVIDENCE_PAIR = "incompatible_evidence_pair"

# ==================================================
# SYMBOL CLASS -> COMBINATION ROLE
#
# The primary class -> function mapping is the FROZEN
# `local_plan_symbols_v1.FUNCTIONS`. This table only supplies the combination
# roles for the classes that mapping deliberately leaves functionless (a chair
# or a wardrobe alone is not a space) and the seating membership used by the
# dining-cluster rule. It never redefines the frozen taxonomy.
# ==================================================

_SEATING_CLASSES = frozenset({"chair", "sofa", "seating"})

_COMBINATION_ROLE = {
    "chair": ("dining", "seating_member"),
    "sofa": ("living room", "seating_member"),
    "seating": ("living room", "seating_member"),
    "storage_cabinet": ("bedroom", "wardrobe_member"),
    "bed": ("bedroom", "sleeping_object"),
    "dining_surface": ("dining", "dining_surface"),
    "kitchen_counter": ("kitchen", "kitchen_counter"),
    "kitchen_sink_arrangement": ("kitchen", "kitchen_basin"),
    "sanitary_fixture": ("bathroom", "sanitary_fixture"),
}

_FIXTURE_CLASSES = frozenset(
    {"sanitary_fixture", "kitchen_sink_arrangement", "kitchen_counter"}
)

# Architecturally IMPOSSIBLE co-locations. Two of these in the same trusted
# region at >= SUPPORTING make the region CONFLICTED, never resolved.
INCOMPATIBLE_FUNCTION_PAIRS = (
    frozenset({"bedroom", "bathroom"}),
    frozenset({"bedroom", "wc"}),
    frozenset({"bedroom", "kitchen"}),
    frozenset({"bathroom", "kitchen"}),
    frozenset({"bathroom", "dining"}),
    frozenset({"bathroom", "living room"}),
    frozenset({"wc", "kitchen"}),
    frozenset({"wc", "living room"}),
    frozenset({"wc", "dining"}),
)


# ==================================================
# SMALL HELPERS
# ==================================================


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _bbox(value: Any) -> Optional[List[int]]:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 4
        and all(isinstance(v, (int, float)) for v in value)
    ):
        return [int(round(v)) for v in value]
    return None


def _centre(box: List[int]) -> Tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def _contains(outer: List[int], point: Tuple[float, float]) -> bool:
    return outer[0] <= point[0] <= outer[2] and outer[1] <= point[1] <= outer[3]


def _evidence_id(identity: str) -> str:
    """A deterministic id derived from the evidence's OWN identity.

    Never a fabricated region or item id: the id is a hash of the provenance
    the evidence already carries.
    """
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()
    return "afe-" + digest[:12]


def _independence_key(prefix: str, *parts: Any) -> str:
    return ":".join([prefix] + [str(p) for p in parts if p not in (None, "")])


# ==================================================
# PANEL / REGION NORMALISATION
#
# Two trusted shapes exist in the project and both must be handled without
# inventing anything:
#   * a SINGLE plan  -> the reading itself carries enclosure_geometry/regions
#   * a SHEET        -> panel_readings[i].plan_reading carries them per panel
# ==================================================


def _panels(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    readings = plan.get("panel_readings") or []
    panels = []
    for index, reading in enumerate(readings, 1):
        sub = reading.get("plan_reading") or {}
        panels.append(
            {
                "panel_id": reading.get("panel_id") or ("p%d" % index),
                "role": reading.get("role"),
                "reading": sub,
            }
        )
    if panels:
        return panels
    return [{"panel_id": "p1", "role": None, "reading": plan}]


def _regions(reading: Dict[str, Any]) -> List[Dict[str, Any]]:
    regions = []
    for entry in reading.get("geometry_spaces") or []:
        if not isinstance(entry, dict):
            continue
        region_id = entry.get("region_id")
        box = _bbox(entry.get("bbox_pixels"))
        if not region_id or box is None:
            continue
        regions.append(
            {
                "region_id": region_id,
                "bbox_pixels": box,
                "confidence": entry.get("confidence"),
                "wall_levels": entry.get("wall_levels"),
                "stable_across_gap_scales": entry.get("stable_across_gap_scales"),
                "trusted": _trusted_region(entry),
            }
        )
    return regions


def _trusted_region(region: Dict[str, Any]) -> bool:
    """A region is trusted when the enclosure evidence itself is not weak.

    Only a trusted region may carry STRONG evidence. An untrusted enclosure
    caps every strength at SUPPORTING, because the enclosure identity is what
    the architectural claim rests on.
    """
    if region.get("stable_across_gap_scales") is False:
        return False
    return str(region.get("confidence") or "").upper() in ("MEDIUM", "HIGH")


def _panel_labels(reading: Dict[str, Any]) -> List[Dict[str, Any]]:
    local = reading.get("local_plan_reading") or {}
    labels = local.get("labels")
    if isinstance(labels, list) and labels:
        return [item for item in labels if isinstance(item, dict)]
    # No grounded transcription available: fall back to the named spaces the
    # plan already published, which carry the same label provenance.
    out = []
    for entry in reading.get("named_spaces") or []:
        if isinstance(entry, dict) and entry.get("evidence_type") == "label":
            out.append(entry)
    return out


def _panel_openings(reading: Dict[str, Any]) -> List[Dict[str, Any]]:
    instances = []
    for group in reading.get("openings") or []:
        if not isinstance(group, dict):
            continue
        kind = group.get("kind")
        for item in group.get("instances") or []:
            if not isinstance(item, dict):
                continue
            box = _bbox(item.get("bbox_pixels"))
            if box is None:
                continue
            instances.append(
                {
                    "kind": kind or item.get("kind"),
                    "bbox_pixels": box,
                    "confidence": item.get("confidence"),
                    "raster_patch_sha256": item.get("raster_patch_sha256"),
                    "element_id": item.get("element_id"),
                    "producer": item.get("producer"),
                }
            )
    return instances


# ==================================================
# EVIDENCE ITEM CONSTRUCTION
# ==================================================


def _item(
    *,
    evidence_type: str,
    architectural_signal: str,
    source_panel_id: Optional[str],
    source_region_id: Optional[str] = None,
    region_attribution_status: str = REGION_ATTRIBUTION_NOT_RECORDED,
    source_item_id: Optional[str] = None,
    source_bbox: Optional[List[int]] = None,
    source: str = "local_offline_raster",
    producer: str = "architectural_function_evidence_v1",
    confidence: Optional[str] = None,
    grounding_status: str = GROUNDING_SYMBOL,
    transport_status: str = TRANSPORT_NOT_TRANSPORTED,
    supporting_functions: Optional[Iterable[str]] = None,
    contradicting_functions: Optional[Iterable[str]] = None,
    evidence_strength: str = WEAK,
    independence_key: str = "",
    same_underlying_evidence: bool = False,
    combination_role: Optional[str] = None,
    correspondence: Optional[Dict[str, Any]] = None,
    notes: Optional[Iterable[str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    identity = _independence_key(
        evidence_type,
        source_panel_id,
        source_region_id,
        source_item_id,
        architectural_signal,
        source_bbox,
        independence_key,
    )
    item = {
        "evidence_id": _evidence_id(identity),
        "evidence_type": evidence_type,
        "architectural_signal": architectural_signal,
        "source_panel_id": source_panel_id,
        "source_region_id": source_region_id,
        "region_attribution_status": (
            REGION_ATTRIBUTION_BOUND
            if source_region_id
            else region_attribution_status
        ),
        "source_item_id": source_item_id,
        "source_bbox": source_bbox,
        "source": source,
        "producer": producer,
        "confidence": confidence,
        "grounding_status": grounding_status,
        "transport_status": transport_status,
        "supporting_functions": sorted(set(supporting_functions or ())),
        "contradicting_functions": sorted(set(contradicting_functions or ())),
        "evidence_strength": evidence_strength,
        "independence_key": independence_key or identity,
        "same_underlying_evidence": bool(same_underlying_evidence),
        "combination_role": combination_role,
        "correspondence": correspondence,
        "notes": list(notes or ()),
    }
    if extra:
        item.update(extra)
    return item


def _label_evidence(panel: Dict[str, Any]) -> List[Dict[str, Any]]:
    """DIRECT semantic evidence, when the enclosure binding is genuinely known."""
    items = []
    for index, label in enumerate(_panel_labels(panel["reading"]), 1):
        function = label.get("semantic_function")
        if not function:
            continue
        box = _bbox(label.get("bbox_pixels"))
        region_id = label.get("associated_region_id")
        # The SAME label pixels are ONE source however many OCR passes read
        # them. `independent_passes` is recorded for audit and is explicitly
        # NOT a vote count.
        passes = label.get("independent_passes")
        items.append(
            _item(
                evidence_type=DIRECT_SEMANTIC,
                architectural_signal=SIGNAL_GROUNDED_ROOM_LABEL,
                source_panel_id=panel["panel_id"],
                source_region_id=region_id,
                region_attribution_status=REGION_ATTRIBUTION_NOT_RECORDED,
                source_item_id="label%d" % index,
                source_bbox=box,
                source="local_ocr_grounded",
                producer="local_plan_reader_v1",
                confidence=label.get("confidence"),
                grounding_status=(
                    GROUNDING_GROUNDED if region_id else GROUNDING_GROUNDED_UNBOUND
                ),
                supporting_functions=[function],
                # A grounded label IS direct evidence; the enclosure binding is
                # what makes it attributable to a region, and it is withheld
                # (not guessed) when the trusted data does not record it.
                evidence_strength=DIRECT,
                independence_key=_independence_key(
                    "label", panel["panel_id"], label.get("text"), box
                ),
                notes=[
                    "grounded label; transcribed text is the source identity"
                    + (
                        ""
                        if region_id
                        else "; enclosure binding is not recorded in the "
                        "trusted data, so the region is withheld rather than "
                        "guessed"
                    ),
                ],
                extra={
                    "label_text": label.get("text"),
                    "raw_ocr": label.get("raw_ocr"),
                    "ocr_passes": passes,
                    "ocr_passes_are_independent_evidence": False,
                    "zone": _zone(function),
                },
            )
        )
    return items


def _furniture_evidence(panel: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Furniture / fixture symbol evidence, bound only where genuinely bound."""
    items = []
    for entry in panel["reading"].get("furniture") or []:
        if not isinstance(entry, dict):
            continue
        symbol_class = entry.get("class")
        role = _COMBINATION_ROLE.get(symbol_class)
        function = entry.get("supports_space") or entry.get("supported_function")
        if role and not function:
            function = role[0]
        region_ids = [
            r for r in (entry.get("region_ids") or []) if isinstance(r, str)
        ]
        box = _bbox(entry.get("bbox_pixels"))
        native = bool(entry.get("native_symbol_pass"))
        patch = entry.get("raster_patch_sha256")
        origin_panel = entry.get("source_panel_id") or panel["panel_id"]
        # The patch hash is the UNDERLYING object identity: an item transported
        # from another panel keeps its native patch hash, so it can never be
        # counted as a second independent vote.
        key = _independence_key("item", origin_panel, symbol_class, patch)
        if not region_ids:
            items.append(
                _item(
                    evidence_type=(
                        FIXTURE if symbol_class in _FIXTURE_CLASSES else FURNITURE
                    ),
                    architectural_signal=(
                        SIGNAL_FIXTURE_SYMBOL
                        if symbol_class in _FIXTURE_CLASSES
                        else SIGNAL_FURNITURE_SYMBOL
                    ),
                    source_panel_id=panel["panel_id"],
                    region_attribution_status=REGION_ATTRIBUTION_NOT_TRANSPORTED,
                    source_item_id=entry.get("item_id"),
                    source_bbox=box,
                    source=entry.get("source") or "local_raster_symbol_topology",
                    producer="local_plan_symbols_v1",
                    confidence=entry.get("confidence"),
                    grounding_status=GROUNDING_TRANSPORTED_UNBOUND,
                    transport_status=(
                        TRANSPORT_TRANSPORTED if native else TRANSPORT_NATIVE
                    ),
                    supporting_functions=[function] if function else [],
                    evidence_strength=SUPPORTING,
                    independence_key=key,
                    combination_role=role[1] if role else None,
                    notes=[
                        "UNBOUND ARCHITECTURAL EVIDENCE: the item is grounded but "
                        "carries no trusted region identity, so it may not "
                        "promote a space function",
                    ],
                    extra={"symbol_class": symbol_class},
                )
            )
            continue
        for region_id in region_ids:
            items.append(
                _item(
                    evidence_type=(
                        FIXTURE if symbol_class in _FIXTURE_CLASSES else FURNITURE
                    ),
                    architectural_signal=(
                        SIGNAL_FIXTURE_SYMBOL
                        if symbol_class in _FIXTURE_CLASSES
                        else SIGNAL_FURNITURE_SYMBOL
                    ),
                    source_panel_id=panel["panel_id"],
                    source_region_id=region_id,
                    source_item_id=entry.get("item_id"),
                    source_bbox=box,
                    source=entry.get("source") or "local_raster_symbol_topology",
                    producer="local_plan_symbols_v1",
                    confidence=entry.get("confidence"),
                    grounding_status=GROUNDING_SYMBOL,
                    transport_status=(
                        TRANSPORT_TRANSPORTED if native else TRANSPORT_NATIVE
                    ),
                    supporting_functions=[function] if function else [],
                    evidence_strength=SUPPORTING,
                    independence_key=key,
                    combination_role=role[1] if role else None,
                    notes=[
                        "localized raster symbol inside an independently "
                        "detected region"
                    ],
                    extra={"symbol_class": symbol_class},
                )
            )
    return items


def _opening_evidence(panel: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Access evidence attributed to a region by the opening's own centre."""
    items = []
    for index, opening in enumerate(_panel_openings(panel["reading"]), 1):
        items.append(
            _item(
                evidence_type=OPENING_ACCESS,
                architectural_signal=SIGNAL_OPENING_OR_ACCESS,
                source_panel_id=panel["panel_id"],
                source_region_id=None,
                source_item_id="opening%d" % index,
                source_bbox=opening["bbox_pixels"],
                source="local_raster_geometry",
                producer=opening.get("producer") or UNKNOWN,
                confidence=opening.get("confidence"),
                grounding_status=GROUNDING_GEOMETRY,
                supporting_functions=[],
                evidence_strength=WEAK,
                independence_key=_independence_key(
                    "opening",
                    panel["panel_id"],
                    opening.get("kind"),
                    opening.get("raster_patch_sha256") or opening["bbox_pixels"],
                ),
                notes=[
                    "access evidence: an opening never determines a room "
                    "function by itself",
                ],
                extra={
                    "opening_kind": opening.get("kind"),
                    "centre_pixels": list(_centre(opening["bbox_pixels"])),
                },
            )
        )
    return items


def _relation_evidence(panel: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    for index, relation in enumerate(panel["reading"].get("relations") or [], 1):
        if not isinstance(relation, dict):
            continue
        kind = relation.get("kind")
        if kind not in ("adjacency", "circulation"):
            continue
        evidence_type = ADJACENCY if kind == "adjacency" else CIRCULATION
        items.append(
            _item(
                evidence_type=evidence_type,
                architectural_signal=(
                    SIGNAL_ADJACENCY_RELATION
                    if kind == "adjacency"
                    else SIGNAL_CIRCULATION_SPACE
                ),
                source_panel_id=panel["panel_id"],
                source_item_id="relation%d" % index,
                source="published_plan_relation",
                producer="architectural_vision_interpreter_v1",
                confidence=relation.get("confidence"),
                grounding_status=GROUNDING_RELATION,
                supporting_functions=[],
                evidence_strength=WEAK,
                independence_key=_independence_key(
                    "relation", panel["panel_id"], kind, tuple(relation.get("between") or ())
                ),
                notes=["contextual relation evidence; never a function by itself"],
                extra={"between": relation.get("between") or []},
            )
        )
    return items


def _circulation_evidence(panel: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    for index, space in enumerate(panel["reading"].get("circulation") or [], 1):
        items.append(
            _item(
                evidence_type=CIRCULATION,
                architectural_signal=SIGNAL_CIRCULATION_SPACE,
                source_panel_id=panel["panel_id"],
                source_item_id="circulation%d" % index,
                source="published_plan_circulation",
                producer="architectural_vision_interpreter_v1",
                confidence="LOW",
                grounding_status=GROUNDING_RELATION,
                supporting_functions=["circulation"],
                evidence_strength=SUPPORTING,
                independence_key=_independence_key(
                    "circulation", panel["panel_id"], space
                ),
                notes=["a circulation space named by the plan's own reading"],
                extra={"space": space},
            )
        )
    return items


def _geometry_evidence(region: Dict[str, Any], panel_id: str) -> Dict[str, Any]:
    """Enclosure geometry. Context only: it supports NO function.

    Aspect ratio, size and sheet position are recorded for audit but are
    explicitly excluded from function determination.
    """
    box = region["bbox_pixels"]
    width = max(1, box[2] - box[0])
    height = max(1, box[3] - box[1])
    return _item(
        evidence_type=GEOMETRY,
        architectural_signal=SIGNAL_ENCLOSURE_GEOMETRY,
        source_panel_id=panel_id,
        source_region_id=region["region_id"],
        source_item_id=region["region_id"],
        source_bbox=box,
        source="local_raster_wall_boundaries",
        producer="local_plan_symbols_v1",
        confidence=region.get("confidence"),
        grounding_status=GROUNDING_GEOMETRY,
        supporting_functions=[],
        evidence_strength=WEAK,
        independence_key=_independence_key(
            "geometry", panel_id, region["region_id"]
        ),
        notes=[
            "enclosure geometry is WEAK context and never determines a "
            "function; sheet position is excluded entirely",
        ],
        extra={
            "aspect_ratio": round(width / height, 4),
            "pixel_area": width * height,
            "wall_levels": region.get("wall_levels"),
            "trusted_region": region["trusted"],
            "position_used_for_function": False,
        },
    )


def _conflict_evidence(
    region: Dict[str, Any],
    panel_id: str,
    hypotheses: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """The explicit NEGATIVE_OR_CONFLICTING record of a CONFLICTED region.

    An incompatible co-location is evidence in its own right: it is published
    with strength CONTRADICTING and it supports NO function, so a future
    reasoner can neither resolve the region nor lose the reason it cannot.
    """
    functions = [h["function"] for h in hypotheses]
    pair: List[str] = []
    for candidate in INCOMPATIBLE_FUNCTION_PAIRS:
        if all(function in functions for function in candidate):
            pair = sorted(candidate)
            break
    return _item(
        evidence_type=NEGATIVE_OR_CONFLICTING,
        architectural_signal=SIGNAL_INCOMPATIBLE_EVIDENCE_PAIR,
        source_panel_id=panel_id,
        source_region_id=region["region_id"],
        source_item_id="conflict:" + "+".join(pair or sorted(functions)),
        source_bbox=region["bbox_pixels"],
        source="architectural_function_evidence_v1",
        producer="architectural_function_evidence_v1",
        confidence=region.get("confidence"),
        grounding_status=GROUNDING_GEOMETRY,
        supporting_functions=[],
        contradicting_functions=pair or sorted(functions),
        evidence_strength=CONTRADICTING,
        independence_key=_independence_key(
            "conflict", panel_id, region["region_id"], tuple(pair or sorted(functions))
        ),
        notes=[
            "incompatible architectural evidence co-located in ONE trusted "
            "region; the region is never resolved",
        ],
        extra={"conflicting_functions": pair or sorted(functions)},
    )


def _transfer_evidence(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Corresponding-panel transfers that the trusted data already provides."""
    items = []
    fusion = plan.get("fusion") or {}
    for index, transfer in enumerate(
        fusion.get("corresponding_label_transfers") or [], 1
    ):
        if not isinstance(transfer, dict):
            continue
        function = transfer.get("space")
        box = _bbox(transfer.get("bbox_pixels"))
        target_region = transfer.get("corresponding_region_id")
        items.append(
            _item(
                evidence_type=CORRESPONDING_PANEL,
                architectural_signal=SIGNAL_CORRESPONDING_PANEL_TRANSFER,
                source_panel_id=transfer.get("source_panel_id"),
                source_region_id=transfer.get("associated_region_id"),
                source_item_id="transfer%d" % index,
                source_bbox=box,
                source="corresponding_panel_region_match",
                producer="local_plan_sheet_v1",
                confidence=transfer.get("confidence"),
                grounding_status=GROUNDING_GROUNDED,
                transport_status=TRANSPORT_TRANSPORTED,
                supporting_functions=[function] if function else [],
                evidence_strength=DIRECT,
                independence_key=_independence_key(
                    "transfer",
                    transfer.get("source_panel_id"),
                    transfer.get("associated_region_id"),
                    transfer.get("evidence"),
                ),
                same_underlying_evidence=True,
                correspondence={
                    "source_panel_id": transfer.get("source_panel_id"),
                    "source_region_id": transfer.get("associated_region_id"),
                    "target_panel_id": fusion.get("geometry_panel_id"),
                    "target_region_id": target_region,
                    "correspondence_method": transfer.get("transfer"),
                    "correspondence_confidence": transfer.get("confidence"),
                    "same_underlying_evidence": True,
                },
                notes=[
                    "the SAME underlying evidence on a corresponding panel; "
                    "never a second independent vote",
                ],
                extra={"target_region_id": target_region},
            )
        )
    return items


# ==================================================
# PART 3/4 — PER-REGION STRENGTH + INDEPENDENCE
# ==================================================


def _region_hypotheses(
    region_evidence: List[Dict[str, Any]], trusted: bool
) -> Tuple[List[Dict[str, Any]], str]:
    """Derive representable hypothesis states — NEVER a resolution.

    Independence is computed from the underlying evidence identity, so a
    repeated observation of the same source contributes one vote, not several.
    """
    key_of = {
        item["evidence_id"]: item["independence_key"] for item in region_evidence
    }

    roles: Dict[str, List[str]] = {}
    classes: Dict[str, List[str]] = {}
    direct: Dict[str, List[str]] = {}

    for item in region_evidence:
        eid = item["evidence_id"]
        if item["evidence_strength"] == DIRECT:
            for function in item["supporting_functions"]:
                direct.setdefault(function, []).append(eid)
        role = item.get("combination_role")
        if role:
            roles.setdefault(role, []).append(eid)
        symbol_class = item.get("symbol_class")
        if symbol_class:
            classes.setdefault(symbol_class, []).append(eid)

    def independent(eids: Iterable[str]) -> int:
        return len({key_of.get(e) for e in eids})

    store: Dict[str, Dict[str, Any]] = {}

    def set_hypothesis(function, strength, reason, eids):
        eids = sorted(set(eids))
        current = store.get(function)
        if current is None or _STRENGTH_RANK[strength] > _STRENGTH_RANK[
            current["evidence_strength"]
        ]:
            store[function] = {
                "function": function,
                "evidence_strength": strength,
                "reason": reason,
                "evidence_ids": eids,
            }
        else:
            current["evidence_ids"] = sorted(set(current["evidence_ids"]) | set(eids))

    for function, eids in direct.items():
        set_hypothesis(
            function, DIRECT, "grounded label inside a trusted enclosure", eids
        )

    def seating() -> List[str]:
        return [e for c in _SEATING_CLASSES for e in classes.get(c, [])]

    # --- sleeping -------------------------------------------------------
    beds = roles.get("sleeping_object", [])
    wardrobes = roles.get("wardrobe_member", [])
    if beds and wardrobes:
        set_hypothesis(
            "bedroom",
            STRONG,
            "bed plus an independent wardrobe/storage symbol in the SAME region",
            beds + wardrobes,
        )
    elif independent(beds) >= 2:
        set_hypothesis(
            "bedroom",
            STRONG,
            "two independent bed symbols in the SAME region",
            beds,
        )
    elif beds:
        set_hypothesis(
            "bedroom",
            SUPPORTING,
            "a single bed symbol: supportive only, never sufficient alone",
            beds,
        )

    # --- sanitary -------------------------------------------------------
    sanitary = roles.get("sanitary_fixture", [])
    if independent(sanitary) >= 2:
        set_hypothesis(
            "bathroom",
            STRONG,
            "a sanitary fixture cluster (>= 2 independent fixture symbols)",
            sanitary,
        )
    elif sanitary:
        set_hypothesis(
            "bathroom",
            SUPPORTING,
            "a single sanitary fixture: supportive only",
            sanitary,
        )

    # --- dining ---------------------------------------------------------
    surfaces = roles.get("dining_surface", [])
    seats = seating()
    if surfaces and independent(seats) >= 2:
        set_hypothesis(
            "dining",
            STRONG,
            "a dining surface plus multiple seating symbols in the SAME region",
            surfaces + seats,
        )
    elif surfaces:
        set_hypothesis(
            "dining",
            SUPPORTING,
            "a dining surface without corroborating seating",
            surfaces,
        )
    elif independent(seats) >= 2:
        set_hypothesis(
            "dining",
            SUPPORTING,
            "seating without a dining surface: unresolved",
            seats,
        )

    # --- kitchen --------------------------------------------------------
    counters = roles.get("kitchen_counter", [])
    basins = roles.get("kitchen_basin", [])
    if counters and basins:
        set_hypothesis(
            "kitchen",
            STRONG,
            "a counter/basin arrangement in the SAME region",
            counters + basins,
        )
    elif counters or basins:
        set_hypothesis(
            "kitchen",
            SUPPORTING,
            "a single kitchen symbol: supportive only",
            counters + basins,
        )

    # --- living ---------------------------------------------------------
    # The brief's own model: a sofa is supportive only. Seating alone never
    # reaches STRONG, so living-room evidence can never resolve by itself.
    living = [e for c in ("sofa", "seating") for e in classes.get(c, [])]
    if living:
        set_hypothesis(
            "living room",
            SUPPORTING,
            "seating is supportive evidence only and never resolves a room",
            living,
        )

    if not trusted:
        for entry in store.values():
            if _STRENGTH_RANK[entry["evidence_strength"]] > _STRENGTH_RANK[
                SUPPORTING
            ]:
                entry["evidence_strength"] = SUPPORTING
                entry["reason"] = (
                    entry["reason"] + " [capped: the enclosure is not trusted]"
                )

    hypotheses = sorted(
        store.values(),
        key=lambda e: (-_STRENGTH_RANK[e["evidence_strength"]], e["function"]),
    )

    functions = [h["function"] for h in hypotheses]
    conflicted = False
    for pair in INCOMPATIBLE_FUNCTION_PAIRS:
        present = [f for f in functions if f in pair]
        if len(present) == len(pair):
            conflicted = True
            break

    for hypothesis in hypotheses:
        strength = hypothesis["evidence_strength"]
        hypothesis["independent_sources"] = independent(hypothesis["evidence_ids"])
        if strength == DIRECT:
            state = SUPPORTED
        elif strength == STRONG:
            state = (
                SUPPORTED if hypothesis["independent_sources"] >= 2 else PROBABLE
            )
        elif len(hypotheses) >= 2:
            state = AMBIGUOUS
        else:
            state = INSUFFICIENT
        hypothesis["state"] = state

    if conflicted:
        region_state = CONFLICTED
    elif any(h["state"] == SUPPORTED for h in hypotheses):
        region_state = SUPPORTED
    elif any(h["state"] == PROBABLE for h in hypotheses):
        region_state = PROBABLE
    elif len(hypotheses) >= 2:
        region_state = AMBIGUOUS
    elif len(hypotheses) == 1:
        region_state = INSUFFICIENT
    else:
        region_state = UNKNOWN

    return hypotheses, region_state


def evidence_state_for(evidence_items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """PUBLIC, PURE helper: the representable state of a set of evidence.

    This is the contract's own state machine, exposed so a future reasoner (and
    the W4.1 tests) can ask what a set of evidence supports WITHOUT resolving a
    function. It always returns ``resolved_function: None``.
    """
    items = [i for i in evidence_items if isinstance(i, dict)]
    trusted = all(
        i.get("trusted_region", True)
        for i in items
        if i.get("evidence_type") == GEOMETRY
    )
    hypotheses, state = _region_hypotheses(items, trusted)
    return {
        "state": state,
        "hypotheses": hypotheses,
        "resolved_function": None,
        "resolution_withheld": True,
    }


# ==================================================
# PART 5 — CORRESPONDING PANEL POLICY
# ==================================================


def _existing_correspondences(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The correspondences the trusted data ALREADY provides. Read-only.

    W4.1 creates none. A correspondence is reported with the method and
    confidence the producing layer recorded, never re-derived here.
    """
    local = plan.get("local_plan_reading") or {}
    sheet = local.get("sheet_structure") or {}
    records = []
    for record in sheet.get("corresponding_regions") or []:
        if not isinstance(record, dict):
            continue
        records.append(
            {
                "panel_ids": list(record.get("panel_ids") or []),
                "pairs": [
                    {
                        "left_region_id": pair.get("left_region_id"),
                        "right_region_id": pair.get("right_region_id"),
                        "centroid_distance_normalized": pair.get(
                            "centroid_distance_normalized"
                        ),
                        "area_ratio": pair.get("area_ratio"),
                        "mutual_centroid_containment": pair.get(
                            "mutual_centroid_containment"
                        ),
                    }
                    for pair in record.get("pairs") or []
                    if isinstance(pair, dict)
                ],
                "correspondence_method": record.get("source"),
                "correspondence_confidence": record.get("confidence"),
            }
        )
    return records


# ==================================================
# ZONE LOOKUP (existing project convention, imported lazily)
# ==================================================


def _zone(function: Optional[str]) -> Optional[str]:
    if not function:
        return None
    try:
        from core.vision.architectural_vision_interpreter_v1 import SPACE_ZONE

        return SPACE_ZONE.get(function)
    except Exception:
        return None


# ==================================================
# PUBLIC BUILDER
# ==================================================


def build_architectural_function_evidence(
    plan: Dict[str, Any],
) -> Dict[str, Any]:
    """Collect and classify the architectural function evidence of a plan.

    PURE and READ-ONLY: `plan` is never mutated and nothing is resolved.
    """
    if not isinstance(plan, dict):
        return _empty_contract()

    panels = _panels(plan)
    evidence_items: List[Dict[str, Any]] = []
    panel_records: List[Dict[str, Any]] = []

    for panel in panels:
        panel_id = panel["panel_id"]
        reading = panel["reading"]
        regions = _regions(reading)

        panel_items: List[Dict[str, Any]] = []
        panel_items.extend(_label_evidence(panel))
        panel_items.extend(_furniture_evidence(panel))
        panel_items.extend(_relation_evidence(panel))
        panel_items.extend(_circulation_evidence(panel))

        # Enclosure geometry: ONE evidence item per region, context only.
        geometry_items = [_geometry_evidence(region, panel_id) for region in regions]
        panel_items.extend(geometry_items)

        # An opening is attributed to a region ONLY by its OWN centre, and only
        # as WEAK access evidence. Overlapping regions may legitimately claim
        # the same opening, so each containing region gets its own copy with its
        # own evidence id; an opening in no region stays unbound.
        for opening in _opening_evidence(panel):
            claimed = [
                region
                for region in regions
                if _contains(region["bbox_pixels"], opening["centre_pixels"])
            ]
            if not claimed:
                panel_items.append(opening)
                continue
            for region in claimed:
                panel_items.append(
                    dict(
                        opening,
                        source_region_id=region["region_id"],
                        region_attribution_status=REGION_ATTRIBUTION_BOUND,
                        evidence_id=_evidence_id(
                            opening["evidence_id"] + ":" + region["region_id"]
                        ),
                    )
                )

        region_records = []
        for region in regions:
            region_id = region["region_id"]
            region_items = [
                item
                for item in panel_items
                if item.get("source_region_id") == region_id
            ]
            hypotheses, state = _region_hypotheses(region_items, region["trusted"])
            # A CONFLICTED region publishes the conflict as evidence in its own
            # right. It supports no function, so it is created AFTER the
            # hypotheses are derived and can never create one.
            if state == CONFLICTED:
                conflict = _conflict_evidence(region, panel_id, hypotheses)
                region_items = region_items + [conflict]
                panel_items.append(conflict)
            types_present = sorted({i["evidence_type"] for i in region_items})
            bound_functions = [
                i for i in region_items if i["evidence_type"] in (FURNITURE, FIXTURE)
            ]
            region_records.append(
                {
                    "panel_id": panel_id,
                    "region_id": region_id,
                    "region_bbox_pixels": region["bbox_pixels"],
                    "region_confidence": region.get("confidence"),
                    "trusted_region": region["trusted"],
                    "wall_levels": region.get("wall_levels"),
                    "evidence_ids": sorted(i["evidence_id"] for i in region_items),
                    "evidence_types_present": types_present,
                    "grounded_text_evidence": any(
                        i["evidence_type"] == DIRECT_SEMANTIC for i in region_items
                    ),
                    "furniture_evidence": any(
                        i["evidence_type"] == FURNITURE for i in bound_functions
                    ),
                    "fixture_evidence": any(
                        i["evidence_type"] == FIXTURE for i in bound_functions
                    ),
                    "access_opening_evidence": any(
                        i["evidence_type"] == OPENING_ACCESS for i in region_items
                    ),
                    "corresponding_panel_evidence": any(
                        i["evidence_type"] == CORRESPONDING_PANEL
                        for i in region_items
                    ),
                    "geometry_only": not any(
                        i["evidence_type"] not in (GEOMETRY, OPENING_ACCESS)
                        for i in region_items
                    ),
                    "no_semantic_evidence": not any(
                        i["evidence_type"]
                        in (DIRECT_SEMANTIC, FURNITURE, FIXTURE, CORRESPONDING_PANEL)
                        for i in region_items
                    ),
                    "hypotheses": hypotheses,
                    "region_state": state,
                    "resolved_function": None,
                    "resolution_withheld": True,
                }
            )

        evidence_items.extend(panel_items)

        panel_records.append(
            {
                "panel_id": panel_id,
                "role": panel["role"],
                "region_count": len(regions),
                "regions": region_records,
                "evidence_ids": sorted(i["evidence_id"] for i in panel_items),
                "panel_level_evidence_ids": sorted(
                    i["evidence_id"]
                    for i in panel_items
                    if not i.get("source_region_id")
                ),
                "unbound_evidence_ids": sorted(
                    i["evidence_id"]
                    for i in panel_items
                    if i.get("region_attribution_status")
                    == REGION_ATTRIBUTION_NOT_TRANSPORTED
                ),
            }
        )

    transfers = _transfer_evidence(plan)
    evidence_items.extend(transfers)

    unbound = [
        i
        for i in evidence_items
        if i.get("region_attribution_status")
        in (REGION_ATTRIBUTION_NOT_TRANSPORTED, REGION_ATTRIBUTION_NOT_RECORDED)
    ]
    unbound_ids = {i["evidence_id"] for i in unbound}

    type_counts: Dict[str, int] = {}
    strength_counts: Dict[str, int] = {}
    reason_counts: Dict[str, int] = {}
    for item in evidence_items:
        type_counts[item["evidence_type"]] = (
            type_counts.get(item["evidence_type"], 0) + 1
        )
        strength_counts[item["evidence_strength"]] = (
            strength_counts.get(item["evidence_strength"], 0) + 1
        )
        if item["evidence_id"] in unbound_ids:
            reason_counts[item["region_attribution_status"]] = (
                reason_counts.get(item["region_attribution_status"], 0) + 1
            )

    state_counts: Dict[str, int] = {}
    for panel in panel_records:
        for region in panel["regions"]:
            state_counts[region["region_state"]] = (
                state_counts.get(region["region_state"], 0) + 1
            )

    contract = {
        "contract": CONTRACT,
        "version": VERSION,
        "mode": MODE,
        "read_only": READ_ONLY,
        "provider_independent": PROVIDER_INDEPENDENT,
        "model_independent": MODEL_INDEPENDENT,
        "resolves_functions": RESOLVES_FUNCTIONS,
        "resolution_withheld": RESOLUTION_WITHHELD,
        "resolved_functions": {},
        "changes_inferred_functions": CHANGES_INFERRED_FUNCTIONS,
        "changes_named_spaces": CHANGES_NAMED_SPACES,
        "changes_unit_count": CHANGES_UNIT_COUNT,
        "changes_role_classification": CHANGES_ROLE_CLASSIFICATION,
        "creates_region_bindings": CREATES_REGION_BINDINGS,
        "creates_correspondences": CREATES_CORRESPONDENCES,
        "evidence_types": list(EVIDENCE_TYPES),
        "evidence_strengths": list(EVIDENCE_STRENGTHS),
        "resolution_states": list(RESOLUTION_STATES),
        "panels": panel_records,
        "evidence_items": evidence_items,
        "evidence_without_region": sorted(unbound_ids),
        "evidence_without_region_reasons": reason_counts,
        "corresponding_panel": {
            "existing_correspondences": _existing_correspondences(plan),
            "transfers": sorted(i["evidence_id"] for i in transfers),
            "created_new_correspondences": False,
            "policy": (
                "a transported item is the SAME underlying evidence and is "
                "never counted as a second independent vote; no correspondence "
                "is created in this phase"
            ),
        },
        "independence": {
            "rule": (
                "evidence is independent only when its underlying source "
                "differs; repeated OCR passes of the same pixels, and the same "
                "object transported from another panel, are the SAME evidence"
            ),
            "identity_source": "raster_patch_sha256 / label identity / region id",
            "independence_keys": sorted({i["independence_key"] for i in evidence_items}),
        },
        "counts": {
            "evidence_items": len(evidence_items),
            "evidence_types": type_counts,
            "strengths": strength_counts,
            "region_states": state_counts,
            "regions_total": sum(
                panel["region_count"] for panel in panel_records
            ),
            "evidence_without_region": len(unbound),
            "evidence_without_region_reasons": reason_counts,
        },
        "notes": [
            "SHADOW MODE: this structure is additive and changes no existing "
            "field of the plan reading",
            "geometry, aspect ratio, size and sheet position never determine a "
            "function",
            "absence of furniture never implies a function",
            "no region is bound and no correspondence is created in this phase",
        ],
    }
    return contract


def _empty_contract() -> Dict[str, Any]:
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "mode": MODE,
        "read_only": READ_ONLY,
        "resolves_functions": False,
        "resolution_withheld": True,
        "resolved_functions": {},
        "panels": [],
        "evidence_items": [],
        "evidence_without_region": [],
        "counts": {"evidence_items": 0},
        "notes": ["no plan reading supplied"],
    }


print(
    "[W4.1] ARCHITECTURAL FUNCTION EVIDENCE v1 ONLINE "
    "(shadow mode, read-only, no function resolution)"
)
