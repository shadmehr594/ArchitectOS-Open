"""ArchitecturalHumanReadablePlanV1 + ArchitecturalPlanCompletenessV1.

Read-only, derived contracts that bind the REAL architectural design chain to a
human-readable floor plan and an honest completeness report.

These contracts extend the existing plan lineage — ``ArchitecturalPlanModel``
(semantic program) + ``architectural_geometry`` (metric geometry) +
``PlanDrawingServiceV1``/``PlanModelToSceneAdapterV1`` (canonical drawing path).
They deliberately do NOT introduce a competing plan architecture: they are a
projection over what the pipeline already produces.

Hard rules:

- geometry is never invented, repaired, snapped or smoothed
- a plan element without realized geometry is recorded as
  MISSING_REALIZATION, never drawn
- every record carries its provenance
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any


CONTRACT = "ArchitecturalHumanReadablePlanV1"
COMPLETENESS_CONTRACT = "ArchitecturalPlanCompletenessV1"
VERSION = "1.0"

# ---- plan statuses ---------------------------------------------------------
STATUS_COMPLETE = "COMPLETE"
STATUS_COMPLETE_WITH_WARNINGS = "COMPLETE_WITH_WARNINGS"
STATUS_PARTIAL = "PARTIAL"
STATUS_SEMANTIC_ONLY = "SEMANTIC_ONLY"
STATUS_GEOMETRY_INCOMPLETE = "GEOMETRY_INCOMPLETE"
STATUS_FAILED = "FAILED"

PLAN_STATUSES = (
    STATUS_COMPLETE, STATUS_COMPLETE_WITH_WARNINGS, STATUS_PARTIAL,
    STATUS_SEMANTIC_ONLY, STATUS_GEOMETRY_INCOMPLETE, STATUS_FAILED,
)

# ---- realization classification -------------------------------------------
REALIZED = "GEOMETRY_REALIZED"
PARTIAL = "GEOMETRY_PARTIAL"
SEMANTIC_ONLY = "SEMANTIC_ONLY"
CONTRACT_ONLY = "CONTRACT_ONLY"
LEGACY = "LEGACY"
MISSING_REALIZATION = "MISSING_REALIZATION"
READY_FOR_PLAN_DISPLAY = "READY_FOR_PLAN_DISPLAY"

REALIZATION_CLASSES = (
    REALIZED, PARTIAL, SEMANTIC_ONLY, CONTRACT_ONLY, LEGACY,
    MISSING_REALIZATION, READY_FOR_PLAN_DISPLAY,
)

# ---- missing realization stage codes --------------------------------------
INTERNAL_WALL_REALIZATION_MISSING = "INTERNAL_WALL_REALIZATION_MISSING"
DOOR_GEOMETRY_REALIZATION_MISSING = "DOOR_GEOMETRY_REALIZATION_MISSING"
WINDOW_GEOMETRY_REALIZATION_MISSING = "WINDOW_GEOMETRY_REALIZATION_MISSING"
STAIR_GEOMETRY_REALIZATION_MISSING = "STAIR_GEOMETRY_REALIZATION_MISSING"
ELEVATOR_GEOMETRY_REALIZATION_MISSING = "ELEVATOR_GEOMETRY_REALIZATION_MISSING"
ROOM_FOOTPRINT_REALIZATION_MISSING = "ROOM_FOOTPRINT_REALIZATION_MISSING"
PARKING_REALIZATION_MISSING = "PARKING_REALIZATION_MISSING"
FLOOR_ENVELOPE_REALIZATION_MISSING = "FLOOR_ENVELOPE_REALIZATION_MISSING"
ROOF_REALIZATION_MISSING = "ROOF_REALIZATION_MISSING"
EXTERNAL_SPACE_REALIZATION_MISSING = "EXTERNAL_SPACE_REALIZATION_MISSING"
ENTRANCE_GEOMETRY_REALIZATION_MISSING = "ENTRANCE_GEOMETRY_REALIZATION_MISSING"

MISSING_STAGE_CODES = (
    INTERNAL_WALL_REALIZATION_MISSING, DOOR_GEOMETRY_REALIZATION_MISSING,
    WINDOW_GEOMETRY_REALIZATION_MISSING, STAIR_GEOMETRY_REALIZATION_MISSING,
    ELEVATOR_GEOMETRY_REALIZATION_MISSING, ROOM_FOOTPRINT_REALIZATION_MISSING,
    PARKING_REALIZATION_MISSING, FLOOR_ENVELOPE_REALIZATION_MISSING,
    ROOF_REALIZATION_MISSING, EXTERNAL_SPACE_REALIZATION_MISSING,
    ENTRANCE_GEOMETRY_REALIZATION_MISSING,
)

# ---- deterministic plan styles --------------------------------------------
PLAN_STYLE_TOKENS: dict[str, dict[str, Any]] = {
    "PLAN_SPACE": {"stroke": "#111111", "stroke_width": 0.9, "fill": "#ffffff", "fill_opacity": 0.0},
    "PLAN_SPACE_EXTERNAL": {"stroke": "#2f8f6b", "stroke_width": 0.9, "fill": "#2f8f6b", "fill_opacity": 0.10},
    "PLAN_SPACE_CIRCULATION": {"stroke": "#7a4fbf", "stroke_width": 0.8, "fill": "#7a4fbf", "fill_opacity": 0.06},
    "PLAN_WALL_EXTERIOR": {"stroke": "#111111", "stroke_width": 2.4, "fill": "none"},
    "PLAN_WALL_INTERIOR": {"stroke": "#444444", "stroke_width": 1.2, "fill": "none"},
    "PLAN_DOOR": {"stroke": "#b5561f", "stroke_width": 1.6, "fill": "none"},
    "PLAN_WINDOW": {"stroke": "#1f6fb5", "stroke_width": 1.6, "fill": "none"},
    "PLAN_STAIR": {"stroke": "#8a5a00", "stroke_width": 1.0, "fill": "#8a5a00", "fill_opacity": 0.08},
    "PLAN_ELEVATOR": {"stroke": "#8a5a00", "stroke_width": 1.0, "fill": "#8a5a00", "fill_opacity": 0.08},
    "PLAN_LABEL": {"stroke": "none", "stroke_width": 0.0, "fill": "#111111"},
    "PLAN_LABEL_EXTERNAL": {"stroke": "none", "stroke_width": 0.0, "fill": "#1d6b4f"},
    "PLAN_UNRESOLVED": {"stroke": "#b02020", "stroke_width": 1.2, "fill": "none", "dash": "3 2"},
}

PLAN_SVG_BACKGROUND = "#ffffff"
PLAN_SVG_PADDING = 1.0
PLAN_SVG_UNITS_PER_METRE = 20.0
PLAN_SVG_FONT_FAMILY = "monospace"


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


def canonical_plan_document(value: Mapping[str, Any]) -> str:
    payload = deepcopy(dict(value))
    payload.pop("plan_hash", None)
    payload.pop("provenance", None)
    payload.pop("svg_by_floor", None)
    payload.pop("diagnostic_svg_by_floor", None)
    return _canonical(payload)


def plan_semantic_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_plan_document(value).encode("utf-8")).hexdigest()


def svg_sha256(svg: str) -> str:
    return hashlib.sha256(str(svg).encode("utf-8")).hexdigest()


def verify_human_readable_plan(value: Mapping[str, Any]) -> bool:
    if not isinstance(value, Mapping):
        return False
    if value.get("contract") != CONTRACT or str(value.get("version")) != VERSION:
        return False
    if value.get("plan_status") not in PLAN_STATUSES:
        return False
    if not isinstance(value.get("floors"), list):
        return False
    completeness = value.get("completeness")
    if not isinstance(completeness, Mapping):
        return False
    if completeness.get("contract") != COMPLETENESS_CONTRACT:
        return False
    if completeness.get("completeness_status") not in PLAN_STATUSES:
        return False
    stored = value.get("plan_hash")
    return isinstance(stored, str) and stored == plan_semantic_hash(value)


def display_label(name: Any) -> str:
    """Deterministic human-readable label from a canonical semantic name.

    Presentation only: the canonical name is preserved verbatim in metadata.
    """
    text = str(name or "").strip()
    if not text:
        return ""
    for separator in ("_", "-"):
        text = text.replace(separator, " ")
    return " ".join(text.split()).upper()


__all__ = [
    "CONTRACT", "COMPLETENESS_CONTRACT", "VERSION", "PLAN_STATUSES", "REALIZATION_CLASSES",
    "MISSING_STAGE_CODES", "PLAN_STYLE_TOKENS", "PLAN_SVG_BACKGROUND", "PLAN_SVG_PADDING",
    "PLAN_SVG_UNITS_PER_METRE", "PLAN_SVG_FONT_FAMILY",
    "STATUS_COMPLETE", "STATUS_COMPLETE_WITH_WARNINGS", "STATUS_PARTIAL",
    "STATUS_SEMANTIC_ONLY", "STATUS_GEOMETRY_INCOMPLETE", "STATUS_FAILED",
    "REALIZED", "PARTIAL", "SEMANTIC_ONLY", "CONTRACT_ONLY", "LEGACY",
    "MISSING_REALIZATION", "READY_FOR_PLAN_DISPLAY",
    "INTERNAL_WALL_REALIZATION_MISSING", "DOOR_GEOMETRY_REALIZATION_MISSING",
    "WINDOW_GEOMETRY_REALIZATION_MISSING", "STAIR_GEOMETRY_REALIZATION_MISSING",
    "ELEVATOR_GEOMETRY_REALIZATION_MISSING", "ROOM_FOOTPRINT_REALIZATION_MISSING",
    "PARKING_REALIZATION_MISSING", "FLOOR_ENVELOPE_REALIZATION_MISSING",
    "ROOF_REALIZATION_MISSING", "EXTERNAL_SPACE_REALIZATION_MISSING",
    "ENTRANCE_GEOMETRY_REALIZATION_MISSING",
    "canonical_plan_document", "plan_semantic_hash", "svg_sha256",
    "verify_human_readable_plan", "display_label",
]
