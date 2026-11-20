"""StructuralSupportCandidateAnalysisV1.

Design-driven structural support / grid CANDIDATE analysis.

This module proves architectural compatibility only.  It consumes the Design-05
architecture-owned ``StructuralArchitectureInputV1`` (through
``StructuralArchitectureInputAdapterV1``) and produces candidate analysis.

It does NOT:

- generate final columns, beams, slabs, reinforcement, foundations or loads
- choose a structural system, member sizes or material grades
- choose grid spacing, bay count or column count
- resize, round or redefine the architectural envelope
- move architecture to align supports across floors
- execute the existing StructuralGridEngine / StructuralElementEngine
- run BIM / IFC / CAD / render

Grid policy: every axis opportunity is derived from actual architectural
geometry (envelope boundaries, eligibility-region corners, proven exclusion
cuts).  Irregular spacing and unequal bays are the natural result; fixed
4 m / equal-bay / n-by-m division are never applied.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from core.structure.structural_architecture_input_adapter_v1 import (
    StructuralArchitectureInputAdapterError,
    StructuralArchitectureInputAdapterV1,
)


CONTRACT = "StructuralSupportCandidateAnalysisV1"
VERSION = "1.0"

STATUS_ANALYSIS_READY = "ANALYSIS_READY"
STATUS_ANALYSIS_READY_WITH_GAPS = "ANALYSIS_READY_WITH_GAPS"
STATUS_INSUFFICIENT_ARCHITECTURAL_INPUT = "INSUFFICIENT_ARCHITECTURAL_INPUT"
STATUS_NO_VALID_SUPPORT_REGION = "NO_VALID_SUPPORT_REGION"
STATUS_PROTECTED_ZONE_CONFLICT = "PROTECTED_ZONE_CONFLICT"
STATUS_LEGACY_GRID_ASSUMPTION_BLOCKED = "LEGACY_GRID_ASSUMPTION_BLOCKED"
STATUS_STRUCTURAL_INPUT_REQUIRED = "STRUCTURAL_INPUT_REQUIRED"
STATUS_STALE_PARENT = "STALE_PARENT"
STATUS_FAILED = "FAILED"

STATUSES = (
    STATUS_ANALYSIS_READY,
    STATUS_ANALYSIS_READY_WITH_GAPS,
    STATUS_INSUFFICIENT_ARCHITECTURAL_INPUT,
    STATUS_NO_VALID_SUPPORT_REGION,
    STATUS_PROTECTED_ZONE_CONFLICT,
    STATUS_LEGACY_GRID_ASSUMPTION_BLOCKED,
    STATUS_STRUCTURAL_INPUT_REQUIRED,
    STATUS_STALE_PARENT,
    STATUS_FAILED,
)

WALL_ALIGNED = "WALL_ALIGNED_SUPPORT_OPPORTUNITY"
ELIGIBILITY_CORNER = "ELIGIBILITY_CORNER_SUPPORT_OPPORTUNITY"
INTERIOR = "INTERIOR_SUPPORT_OPPORTUNITY"

TOLERANCE = 1e-6


class StructuralSupportCandidateAnalysisV1(dict):
    """Versioned, dict-compatible candidate-analysis contract."""

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as error:  # pragma: no cover - attribute convenience
            raise AttributeError(item) from error


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


def _ring(value: Any) -> list[list[float]]:
    if not isinstance(value, (list, tuple)):
        return []
    output: list[list[float]] = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return []
        try:
            output.append([float(point[0]), float(point[1])])
        except (TypeError, ValueError):
            return []
    return output


def _shape_from_surface(surface: Any) -> Polygon | None:
    """Read a Design-05 ``{"exterior": [...], "holes": [...]}`` surface."""
    if not isinstance(surface, Mapping):
        return None
    exterior = _ring(surface.get("exterior"))
    if len(exterior) < 4:
        return None
    holes = [
        hole for hole in (_ring(item) for item in surface.get("holes", []) or [])
        if len(hole) >= 4
    ]
    try:
        shape = Polygon(exterior, holes)
    except (ValueError, TypeError):
        return None
    if not shape.is_valid:
        shape = shape.buffer(0)
    return shape if isinstance(shape, Polygon) and not shape.is_empty else None


def _shape_from_polygon(polygon: Any) -> Polygon | None:
    ring = _ring(polygon)
    if len(ring) < 4:
        return None
    try:
        shape = Polygon(ring)
    except (ValueError, TypeError):
        return None
    if not shape.is_valid:
        shape = shape.buffer(0)
    return shape if isinstance(shape, Polygon) and not shape.is_empty else None


def _floor_ids(item: Mapping[str, Any]) -> set[str]:
    values = item.get("floor_ids")
    if isinstance(values, (list, tuple)):
        return {str(value) for value in values}
    value = item.get("floor_id")
    return {str(value)} if value is not None else set()


def _unique_sorted(values: list[float]) -> list[float]:
    output: list[float] = []
    for value in sorted(values):
        if not output or abs(value - output[-1]) > TOLERANCE:
            output.append(value)
    return output


class StructuralSupportCandidateAnalyzerV1:
    """Produce architecture-compatible support / grid candidate analysis."""

    VERSION = VERSION

    def __init__(self):
        self.adapter = StructuralArchitectureInputAdapterV1()

    # --------------------------------------------------
    # public entry
    # --------------------------------------------------

    def analyze(self, design_05_candidate: Mapping[str, Any]) -> StructuralSupportCandidateAnalysisV1:
        try:
            adapted = self.adapter.adapt(design_05_candidate)
        except StructuralArchitectureInputAdapterError as error:
            return self._blocked(error.status, error.conflicts, design_05_candidate)

        guard = adapted.get("engine_input_projection", {}).get(
            "structural_architecture_input", {}
        )
        legacy_claims = [
            key for key in ("grid_spacing", "column_count", "beam_layout")
            if guard.get(key) is not None
        ]
        if legacy_claims:
            return self._blocked(
                STATUS_LEGACY_GRID_ASSUMPTION_BLOCKED,
                [{"code": "AUTHORITATIVE_GRID_ASSUMPTION_IN_ARCHITECTURAL_INPUT",
                  "fields": legacy_claims}],
                design_05_candidate,
                adapted=adapted,
            )

        readiness = adapted.get("source", {}).get("readiness_status")
        conflicts = [
            item for item in (adapted.get("unresolved_architectural_gaps") or [])
            if isinstance(item, Mapping) and item.get("code") == "PROTECTED_ZONE_OUTSIDE_ARCHITECTURAL_ENVELOPE"
        ]
        if readiness == "BLOCKED_PROTECTED_ZONE" or conflicts:
            return self._blocked(
                STATUS_PROTECTED_ZONE_CONFLICT,
                conflicts or [{"code": "BLOCKED_PROTECTED_ZONE"}],
                design_05_candidate, adapted=adapted,
            )

        floors = self._analyze_floors(adapted)
        eligible_area = sum(item["eligible_area_m2"] for item in floors)

        if not floors:
            return self._blocked(
                STATUS_INSUFFICIENT_ARCHITECTURAL_INPUT,
                [{"code": "NO_USABLE_FLOOR_ENVELOPE"}], design_05_candidate, adapted=adapted,
            )
        if eligible_area <= TOLERANCE:
            return self._document(
                STATUS_NO_VALID_SUPPORT_REGION, adapted, floors,
                warnings=[{"code": "NO_ELIGIBLE_SUPPORT_AREA"}],
            )

        return self._document(
            STATUS_ANALYSIS_READY_WITH_GAPS if adapted["status"] != "READY" else STATUS_ANALYSIS_READY,
            adapted, floors,
        )

    # --------------------------------------------------
    # per-floor candidate analysis
    # --------------------------------------------------

    def _analyze_floors(self, adapted: Mapping[str, Any]) -> list[dict[str, Any]]:
        regions_by_floor: dict[str, list[Mapping[str, Any]]] = {}
        for region in adapted.get("eligible_support_regions", []) or []:
            if isinstance(region, Mapping) and region.get("floor_id") is not None:
                regions_by_floor.setdefault(str(region["floor_id"]), []).append(region)

        exclusions = [
            item for item in (adapted.get("exclusions") or []) if isinstance(item, Mapping)
        ]

        output: list[dict[str, Any]] = []
        for floor in adapted.get("floors", []) or []:
            floor_id = str(floor["floor_id"])
            envelope = _shape_from_polygon(floor.get("envelope_polygon"))
            if envelope is None:
                continue

            active: list[tuple[Mapping[str, Any], Polygon]] = []
            for exclusion in exclusions:
                if floor_id not in _floor_ids(exclusion):
                    continue
                shape = _shape_from_polygon(exclusion.get("polygon"))
                if shape is not None and shape.intersects(envelope):
                    active.append((exclusion, shape))

            regions = regions_by_floor.get(floor_id, [])
            eligible_shapes = [
                shape for shape in (
                    _shape_from_surface(surface)
                    for region in regions
                    for surface in (region.get("polygons") or [])
                ) if shape is not None
            ]
            # An empty eligible geometry (no eligible regions, or all degenerate)
            # fails closed: every opportunity is rejected.
            eligible_union = unary_union(eligible_shapes) if eligible_shapes else Polygon()

            opportunities, rejected = self._opportunities(
                envelope, active, eligible_union
            )
            axis_x = _unique_sorted([item["point"][0] for item in opportunities])
            axis_y = _unique_sorted([item["point"][1] for item in opportunities])

            output.append({
                "floor_id": floor_id,
                "architectural_envelope_ref": floor.get("geometry_ref"),
                "envelope_polygon": deepcopy(floor.get("envelope_polygon")),
                "envelope_area_m2": round(float(envelope.area), 6),
                "eligible_region_refs": sorted(str(item.get("region_id")) for item in regions),
                "excluded_region_refs": sorted(
                    str(item.get("zone_id") or item.get("constraint_id") or item.get("void_id"))
                    for item, _ in active
                ),
                "eligible_area_m2": round(float(eligible_union.area), 6),
                "candidate_axis_opportunities": {"x": axis_x, "y": axis_y},
                "candidate_support_regions": opportunities,
                "rejected_support_regions": rejected,
                "span_observations": {
                    "x": self._spans(axis_x),
                    "y": self._spans(axis_y),
                    "span_criteria_available": False,
                    "span_criteria_source": "STRUCTURAL_ENGINEERING_CRITERIA_NOT_ARCHITECTURAL",
                },
                "committed_columns": [],
                "committed_beams": [],
                "support_stack_forced": False,
                "architecture_moved": False,
            })
        return output

    def _opportunities(
        self,
        envelope: Polygon,
        active: list[tuple[Mapping[str, Any], Polygon]],
        eligible_union: Polygon | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        raw: list[tuple[float, float, str]] = []
        for x, y in list(envelope.exterior.coords)[:-1]:
            raw.append((float(x), float(y), "ARCHITECTURAL_ENVELOPE_BOUNDARY"))
        for exclusion, shape in active:
            for x, y in list(shape.exterior.coords)[:-1]:
                raw.append((float(x), float(y), "PROVEN_EXCLUSION_BOUNDARY"))

        seen: set[tuple[float, float]] = set()
        opportunities: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for x, y, source in sorted(raw):
            key = (round(x, 6), round(y, 6))
            if key in seen:
                continue
            seen.add(key)
            point = Point(x, y)
            blocking = next(
                (item for item, shape in active if shape.contains(point)), None
            )
            if blocking is not None:
                rejected.append({
                    "point": [x, y],
                    "source": source,
                    "reason": "INSIDE_PROVEN_EXCLUSION",
                    "excluded_by": str(
                        blocking.get("zone_id") or blocking.get("constraint_id")
                        or blocking.get("void_id")
                    ),
                    "committed": False,
                })
                continue
            if not eligible_union.covers(point):
                rejected.append({
                    "point": [x, y],
                    "source": source,
                    "reason": "OUTSIDE_ELIGIBLE_SUPPORT_REGION",
                    "excluded_by": None,
                    "committed": False,
                })
                continue
            on_envelope = envelope.boundary.distance(point) <= TOLERANCE
            on_exclusion = any(
                shape.boundary.distance(point) <= TOLERANCE for _, shape in active
            )
            if on_envelope:
                kind = WALL_ALIGNED
            elif on_exclusion:
                kind = ELIGIBILITY_CORNER
            else:
                kind = INTERIOR
            opportunities.append({
                "point": [x, y],
                "kind": kind,
                "source": source,
                "committed": False,
                "is_column": False,
                "structural_candidate_only": True,
            })
        return opportunities, rejected

    @staticmethod
    def _spans(values: list[float]) -> dict[str, Any]:
        spans = [
            round(values[index + 1] - values[index], 6)
            for index in range(len(values) - 1)
        ]
        return {
            "axis_values": list(values),
            "observed_spans": spans,
            "min_span": min(spans) if spans else None,
            "max_span": max(spans) if spans else None,
            "unequal_spans": len({round(span, 6) for span in spans}) > 1,
            "equal_bay_forced": False,
        }

    # --------------------------------------------------
    # cross-floor compatibility
    # --------------------------------------------------

    @staticmethod
    def _cross_floor(floors: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for previous, current in zip(floors, floors[1:]):
            prev_x = {round(value, 6) for value in previous["candidate_axis_opportunities"]["x"]}
            curr_x = {round(value, 6) for value in current["candidate_axis_opportunities"]["x"]}
            prev_y = {round(value, 6) for value in previous["candidate_axis_opportunities"]["y"]}
            curr_y = {round(value, 6) for value in current["candidate_axis_opportunities"]["y"]}
            aligned = len((prev_x & curr_x)) + len((prev_y & curr_y))
            unaligned = len((prev_x ^ curr_x)) + len((prev_y ^ curr_y))
            output.append({
                "floor_pair": [previous["floor_id"], current["floor_id"]],
                "aligned_axis_opportunities": aligned,
                "unaligned_axis_opportunities": unaligned,
                "condition": (
                    "SUPPORT_POSITIONS_NOT_VERTICALLY_ALIGNED" if unaligned else "ALIGNED"
                ),
                "support_stack_forced": False,
                "architecture_moved": False,
                "floor_geometry_reused": False,
            })
        return output

    # --------------------------------------------------
    # documents
    # --------------------------------------------------

    def _document(
        self,
        status: str,
        adapted: Mapping[str, Any],
        floors: list[dict[str, Any]],
        warnings: list[dict[str, Any]] | None = None,
    ) -> StructuralSupportCandidateAnalysisV1:
        unresolved = [
            {**deepcopy(dict(item)), "classification": item.get("classification", "STRUCTURAL_DESIGN_INPUT_GAP")}
            for item in (adapted.get("structural_input_requirements") or [])
            if isinstance(item, Mapping)
        ]
        unresolved.extend(
            deepcopy(dict(item)) for item in (adapted.get("unresolved_architectural_gaps") or [])
            if isinstance(item, Mapping)
        )

        document = StructuralSupportCandidateAnalysisV1({
            "contract": CONTRACT,
            "version": VERSION,
            "status": status,
            "analysis_status": status,
            "authority": "STRUCTURAL_CANDIDATE_ANALYSIS_ARCHITECTURE_SUBORDINATE",
            "source": deepcopy(dict(adapted.get("source", {}))),
            "adapter_hash": adapted.get("adapter_hash"),
            "readiness_status": adapted.get("source", {}).get("readiness_status"),
            "floors": floors,
            "cross_floor_continuity": self._cross_floor(floors),
            "external_space_constraints": deepcopy(
                adapted.get("external_space_constraints", [])
            ),
            "candidate_axis_opportunities": {
                "x": _unique_sorted([
                    value for floor in floors
                    for value in floor["candidate_axis_opportunities"]["x"]
                ]),
                "y": _unique_sorted([
                    value for floor in floors
                    for value in floor["candidate_axis_opportunities"]["y"]
                ]),
            },
            "candidate_support_regions": [
                {**deepcopy(item), "floor_id": floor["floor_id"]}
                for floor in floors for item in floor["candidate_support_regions"]
            ],
            "rejected_support_regions": [
                {**deepcopy(item), "floor_id": floor["floor_id"]}
                for floor in floors for item in floor["rejected_support_regions"]
            ],
            "span_observations": [
                {"floor_id": floor["floor_id"], **deepcopy(floor["span_observations"])}
                for floor in floors
            ],
            "strategy_candidates": [{
                "strategy_id": "DESIGN_DRIVEN_ARCHITECTURAL_AXIS_CANDIDATE",
                "basis": "architectural_axis_opportunities",
                "grid_spacing": None,
                "equal_bay": False,
                "fixed_four_meter_grid": False,
                "committed": False,
                "requires_structural_inputs": [
                    item.get("input") for item in unresolved
                    if item.get("classification") == "STRUCTURAL_DESIGN_INPUT_GAP"
                ],
            }],
            "unresolved_structural_inputs": unresolved,
            "committed_structural_elements": [],
            "generated_columns": [],
            "generated_beams": [],
            "grid_policy": {
                "design_driven": True,
                "irregular_spacing_allowed": True,
                "unequal_bays_allowed": True,
                "fixed_four_meter_authority": False,
                "equal_bay_by_default": False,
                "arbitrary_division": False,
                "envelope_rounded_to_grid": False,
                "outer_supports_deleted_to_fit_spacing": False,
            },
            "warnings": list(warnings or []),
            "provenance": {
                "analyzer": "StructuralSupportCandidateAnalyzerV1",
                "analyzer_version": VERSION,
                "structural_synthesis_performed": False,
                "final_members_committed": False,
                "structural_grid_engine_executed": False,
                "structural_element_engine_executed": False,
                "bim_ifc_executed": False,
                "architecture_mutated": False,
                "design_05_mutated": False,
                "member_sizing_performed": False,
                "loads_defined": False,
                "structural_system_selected": False,
            },
        })
        document["analysis_hash"] = self.hash(document)
        return document

    def _blocked(
        self,
        status: str,
        conflicts: list[dict[str, Any]],
        design_05_candidate: Mapping[str, Any],
        adapted: Mapping[str, Any] | None = None,
    ) -> StructuralSupportCandidateAnalysisV1:
        source = {}
        if isinstance(adapted, Mapping):
            source = deepcopy(dict(adapted.get("source", {})))
        elif isinstance(design_05_candidate, Mapping):
            source = {
                "candidate_id": design_05_candidate.get("candidate_id"),
                "candidate_version": design_05_candidate.get("candidate_version"),
                "candidate_hash": design_05_candidate.get("candidate_hash"),
            }
        document = StructuralSupportCandidateAnalysisV1({
            "contract": CONTRACT,
            "version": VERSION,
            "status": status,
            "analysis_status": status,
            "authority": "STRUCTURAL_CANDIDATE_ANALYSIS_ARCHITECTURE_SUBORDINATE",
            "source": source,
            "adapter_hash": None if not isinstance(adapted, Mapping) else adapted.get("adapter_hash"),
            "readiness_status": source.get("readiness_status"),
            "floors": [],
            "cross_floor_continuity": [],
            "candidate_axis_opportunities": {"x": [], "y": []},
            "candidate_support_regions": [],
            "rejected_support_regions": [],
            "span_observations": [],
            "strategy_candidates": [],
            "unresolved_structural_inputs": [],
            "committed_structural_elements": [],
            "generated_columns": [],
            "generated_beams": [],
            "grid_policy": {
                "design_driven": True,
                "fixed_four_meter_authority": False,
                "equal_bay_by_default": False,
                "envelope_rounded_to_grid": False,
            },
            "warnings": [{"code": status, "conflicts": deepcopy(conflicts)}],
            "provenance": {
                "analyzer": "StructuralSupportCandidateAnalyzerV1",
                "analyzer_version": VERSION,
                "structural_synthesis_performed": False,
                "final_members_committed": False,
                "structural_grid_engine_executed": False,
                "structural_element_engine_executed": False,
                "bim_ifc_executed": False,
                "architecture_mutated": False,
                "design_05_mutated": False,
            },
        })
        document["analysis_hash"] = self.hash(document)
        return document

    # --------------------------------------------------
    # deterministic hash
    # --------------------------------------------------

    @staticmethod
    def hash(document: Mapping[str, Any]) -> str:
        payload = {
            key: value for key, value in document.items()
            if key not in ("analysis_hash", "provenance")
        }
        return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


structural_support_candidate_analysis = StructuralSupportCandidateAnalyzerV1()


def analyze_structural_support_candidates_v1(
    design_05_candidate: Mapping[str, Any],
) -> StructuralSupportCandidateAnalysisV1:
    """Module-level convenience wrapper over the canonical analyzer."""
    return structural_support_candidate_analysis.analyze(design_05_candidate)


__all__ = [
    "CONTRACT", "VERSION", "STATUSES",
    "STATUS_ANALYSIS_READY", "STATUS_ANALYSIS_READY_WITH_GAPS",
    "STATUS_INSUFFICIENT_ARCHITECTURAL_INPUT", "STATUS_NO_VALID_SUPPORT_REGION",
    "STATUS_PROTECTED_ZONE_CONFLICT", "STATUS_LEGACY_GRID_ASSUMPTION_BLOCKED",
    "STATUS_STRUCTURAL_INPUT_REQUIRED", "STATUS_STALE_PARENT", "STATUS_FAILED",
    "WALL_ALIGNED", "ELIGIBILITY_CORNER", "INTERIOR",
    "StructuralSupportCandidateAnalysisV1", "StructuralSupportCandidateAnalyzerV1",
    "analyze_structural_support_candidates_v1", "structural_support_candidate_analysis",
]
