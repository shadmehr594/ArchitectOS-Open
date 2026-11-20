"""Architectural layout intelligence contracts.

Narrow extension of the coherent-plan lineage (01A / 01A2) adding:

- ``ArchitecturalLayoutCandidateV1``    — one deterministic layout candidate
- ``ArchitecturalLayoutEvaluationV1``   — structured architectural evaluation
- ``ArchitecturalDesignQualityGateV1``  — the acceptance gate

Treemap / rectangle packing is only a CANDIDATE GEOMETRY GENERATOR.  Selection is
performed by architectural evaluation, never by the packing algorithm.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any


CANDIDATE_CONTRACT = "ArchitecturalLayoutCandidateV1"
EVALUATION_CONTRACT = "ArchitecturalLayoutEvaluationV1"
GATE_CONTRACT = "ArchitecturalDesignQualityGateV1"
VERSION = "1.0"

# ---- relationship priority classes ----------------------------------------
CRITICAL = "CRITICAL"
HIGH = "HIGH"
PREFERRED = "PREFERRED"
OPTIONAL = "OPTIONAL"
FORBIDDEN = "FORBIDDEN"

PRIORITY_CLASSES = (CRITICAL, HIGH, PREFERRED, OPTIONAL, FORBIDDEN)

# ---- quality gate statuses -------------------------------------------------
QUALITY_PASS = "ARCHITECTURAL_QUALITY_PASS"
QUALITY_PASS_WITH_WARNINGS = "ARCHITECTURAL_QUALITY_PASS_WITH_WARNINGS"
QUALITY_FAIL = "ARCHITECTURAL_QUALITY_FAIL"

QUALITY_STATUSES = (QUALITY_PASS, QUALITY_PASS_WITH_WARNINGS, QUALITY_FAIL)

# ---- entrance hierarchy ----------------------------------------------------
ENTRANCE_HIERARCHY_VALID = "ENTRANCE_HIERARCHY_VALID"
ENTRANCE_HIERARCHY_WEAK = "ENTRANCE_HIERARCHY_WEAK"
ENTRANCE_HIERARCHY_INVALID = "ENTRANCE_HIERARCHY_INVALID"
ENTRANCE_EDGE_UNRESOLVED = "ENTRANCE_EDGE_UNRESOLVED"

ENTRANCE_STATUSES = (
    ENTRANCE_HIERARCHY_VALID, ENTRANCE_HIERARCHY_WEAK,
    ENTRANCE_HIERARCHY_INVALID, ENTRANCE_EDGE_UNRESOLVED,
)

# ---- vertical core ---------------------------------------------------------
CORE_ALIGNED = "CORE_ALIGNED_ACROSS_SERVED_FLOORS"
CORE_MISALIGNED = "CORE_MISALIGNED_ACROSS_SERVED_FLOORS"
CORE_MISSING = "CORE_MISSING_ON_SERVED_FLOOR"

CORE_STATUSES = (CORE_ALIGNED, CORE_MISALIGNED, CORE_MISSING)

# ---- hard rejection codes --------------------------------------------------
ROOM_OVERLAP_DETECTED = "ROOM_OVERLAP_DETECTED"
SERVED_UPPER_FLOOR_WITHOUT_VERTICAL_CORE = "SERVED_UPPER_FLOOR_WITHOUT_VERTICAL_CORE"
CORE_NOT_ALIGNED_ACROSS_FLOORS = "CORE_NOT_ALIGNED_ACROSS_FLOORS"
ENTRANCE_CANNOT_REACH_PUBLIC_CIRCULATION = "ENTRANCE_CANNOT_REACH_PUBLIC_CIRCULATION"
CRITICAL_ADJACENCY_MISSING = "CRITICAL_ADJACENCY_MISSING"
PROTECTED_CORE_OVERLAPPED = "PROTECTED_CORE_OVERLAPPED"
UPPER_FLOOR_CORRIDOR_WITHOUT_ARRIVAL = "UPPER_FLOOR_CORRIDOR_WITHOUT_ARRIVAL"
REQUIRED_ROOM_ISOLATED = "REQUIRED_ROOM_ISOLATED"
FORBIDDEN_RELATION_PRESENT = "FORBIDDEN_RELATION_PRESENT"
ENVELOPE_NOT_REALIZED = "ENVELOPE_NOT_REALIZED"

HARD_REJECTION_CODES = (
    ROOM_OVERLAP_DETECTED, SERVED_UPPER_FLOOR_WITHOUT_VERTICAL_CORE,
    CORE_NOT_ALIGNED_ACROSS_FLOORS, ENTRANCE_CANNOT_REACH_PUBLIC_CIRCULATION,
    CRITICAL_ADJACENCY_MISSING, PROTECTED_CORE_OVERLAPPED,
    UPPER_FLOOR_CORRIDOR_WITHOUT_ARRIVAL, REQUIRED_ROOM_ISOLATED,
    FORBIDDEN_RELATION_PRESENT, ENVELOPE_NOT_REALIZED,
)

# ---- evaluation components -------------------------------------------------
SCORE_COMPONENTS = (
    "geometry_validity", "critical_adjacency", "high_adjacency",
    "entrance_hierarchy", "circulation_quality", "vertical_core_continuity",
    "privacy", "public_private_zoning", "service_logic",
    "external_space_relation", "room_proportion_quality",
    "daylight_opportunity", "unresolved_penalty",
)

# ---- proportion ------------------------------------------------------------
PROPORTION_OK = "PROPORTION_OK"
PROPORTION_PATHOLOGICAL = "PROPORTION_PATHOLOGICAL"
PROPORTION_RULE_UNRESOLVED = "PROPORTION_RULE_UNRESOLVED"

# ---- external edge / daylight ---------------------------------------------
EXTERIOR_EDGE_CONTACT = "EXTERIOR_EDGE_CONTACT"
DAYLIGHT_OPPORTUNITY = "DAYLIGHT_OPPORTUNITY"

# ---- deterministic candidate styles ---------------------------------------
CANDIDATE_STYLE_TOKENS: dict[str, dict[str, Any]] = {
    "CAND_ENVELOPE": {"stroke": "#111111", "stroke_width": 2.2, "fill": "none"},
    "CAND_CORE": {"stroke": "#8a5a00", "stroke_width": 1.8, "fill": "#8a5a00", "fill_opacity": 0.14},
    "CAND_SPACE": {"stroke": "#333333", "stroke_width": 0.9, "fill": "#ffffff", "fill_opacity": 0.0},
    "CAND_SPACE_PUBLIC": {"stroke": "#3f6fa8", "stroke_width": 0.9, "fill": "#3f6fa8", "fill_opacity": 0.07},
    "CAND_SPACE_SERVICE": {"stroke": "#b5561f", "stroke_width": 0.9, "fill": "#b5561f", "fill_opacity": 0.07},
    "CAND_SPACE_CIRCULATION": {"stroke": "#7a4fbf", "stroke_width": 0.9, "fill": "#7a4fbf", "fill_opacity": 0.09},
    "CAND_SPACE_PRIVATE": {"stroke": "#1f7a3d", "stroke_width": 0.9, "fill": "#1f7a3d", "fill_opacity": 0.07},
    "CAND_SPACE_EXTERNAL": {"stroke": "#2f8f6b", "stroke_width": 0.9, "fill": "#2f8f6b", "fill_opacity": 0.12},
}

CANDIDATE_SVG_BACKGROUND = "#ffffff"
CANDIDATE_SVG_PADDING = 1.2
CANDIDATE_SVG_UNITS_PER_METRE = 16.0
CANDIDATE_SVG_FONT_FAMILY = "monospace"


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


def canonical_layout_document(value: Mapping[str, Any]) -> str:
    payload = deepcopy(dict(value))
    for key in ("plan_hash", "provenance", "svg_by_floor", "candidate_svg_by_floor",
                "candidate_sheets_by_floor"):
        payload.pop(key, None)
    return _canonical(payload)


def layout_semantic_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_layout_document(value).encode("utf-8")).hexdigest()


def candidate_hash(candidate: Mapping[str, Any]) -> str:
    payload = {key: item for key, item in candidate.items()
               if key not in ("candidate_hash", "svg", "provenance")}
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def svg_sha256(svg: str) -> str:
    return hashlib.sha256(str(svg).encode("utf-8")).hexdigest()


def verify_layout_intelligence(value: Mapping[str, Any]) -> bool:
    if not isinstance(value, Mapping):
        return False
    if value.get("contract") != CANDIDATE_CONTRACT or str(value.get("version")) != VERSION:
        return False
    gate = value.get("quality_gate")
    if not isinstance(gate, Mapping) or gate.get("contract") != GATE_CONTRACT:
        return False
    if gate.get("quality_status") not in QUALITY_STATUSES:
        return False
    stored = value.get("plan_hash")
    return isinstance(stored, str) and stored == layout_semantic_hash(value)


__all__ = [
    "CANDIDATE_CONTRACT", "EVALUATION_CONTRACT", "GATE_CONTRACT", "VERSION",
    "CRITICAL", "HIGH", "PREFERRED", "OPTIONAL", "FORBIDDEN", "PRIORITY_CLASSES",
    "QUALITY_PASS", "QUALITY_PASS_WITH_WARNINGS", "QUALITY_FAIL", "QUALITY_STATUSES",
    "ENTRANCE_HIERARCHY_VALID", "ENTRANCE_HIERARCHY_WEAK",
    "ENTRANCE_HIERARCHY_INVALID", "ENTRANCE_EDGE_UNRESOLVED", "ENTRANCE_STATUSES",
    "CORE_ALIGNED", "CORE_MISALIGNED", "CORE_MISSING", "CORE_STATUSES",
    "ROOM_OVERLAP_DETECTED", "SERVED_UPPER_FLOOR_WITHOUT_VERTICAL_CORE",
    "CORE_NOT_ALIGNED_ACROSS_FLOORS", "ENTRANCE_CANNOT_REACH_PUBLIC_CIRCULATION",
    "CRITICAL_ADJACENCY_MISSING", "PROTECTED_CORE_OVERLAPPED",
    "UPPER_FLOOR_CORRIDOR_WITHOUT_ARRIVAL", "REQUIRED_ROOM_ISOLATED",
    "FORBIDDEN_RELATION_PRESENT", "ENVELOPE_NOT_REALIZED", "HARD_REJECTION_CODES",
    "SCORE_COMPONENTS", "PROPORTION_OK", "PROPORTION_PATHOLOGICAL",
    "PROPORTION_RULE_UNRESOLVED", "EXTERIOR_EDGE_CONTACT", "DAYLIGHT_OPPORTUNITY",
    "CANDIDATE_STYLE_TOKENS", "CANDIDATE_SVG_BACKGROUND", "CANDIDATE_SVG_PADDING",
    "CANDIDATE_SVG_UNITS_PER_METRE", "CANDIDATE_SVG_FONT_FAMILY",
    "canonical_layout_document", "layout_semantic_hash", "candidate_hash",
    "svg_sha256", "verify_layout_intelligence",
]
