"""StructuralArchitectureInputAdapterV1.

Narrow, read-only adapter that projects a Design-05
``Design05StructuralReadinessCandidateV1`` (and its embedded
``StructuralArchitectureInputV1``) into a shape the EXISTING structural
consumers can consume, without performing any structural design.

Hard boundaries (enforced by ``adapter_guard``):

- never chooses grid spacing, bay count or column count
- never invents support points
- never resizes / rounds / redefines the architectural envelope
- never fills missing architectural evidence with legacy defaults
- never mutates the Design-05 candidate or its parents

The projection is intentionally lossless: the full richer Design-05 evidence is
carried forward, so a consumer never has to fall back to width/depth-only
inference.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any

from core.architecture.contracts.architectural_structural_readiness_v1 import (
    CONTRACT as DESIGN_05_CONTRACT,
    INPUT_CONTRACT,
    verify_design_05_candidate,
)


CONTRACT = "StructuralArchitectureInputAdapterV1"
VERSION = "1.0"

STATUS_READY = "READY"
STATUS_READY_WITH_GAPS = "READY_WITH_GAPS"
STATUS_INSUFFICIENT_ARCHITECTURAL_INPUT = "INSUFFICIENT_ARCHITECTURAL_INPUT"
STATUS_STRUCTURAL_INPUT_REQUIRED = "STRUCTURAL_INPUT_REQUIRED"
STATUS_STALE_PARENT = "STALE_PARENT"
STATUS_FAILED = "FAILED"

STATUSES = (
    STATUS_READY,
    STATUS_READY_WITH_GAPS,
    STATUS_INSUFFICIENT_ARCHITECTURAL_INPUT,
    STATUS_STRUCTURAL_INPUT_REQUIRED,
    STATUS_STALE_PARENT,
    STATUS_FAILED,
)


class StructuralArchitectureInputAdapterError(ValueError):
    """Raised when a Design-05 candidate cannot be safely adapted."""

    def __init__(self, status: str, conflicts: list[dict[str, Any]]):
        super().__init__(status)
        self.status = status
        self.conflicts = list(conflicts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "conflicts": deepcopy(self.conflicts),
            "adapted": False,
            "architecture_mutated": False,
            "structural_elements_generated": False,
        }


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


def _points(polygon: Any) -> list[list[float]]:
    if not isinstance(polygon, (list, tuple)):
        return []
    output: list[list[float]] = []
    for point in polygon:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            try:
                output.append([float(point[0]), float(point[1])])
            except (TypeError, ValueError):
                return []
        else:
            return []
    return output


def _bounds(polygons: list[list[list[float]]]) -> dict[str, float] | None:
    xs = [point[0] for polygon in polygons for point in polygon]
    ys = [point[1] for polygon in polygons for point in polygon]
    if not xs or not ys:
        return None
    return {
        "min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys),
        "width": max(xs) - min(xs), "depth": max(ys) - min(ys),
    }


class StructuralArchitectureInputAdapterV1:
    """Project Design-05 architectural authority into a safe consumer input."""

    VERSION = VERSION

    # --------------------------------------------------
    # public entry
    # --------------------------------------------------

    def adapt(self, design_05_candidate: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(design_05_candidate, Mapping):
            raise StructuralArchitectureInputAdapterError(
                STATUS_FAILED, [{"code": "DESIGN_05_CANDIDATE_MUST_BE_MAPPING"}]
            )

        if design_05_candidate.get("contract") != DESIGN_05_CONTRACT:
            raise StructuralArchitectureInputAdapterError(
                STATUS_INSUFFICIENT_ARCHITECTURAL_INPUT,
                [{"code": "NOT_A_DESIGN_05_CANDIDATE",
                  "contract": design_05_candidate.get("contract")}],
            )

        if not verify_design_05_candidate(design_05_candidate):
            raise StructuralArchitectureInputAdapterError(
                STATUS_STALE_PARENT,
                [{"code": "DESIGN_05_CANDIDATE_UNVERIFIED_OR_STALE"}],
            )

        source = design_05_candidate.get("structural_architecture_input")
        if not isinstance(source, Mapping) or source.get("contract") != INPUT_CONTRACT:
            raise StructuralArchitectureInputAdapterError(
                STATUS_STRUCTURAL_INPUT_REQUIRED,
                [{"code": "STRUCTURAL_ARCHITECTURE_INPUT_MISSING",
                  "expected_contract": INPUT_CONTRACT}],
            )

        floors = self._floors(design_05_candidate, source)
        if not floors:
            raise StructuralArchitectureInputAdapterError(
                STATUS_INSUFFICIENT_ARCHITECTURAL_INPUT,
                [{"code": "DESIGN_05_FLOOR_ENVELOPES_MISSING_OR_INVALID"}],
            )

        return self._document(design_05_candidate, source, floors)

    # --------------------------------------------------
    # projection helpers
    # --------------------------------------------------

    @staticmethod
    def _floors(design_05_candidate: Mapping[str, Any], source: Mapping[str, Any]) -> list[dict[str, Any]]:
        envelopes = source.get("floor_envelopes", [])
        eligible = source.get("eligible_support_regions", [])
        voids = source.get("voids", [])
        protected = source.get("protected_zones", [])
        restrictions = source.get("opening_access_restrictions", [])
        gaps = source.get("unresolved_architectural_gaps", [])

        eligible_by_floor: dict[str, list[dict[str, Any]]] = {}
        for region in eligible if isinstance(eligible, list) else []:
            if isinstance(region, Mapping) and region.get("floor_id") is not None:
                eligible_by_floor.setdefault(str(region["floor_id"]), []).append(region)

        def refs(items: Any, key: str, floor_id: str) -> list[str]:
            output = []
            for item in items if isinstance(items, list) else []:
                if not isinstance(item, Mapping):
                    continue
                ids = item.get("floor_ids")
                if isinstance(ids, (list, tuple)):
                    floors_here = {str(value) for value in ids}
                elif item.get("floor_id") is not None:
                    floors_here = {str(item.get("floor_id"))}
                else:
                    floors_here = set()
                if floor_id in floors_here and item.get(key) is not None:
                    output.append(str(item[key]))
            return sorted(set(output))

        output: list[dict[str, Any]] = []
        for envelope in envelopes if isinstance(envelopes, list) else []:
            if not isinstance(envelope, Mapping):
                continue
            polygon = _points(envelope.get("polygon"))
            if not polygon:
                continue
            floor_id = str(envelope.get("floor_id"))
            regions = eligible_by_floor.get(floor_id, [])
            output.append({
                "floor_id": floor_id,
                "geometry_ref": envelope.get("geometry_ref"),
                "envelope_polygon": polygon,
                "elevation": deepcopy(envelope.get("elevation")),
                "eligible_region_refs": sorted(str(item.get("region_id")) for item in regions),
                "excluded_constraint_refs": sorted({
                    str(ref) for item in regions
                    for ref in (item.get("excluded_constraint_refs") or [])
                }),
                "void_refs": refs(voids, "void_id", floor_id),
                "protected_zone_refs": refs(protected, "zone_id", floor_id),
                "opening_access_restriction_refs": refs(restrictions, "constraint_id", floor_id),
                "unresolved_gap_codes": sorted({
                    str(item.get("code")) for item in (gaps if isinstance(gaps, list) else [])
                    if isinstance(item, Mapping)
                    and (item.get("floor_id") is None or str(item.get("floor_id")) == floor_id
                         or floor_id in {str(value) for value in (item.get("floor_ids") or [])})
                }),
            })
        return output

    def _document(
        self,
        design_05_candidate: Mapping[str, Any],
        source: Mapping[str, Any],
        floors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        readiness_status = source.get("readiness_status")
        gaps = deepcopy(source.get("unresolved_architectural_gaps", []))
        requirements = deepcopy(
            design_05_candidate.get("structural_input_requirements", [])
        )

        blocking = [
            item for item in gaps if isinstance(item, Mapping)
            and item.get("classification") == "ARCHITECTURE_BLOCKING_GAP"
        ]
        # The adapter reports INPUT COMPLETENESS only.  Architectural conflicts
        # (e.g. BLOCKED_PROTECTED_ZONE) are carried through untouched so the
        # candidate analysis can classify them; they are never resolved here.
        if blocking or gaps or readiness_status != "READY_FOR_STRUCTURAL_SYNTHESIS":
            status = STATUS_READY_WITH_GAPS
        else:
            status = STATUS_READY

        all_polygons = [floor["envelope_polygon"] for floor in floors]
        bounds = _bounds(all_polygons)

        projection = {
            "architecture_first": True,
            "read_only": True,
            "building": {
                "width": None if bounds is None else bounds["width"],
                "depth": None if bounds is None else bounds["depth"],
                "origin_x": None if bounds is None else bounds["min_x"],
                "origin_y": None if bounds is None else bounds["min_y"],
                "dimension_authority": "ARCHITECTURAL_ENVELOPE_BOUNDS_NO_ROUNDING",
                "grid_rounded": False,
            },
            "architectural_geometry": {
                "floor_geometry": [
                    {
                        "floor_id": floor["floor_id"],
                        "geometry_id": floor["geometry_ref"],
                        "polygon": deepcopy(floor["envelope_polygon"]),
                        "elevation": floor["elevation"],
                    }
                    for floor in floors
                ],
            },
            "coordinate_frame": {},
            "parcel_placement": {},
            "structural_architecture_input": deepcopy(dict(source)),
        }

        vertical_levels = []
        for floor in floors:
            elevation = floor["elevation"]
            vertical_levels.append({
                "name": floor["floor_id"],
                "bottom": elevation,
                "top": None,
                "height": None,
                "elevation_evidence": "ARCHITECTURAL_EVIDENCE_ONLY" if elevation is not None
                else "UNRESOLVED_NOT_DEFAULTED",
            })

        document: dict[str, Any] = {
            "contract": CONTRACT,
            "version": VERSION,
            "status": status,
            "authority": "DESIGN_05_ARCHITECTURE_OWNED_READ_ONLY",
            "architecture_first": True,
            "read_only": True,
            "source": {
                "contract": design_05_candidate.get("contract"),
                "candidate_id": design_05_candidate.get("candidate_id"),
                "candidate_version": design_05_candidate.get("candidate_version"),
                "candidate_hash": design_05_candidate.get("candidate_hash"),
                "parent_candidate_id": design_05_candidate.get("parent_candidate_id"),
                "parent_candidate_hash": design_05_candidate.get("parent_candidate_hash"),
                "readiness_status": readiness_status,
            },
            "floors": floors,
            "roof_envelopes": deepcopy(source.get("roof_envelopes", [])),
            "exclusions": deepcopy(design_05_candidate.get("exclusion_zones", [])),
            "eligible_support_regions": deepcopy(source.get("eligible_support_regions", [])),
            "opening_access_restrictions": deepcopy(source.get("opening_access_restrictions", [])),
            "external_space_constraints": deepcopy(
                design_05_candidate.get("external_space_constraints", [])
            ),
            "unresolved_architectural_gaps": gaps,
            "structural_input_requirements": requirements,
            # structural design decisions remain explicitly unowned by architecture
            "spacing_authority": None,
            "equal_bay_authority": None,
            "column_count_authority": None,
            "beam_layout_authority": None,
            "engine_input_projection": projection,
            "vertical_section_projection": {"levels": vertical_levels},
            "adapter_guard": {
                "grid_spacing_chosen": False,
                "equal_bay_chosen": False,
                "column_count_chosen": False,
                "support_points_invented": False,
                "architecture_resized": False,
                "envelope_rounded_to_grid": False,
                "missing_evidence_defaulted": False,
                "four_meter_assumption_applied": False,
                "source_mutated": False,
                "structural_elements_generated": False,
                "legacy_width_depth_only_inference": False,
            },
            "provenance": {
                "adapter": "StructuralArchitectureInputAdapterV1",
                "adapter_version": VERSION,
                "source_contract": DESIGN_05_CONTRACT,
                "input_contract": INPUT_CONTRACT,
                "projection_policy": "LOSSLESS_ARCHITECTURE_AUTHORITY_NO_STRUCTURAL_DECISION",
            },
        }
        document["adapter_hash"] = self.hash(document)
        return document

    # --------------------------------------------------
    # deterministic hash
    # --------------------------------------------------

    @staticmethod
    def hash(document: Mapping[str, Any]) -> str:
        payload = {
            key: value for key, value in document.items()
            if key not in ("adapter_hash", "provenance")
        }
        return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


__all__ = [
    "CONTRACT", "VERSION", "STATUSES",
    "STATUS_READY", "STATUS_READY_WITH_GAPS", "STATUS_INSUFFICIENT_ARCHITECTURAL_INPUT",
    "STATUS_STRUCTURAL_INPUT_REQUIRED", "STATUS_STALE_PARENT", "STATUS_FAILED",
    "StructuralArchitectureInputAdapterError", "StructuralArchitectureInputAdapterV1",
]
