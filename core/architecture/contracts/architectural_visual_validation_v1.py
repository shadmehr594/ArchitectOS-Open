"""ArchitecturalVisualValidationArtifactV1.

Read-only visual inspection contract for the current architectural design chain.

This is an INSPECTION OUTPUT, never a design result.  It carries deterministic
vector records plus a deterministic SVG rendering so a human can see exactly
where the approved architectural baseline, its derived candidates and the
structural support-opportunity state currently stand.

Hard rules:

- no geometry invention, smoothing, snapping, repair or envelope enlargement
- no layout beautification that changes geometric meaning
- missing source evidence becomes structured ``unresolved_visual_evidence``
- the artifact is a pure projection; sources are never mutated
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any


CONTRACT = "ArchitecturalVisualValidationArtifactV1"
VERSION = "1.0"

STATUS_READY = "READY"
STATUS_READY_WITH_UNRESOLVED = "READY_WITH_UNRESOLVED"
STATUS_INSUFFICIENT_VISUAL_SOURCE = "INSUFFICIENT_VISUAL_SOURCE"
STATUS_FAILED = "FAILED"

VALID_ARTIFACT_STATUSES = (
    STATUS_READY,
    STATUS_READY_WITH_UNRESOLVED,
    STATUS_INSUFFICIENT_VISUAL_SOURCE,
    STATUS_FAILED,
)

# Logical views, in deterministic order.
VIEW_ARCHITECTURAL_PLAN = "ARCHITECTURAL_PLAN"
VIEW_OPENING_ACCESS = "OPENING_ACCESS"
VIEW_VOIDS_PROTECTED_ZONES = "VOIDS_PROTECTED_ZONES"
VIEW_STRUCTURAL_READINESS = "STRUCTURAL_READINESS"
VIEW_SUPPORT_CANDIDATE_SUMMARY = "SUPPORT_CANDIDATE_SUMMARY"

VALIDATION_LAYERS = (
    VIEW_ARCHITECTURAL_PLAN,
    VIEW_OPENING_ACCESS,
    VIEW_VOIDS_PROTECTED_ZONES,
    VIEW_STRUCTURAL_READINESS,
    VIEW_SUPPORT_CANDIDATE_SUMMARY,
)

# Semantic style tokens.  Every token maps to a FIXED style so the SVG output is
# byte-deterministic: no random colours, no runtime themes, no dynamic styling.
STYLE_TOKENS: dict[str, dict[str, Any]] = {
    "FLOOR_ENVELOPE": {"stroke": "#111111", "stroke_width": 1.4, "fill": "none", "dash": None, "radius": None},
    "SPACE_BOUNDARY": {"stroke": "#3f6fa8", "stroke_width": 0.7, "fill": "none", "dash": None, "radius": None},
    "EXTERNAL_SPACE": {"stroke": "#2f8f6b", "stroke_width": 0.8, "fill": "#2f8f6b", "fill_opacity": 0.08, "dash": None, "radius": None},
    "WALL": {"stroke": "#333333", "stroke_width": 1.0, "fill": "none", "dash": None, "radius": None},
    "OPENING": {"stroke": "#b5561f", "stroke_width": 1.8, "fill": "none", "dash": None, "radius": None},
    "ACCESS": {"stroke": "#7a4fbf", "stroke_width": 0.9, "fill": "none", "dash": "3 2", "radius": None},
    "VERTICAL_VOID": {"stroke": "#b02020", "stroke_width": 1.0, "fill": "#b02020", "fill_opacity": 0.10, "dash": "4 2", "radius": None},
    "PROTECTED_ZONE": {"stroke": "#b02020", "stroke_width": 0.9, "fill": "#b02020", "fill_opacity": 0.06, "dash": None, "radius": None},
    "ELIGIBILITY_REGION": {"stroke": "#1f7a3d", "stroke_width": 0.8, "fill": "#1f7a3d", "fill_opacity": 0.07, "dash": None, "radius": None},
    "EXCLUSION_REGION": {"stroke": "#8a8a8a", "stroke_width": 0.8, "fill": "#8a8a8a", "fill_opacity": 0.10, "dash": "2 2", "radius": None},
    "SUPPORT_CANDIDATE": {"stroke": "#7b241c", "stroke_width": 0.5, "fill": "#c0392b", "dash": None, "radius": 0.18},
    "REJECTED_SUPPORT_REGION": {"stroke": "#8a8a8a", "stroke_width": 0.5, "fill": "#ffffff", "dash": "1 1", "radius": 0.14},
}

GEOMETRY_TYPES = ("POLYGON", "POLYLINE", "POINT", "RELATION_MARKER")

# Deterministic SVG presentation constants.
SVG_BACKGROUND = "#ffffff"
SVG_PADDING = 0.6
SVG_UNITS_PER_METRE = 24.0
SVG_FONT_FAMILY = "monospace"


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def canonical_visual_validation_document(value: Mapping[str, Any]) -> str:
    """Deterministic Unicode JSON over the semantic payload.

    ``provenance`` (bookkeeping) and the derived ``svg`` strings are excluded so
    the artifact hash tracks SEMANTICS; presentation determinism is tracked
    separately by each floor's ``svg_sha256``.
    """
    if not isinstance(value, Mapping):
        raise ValueError("visual validation artifact must be a mapping")
    payload = deepcopy(dict(value))
    payload.pop("artifact_hash", None)
    payload.pop("provenance", None)
    for floor in payload.get("floor_artifacts", []) or []:
        if isinstance(floor, dict):
            floor.pop("svg", None)
    return json.dumps(
        _json_value(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def visual_validation_semantic_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_visual_validation_document(value).encode("utf-8")
    ).hexdigest()


def svg_sha256(svg: str) -> str:
    return hashlib.sha256(str(svg).encode("utf-8")).hexdigest()


def verify_visual_validation_artifact(value: Mapping[str, Any]) -> bool:
    if not isinstance(value, Mapping):
        return False
    if value.get("contract") != CONTRACT or str(value.get("version")) != VERSION:
        return False
    if value.get("artifact_status") not in VALID_ARTIFACT_STATUSES:
        return False
    if not isinstance(value.get("floor_artifacts"), list):
        return False
    if not isinstance(value.get("validation_layers"), list):
        return False
    stored = value.get("artifact_hash")
    return isinstance(stored, str) and stored == visual_validation_semantic_hash(value)


__all__ = [
    "CONTRACT", "VERSION", "VALID_ARTIFACT_STATUSES", "VALIDATION_LAYERS",
    "STYLE_TOKENS", "GEOMETRY_TYPES",
    "STATUS_READY", "STATUS_READY_WITH_UNRESOLVED",
    "STATUS_INSUFFICIENT_VISUAL_SOURCE", "STATUS_FAILED",
    "VIEW_ARCHITECTURAL_PLAN", "VIEW_OPENING_ACCESS", "VIEW_VOIDS_PROTECTED_ZONES",
    "VIEW_STRUCTURAL_READINESS", "VIEW_SUPPORT_CANDIDATE_SUMMARY",
    "SVG_BACKGROUND", "SVG_PADDING", "SVG_UNITS_PER_METRE", "SVG_FONT_FAMILY",
    "canonical_visual_validation_document", "visual_validation_semantic_hash",
    "svg_sha256", "verify_visual_validation_artifact",
]
