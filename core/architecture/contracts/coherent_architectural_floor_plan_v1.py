"""CoherentArchitecturalFloorPlanV1.

Versioned, derived contract for a COHERENT metric floor plan realization.

It sits on top of the existing plan lineage (``ArchitecturalPlanModel`` +
``architectural_geometry`` + ``ArchitecturalHumanReadablePlanV1``) and resolves
one narrow, proven gap: floors whose layout is still ``abstract_grid`` are
promoted to metric footprints by the geometry engine without any grid
resolution, producing overlapping rooms.

This contract records a non-overlapping metric partition derived from the
architecture's own resolved room areas + its own abstract relative ordering +
its own resolved envelope evidence.  It never mutates a source candidate and
never invents architecture.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any


CONTRACT = "CoherentArchitecturalFloorPlanV1"
VERSION = "1.0"

STATUS_RESOLVED = "RESOLVED"
STATUS_RESOLVED_WITH_GAPS = "RESOLVED_WITH_GAPS"
STATUS_SPATIAL_LAYOUT_UNRESOLVED = "SPATIAL_LAYOUT_UNRESOLVED"
STATUS_PROGRAM_AREA_EXCEEDS_ENVELOPE = "PROGRAM_AREA_EXCEEDS_AVAILABLE_ENVELOPE"
STATUS_ENVELOPE_PENDING = "FLOOR_ENVELOPE_REALIZATION_PENDING"
STATUS_FAILED = "FAILED"

VALID_STATUSES = (
    STATUS_RESOLVED, STATUS_RESOLVED_WITH_GAPS, STATUS_SPATIAL_LAYOUT_UNRESOLVED,
    STATUS_PROGRAM_AREA_EXCEEDS_ENVELOPE, STATUS_ENVELOPE_PENDING, STATUS_FAILED,
)

# ---- overlap / layout root-cause vocabulary -------------------------------
PROGRAM_CONFLICT = "PROGRAM_CONFLICT"
LAYOUT_PLACEMENT_CONFLICT = "LAYOUT_PLACEMENT_CONFLICT"
FOOTPRINT_GENERATION_CONFLICT = "FOOTPRINT_GENERATION_CONFLICT"
FLOOR_ASSIGNMENT_CONFLICT = "FLOOR_ASSIGNMENT_CONFLICT"
ZONE_PACKING_CONFLICT = "ZONE_PACKING_CONFLICT"
CORRIDOR_CONFLICT = "CORRIDOR_CONFLICT"
EXTERNAL_SPACE_CONFLICT = "EXTERNAL_SPACE_CONFLICT"
LEGACY_GRID_ASSUMPTION = "LEGACY_GRID_ASSUMPTION"
POST_LAYOUT_GEOMETRY_DRIFT = "POST_LAYOUT_GEOMETRY_DRIFT"
WALL_DERIVATION_ONLY = "WALL_DERIVATION_ONLY"
OTHER_PROVEN_CAUSE = "OTHER_PROVEN_CAUSE"

ROOT_CAUSES = (
    PROGRAM_CONFLICT, LAYOUT_PLACEMENT_CONFLICT, FOOTPRINT_GENERATION_CONFLICT,
    FLOOR_ASSIGNMENT_CONFLICT, ZONE_PACKING_CONFLICT, CORRIDOR_CONFLICT,
    EXTERNAL_SPACE_CONFLICT, LEGACY_GRID_ASSUMPTION, POST_LAYOUT_GEOMETRY_DRIFT,
    WALL_DERIVATION_ONLY, OTHER_PROVEN_CAUSE,
)

# ---- placement / stair states ---------------------------------------------
PLACED = "PLACED"
UNRESOLVED_SPACE = "UNRESOLVED"

EXTERIOR_WALL = "EXTERIOR_WALL"
INTERIOR_SHARED_WALL = "INTERIOR_SHARED_WALL"

STAIR_CORE_SPACE_RESOLVED = "STAIR_CORE_SPACE_RESOLVED"
STAIR_GEOMETRY_PENDING = "STAIR_GEOMETRY_PENDING"

PROGRAM_AREA_EXCEEDS_AVAILABLE_ENVELOPE = "PROGRAM_AREA_EXCEEDS_AVAILABLE_ENVELOPE"
FLOOR_ENVELOPE_DERIVED_FROM_PROGRAM_AREA = "FLOOR_ENVELOPE_DERIVED_FROM_PROGRAM_AREA"
LAYOUT_ENGINE_ARCHITECTURAL_INCOMPATIBILITY = "LAYOUT_ENGINE_ARCHITECTURAL_INCOMPATIBILITY"

# ---- deterministic plan styles --------------------------------------------
COHERENT_STYLE_TOKENS: dict[str, dict[str, Any]] = {
    "CFP_ENVELOPE": {"stroke": "#111111", "stroke_width": 2.6, "fill": "none"},
    "CFP_SPACE": {"stroke": "#333333", "stroke_width": 1.0, "fill": "#ffffff", "fill_opacity": 0.0},
    "CFP_SPACE_PUBLIC": {"stroke": "#3f6fa8", "stroke_width": 1.0, "fill": "#3f6fa8", "fill_opacity": 0.06},
    "CFP_SPACE_SERVICE": {"stroke": "#b5561f", "stroke_width": 1.0, "fill": "#b5561f", "fill_opacity": 0.06},
    "CFP_SPACE_CIRCULATION": {"stroke": "#7a4fbf", "stroke_width": 1.0, "fill": "#7a4fbf", "fill_opacity": 0.08},
    "CFP_SPACE_PRIVATE": {"stroke": "#1f7a3d", "stroke_width": 1.0, "fill": "#1f7a3d", "fill_opacity": 0.06},
    "CFP_SPACE_EXTERNAL": {"stroke": "#2f8f6b", "stroke_width": 1.0, "fill": "#2f8f6b", "fill_opacity": 0.12},
    "CFP_STAIR_CORE": {"stroke": "#8a5a00", "stroke_width": 1.6, "fill": "#8a5a00", "fill_opacity": 0.10},
    "CFP_WALL_INTERIOR": {"stroke": "#444444", "stroke_width": 1.2, "fill": "none"},
    "CFP_UNRESOLVED": {"stroke": "#b02020", "stroke_width": 1.2, "fill": "none", "dash": "3 2"},
}

COHERENT_SVG_BACKGROUND = "#ffffff"
COHERENT_SVG_PADDING = 1.2
COHERENT_SVG_UNITS_PER_METRE = 18.0
COHERENT_SVG_FONT_FAMILY = "monospace"


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        _json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def canonical_coherent_floor_document(value: Mapping[str, Any]) -> str:
    payload = deepcopy(dict(value))
    payload.pop("plan_hash", None)
    payload.pop("provenance", None)
    payload.pop("svg_by_floor", None)
    payload.pop("diagnostic_svg_by_floor", None)
    return _canonical(payload)


def coherent_floor_semantic_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_coherent_floor_document(value).encode("utf-8")
    ).hexdigest()


def svg_sha256(svg: str) -> str:
    return hashlib.sha256(str(svg).encode("utf-8")).hexdigest()


def verify_coherent_floor_plan(value: Mapping[str, Any]) -> bool:
    if not isinstance(value, Mapping):
        return False
    if value.get("contract") != CONTRACT or str(value.get("version")) != VERSION:
        return False
    if value.get("plan_status") not in VALID_STATUSES:
        return False
    if not isinstance(value.get("floors"), list):
        return False
    stored = value.get("plan_hash")
    return isinstance(stored, str) and stored == coherent_floor_semantic_hash(value)


__all__ = [
    "CONTRACT", "VERSION", "VALID_STATUSES", "ROOT_CAUSES", "COHERENT_STYLE_TOKENS",
    "COHERENT_SVG_BACKGROUND", "COHERENT_SVG_PADDING", "COHERENT_SVG_UNITS_PER_METRE",
    "COHERENT_SVG_FONT_FAMILY",
    "STATUS_RESOLVED", "STATUS_RESOLVED_WITH_GAPS", "STATUS_SPATIAL_LAYOUT_UNRESOLVED",
    "STATUS_PROGRAM_AREA_EXCEEDS_ENVELOPE", "STATUS_ENVELOPE_PENDING", "STATUS_FAILED",
    "PROGRAM_CONFLICT", "LAYOUT_PLACEMENT_CONFLICT", "FOOTPRINT_GENERATION_CONFLICT",
    "FLOOR_ASSIGNMENT_CONFLICT", "ZONE_PACKING_CONFLICT", "CORRIDOR_CONFLICT",
    "EXTERNAL_SPACE_CONFLICT", "LEGACY_GRID_ASSUMPTION", "POST_LAYOUT_GEOMETRY_DRIFT",
    "WALL_DERIVATION_ONLY", "OTHER_PROVEN_CAUSE",
    "PLACED", "UNRESOLVED_SPACE", "EXTERIOR_WALL", "INTERIOR_SHARED_WALL",
    "STAIR_CORE_SPACE_RESOLVED", "STAIR_GEOMETRY_PENDING",
    "PROGRAM_AREA_EXCEEDS_AVAILABLE_ENVELOPE",
    "FLOOR_ENVELOPE_DERIVED_FROM_PROGRAM_AREA",
    "LAYOUT_ENGINE_ARCHITECTURAL_INCOMPATIBILITY",
    "canonical_coherent_floor_document", "coherent_floor_semantic_hash",
    "svg_sha256", "verify_coherent_floor_plan",
]
