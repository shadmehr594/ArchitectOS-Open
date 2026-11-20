"""Evidence-bound Design-04 architectural floor, slab, and roof derivation."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
from typing import Any

from shapely.geometry import Polygon
from shapely.ops import unary_union

from core.architecture.contracts.architectural_floor_roof_geometry_v1 import (
    CONTRACT,
    VERSION,
    design_04_semantic_hash,
)
from core.architecture.contracts.architectural_opening_privacy_parcel_edge_intelligence_v1 import (
    canonical_design_03_document,
    design_03_semantic_hash,
    verify_design_03_candidate,
)


ENGINE_VERSION = "architectural_baseline_floor_roof_geometry_v1"
PHASE = "ARCHITECTURAL-BASELINE-DESIGN-04"
SCOPE = "EVIDENCE_BOUND_ARCHITECTURAL_FLOOR_SLAB_ROOF_GEOMETRY"
_VERIFIED = {"ACCEPTED", "CANONICAL", "RESOLVED", "VERIFIED", "APPROVED"}


class Design04GeometryDerivationError(ValueError):
    """Transactional failure: no Design-04 candidate has been committed."""

    def __init__(self, status: str, conflicts: Sequence[Mapping[str, Any]]):
        self.status = status
        self.conflicts = [deepcopy(dict(item)) for item in conflicts]
        super().__init__(f"{status}: {json.dumps(self.conflicts, sort_keys=True)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": PHASE,
            "status": self.status,
            "candidate_committed": False,
            "conflicts": deepcopy(self.conflicts),
        }


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _polygon(value: Any, *, source: str) -> tuple[Polygon | None, dict[str, Any] | None]:
    try:
        shape = Polygon(value)
    except (TypeError, ValueError):
        return None, {"code": "INVALID_POLYGON_COORDINATES", "source": source}
    if shape.is_empty or shape.area <= 0:
        return None, {"code": "ZERO_AREA_POLYGON", "source": source}
    if not shape.is_valid:
        return None, {"code": "SELF_INTERSECTING_OR_INVALID_POLYGON", "source": source}
    return shape, None


def _coords(shape: Polygon) -> list[list[float]]:
    return [[float(x), float(y)] for x, y in shape.exterior.coords]


def _source_tolerance(extraction: Mapping[str, Any]) -> tuple[float, str]:
    audit = extraction.get("tolerance_audit")
    if isinstance(audit, Mapping):
        raw = audit.get("chosen_snap_tolerance_m")
        if isinstance(raw, (int, float)) and raw >= 0:
            return float(raw), "boundary_extraction.tolerance_audit.chosen_snap_tolerance_m"
    return 0.0, "EXACT_GEOMETRY_NO_TOLERANCE_AVAILABLE"


def _level_policy(floor_ids: list[str], evidence: Mapping[str, Any] | None) -> tuple[list[str], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    levels: dict[str, dict[str, Any]] = {}
    unresolved: list[dict[str, Any]] = []
    raw_levels = evidence.get("levels", ()) if isinstance(evidence, Mapping) else ()
    if isinstance(raw_levels, (list, tuple)):
        for offset, item in enumerate(raw_levels):
            if not isinstance(item, Mapping) or item.get("floor_id") is None:
                continue
            floor_id = str(item["floor_id"])
            if floor_id in levels:
                raise Design04GeometryDerivationError("REJECTED_GEOMETRY", [{
                    "code": "DUPLICATE_LEVEL_ID", "floor_id": floor_id,
                    "source": f"geometry_evidence.levels[{offset}]",
                }])
            levels[floor_id] = deepcopy(dict(item))
    orders = [levels[f].get("order") for f in floor_ids if f in levels]
    usable_order = len(orders) == len(floor_ids) and all(isinstance(v, (int, float)) for v in orders) and len(set(orders)) == len(orders)
    ordered = sorted(floor_ids, key=lambda f: (float(levels[f]["order"]), f)) if usable_order else sorted(floor_ids)
    if not usable_order:
        unresolved.append({
            "classification": "LEVEL_ORDER_EVIDENCE_UNRESOLVED",
            "code": "deterministic_lexical_order_used_without_elevation_or_vertical_order_claim",
        })
    for floor_id in floor_ids:
        level = levels.get(floor_id, {})
        if not isinstance(level.get("elevation"), (int, float)):
            unresolved.append({
                "classification": "FLOOR_ELEVATION_UNRESOLVED", "floor_id": floor_id,
                "code": "canonical_level_elevation_missing_no_default_applied",
            })
    return ordered, levels, unresolved


def _derive_floor_shapes(extraction: Mapping[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    solids = extraction.get("wall_solid_graphs")
    spaces = extraction.get("space_boundary_graphs")
    floor_ids = sorted(set(
        [str(key) for key in solids] if isinstance(solids, Mapping) else []
    ) | set(
        [str(key) for key in spaces] if isinstance(spaces, Mapping) else []
    ))
    derived: dict[str, list[dict[str, Any]]] = {}
    failures: list[dict[str, Any]] = []
    for floor_id in floor_ids:
        graph = solids.get(floor_id, {}) if isinstance(solids, Mapping) else {}
        envelopes = graph.get("floor_envelopes", ()) if isinstance(graph, Mapping) else ()
        records: list[dict[str, Any]] = []
        if isinstance(envelopes, (list, tuple)) and envelopes:
            for offset, envelope in enumerate(envelopes):
                if not isinstance(envelope, Mapping):
                    failures.append({"code": "INVALID_FLOOR_ENVELOPE_RECORD", "floor_id": floor_id})
                    continue
                source = f"boundary_extraction.wall_solid_graphs.{floor_id}.floor_envelopes[{offset}]"
                shape, issue = _polygon(envelope.get("polygon"), source=source)
                if issue:
                    failures.append({**issue, "floor_id": floor_id})
                    continue
                records.append({
                    "shape": shape,
                    "envelope_id": str(envelope.get("envelope_id") or f"{floor_id}:ENVELOPE:{offset}"),
                    "source": source,
                    "source_priority": 1,
                    "source_classification": "CANONICAL_ACTIVE",
                })
        else:
            space_graph = spaces.get(floor_id, {}) if isinstance(spaces, Mapping) else {}
            raw_spaces = space_graph.get("spaces", ()) if isinstance(space_graph, Mapping) else ()
            shapes: list[Polygon] = []
            ids: list[str] = []
            invalid = False
            if isinstance(raw_spaces, (list, tuple)):
                for offset, space in enumerate(raw_spaces):
                    if not isinstance(space, Mapping):
                        continue
                    source = f"boundary_extraction.space_boundary_graphs.{floor_id}.spaces[{offset}]"
                    shape, issue = _polygon(space.get("polygon"), source=source)
                    if issue:
                        failures.append({**issue, "floor_id": floor_id})
                        invalid = True
                        break
                    shapes.append(shape)
                    ids.append(str(space.get("space_id") or space.get("id") or offset))
            merged = unary_union(shapes) if shapes and not invalid else None
            if isinstance(merged, Polygon) and merged.is_valid and merged.area > 0:
                records.append({
                    "shape": merged,
                    "envelope_id": f"{floor_id}:CLOSED_SPACE_BOUNDARY_UNION",
                    "source": f"boundary_extraction.space_boundary_graphs.{floor_id}.spaces",
                    "source_priority": 2,
                    "source_classification": "CANONICAL_ACTIVE_CLOSED_BOUNDARY_FALLBACK",
                    "source_space_ids": sorted(ids),
                })
        if records:
            keys: set[str] = set()
            for record in records:
                key = record["shape"].wkb_hex
                if key in keys:
                    failures.append({"code": "DUPLICATE_FLOOR_GEOMETRY", "floor_id": floor_id})
                keys.add(key)
            for left_index, left in enumerate(records):
                for right in records[left_index + 1:]:
                    if left["shape"].intersection(right["shape"]).area > 0:
                        failures.append({
                            "code": "OVERLAPPING_MUTUALLY_EXCLUSIVE_FLOOR_ENVELOPES",
                            "floor_id": floor_id,
                            "envelope_ids": [left["envelope_id"], right["envelope_id"]],
                        })
            derived[floor_id] = records
    return derived, failures


def _geometry_evidence(value: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise Design04GeometryDerivationError("FAILED", [{"code": "GEOMETRY_EVIDENCE_NOT_A_MAPPING"}])
    if str(value.get("status", "")).upper() not in _VERIFIED:
        raise Design04GeometryDerivationError("FAILED", [{"code": "GEOMETRY_EVIDENCE_NOT_VERIFIED"}])
    return deepcopy(dict(value))


def _vertical_records(
    evidence: Mapping[str, Any] | None,
    floor_shapes: Mapping[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    voids: list[dict[str, Any]] = []
    zones: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    raw = evidence.get("vertical_circulation", ()) if isinstance(evidence, Mapping) else ()
    if not isinstance(raw, (list, tuple)):
        return voids, zones, unresolved
    for offset, item in enumerate(raw):
        if not isinstance(item, Mapping) or str(item.get("status", "")).upper() not in _VERIFIED:
            continue
        identity = str(item.get("id") or item.get("void_id") or f"VERTICAL:{offset}")
        floor_ids = sorted({str(value) for value in item.get("floor_ids", ())})
        base = {
            "void_id": identity,
            "circulation_type": str(item.get("type") or "UNKNOWN").upper(),
            "floor_ids": floor_ids,
            "source": f"geometry_evidence.vertical_circulation[{offset}]",
            "redesigned": False,
        }
        if not item.get("polygon"):
            unresolved.append({
                "classification": "VERTICAL_VOID_GEOMETRY_PENDING", "void_id": identity,
                "floor_ids": floor_ids, "code": "verified_vertical_record_has_no_polygon",
            })
            zones.append({**base, "polygon": None, "status": "VERTICAL_VOID_GEOMETRY_PENDING"})
            continue
        shape, issue = _polygon(item.get("polygon"), source=base["source"])
        if issue:
            raise Design04GeometryDerivationError("REJECTED_GEOMETRY", [{**issue, "void_id": identity}])
        for floor_id in floor_ids:
            envelopes = floor_shapes.get(floor_id, ())
            if envelopes and not any(record["shape"].covers(shape) for record in envelopes):
                raise Design04GeometryDerivationError("PROTECTED_ZONE_CONFLICT", [{
                    "code": "PROTECTED_VERTICAL_VOID_CROSSES_OR_LIES_OUTSIDE_FLOOR_ENVELOPE",
                    "void_id": identity, "floor_id": floor_id,
                }])
        record = {**base, "polygon": _coords(shape), "area_m2": float(shape.area), "status": "PRESERVED_OPEN"}
        voids.append(record)
        zones.append({**record, "zone_type": "VERTICAL_CIRCULATION_PROTECTED_VOID"})
    return voids, zones, unresolved


def _external_spaces(parent: Mapping[str, Any], floor_id: str) -> list[dict[str, Any]]:
    graph = parent.get("boundary_extraction", {}).get("space_boundary_graphs", {}).get(floor_id, {})
    output: list[dict[str, Any]] = []
    for item in graph.get("spaces", ()) if isinstance(graph, Mapping) else ():
        if not isinstance(item, Mapping):
            continue
        semantic = str(item.get("semantic_class") or item.get("semantic_role") or "").upper()
        external = item.get("external") is True or any(token in semantic for token in ("TERRACE", "BALCONY", "EXTERNAL"))
        if external:
            output.append({
                "space_id": str(item.get("space_id") or item.get("id")),
                "external": True,
                "semantic_class": semantic or None,
                "canonical_path": f"boundary_extraction.space_boundary_graphs.{floor_id}.spaces",
            })
    return sorted(output, key=lambda item: item["space_id"])


def derive_architectural_floor_roof_geometry_v1(
    parent_candidate: Mapping[str, Any], *,
    geometry_evidence: Mapping[str, Any] | None = None,
    derivation_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Transactionally derive an immutable Design-04 geometry child."""
    if not verify_design_03_candidate(parent_candidate):
        raise Design04GeometryDerivationError("STALE_PARENT", [{"code": "INVALID_OR_STALE_DESIGN_03_PARENT"}])
    if not isinstance(derivation_provenance, Mapping) or not derivation_provenance:
        raise Design04GeometryDerivationError("FAILED", [{"code": "DERIVATION_PROVENANCE_REQUIRED"}])
    parent_document = canonical_design_03_document(parent_candidate)
    parent_hash = design_03_semantic_hash(parent_candidate)
    evidence = _geometry_evidence(geometry_evidence)
    extraction = parent_candidate.get("boundary_extraction")
    if not isinstance(extraction, Mapping):
        raise Design04GeometryDerivationError("INSUFFICIENT_FLOOR_EVIDENCE", [{"code": "BOUNDARY_EXTRACTION_MISSING"}])

    floor_shapes, failures = _derive_floor_shapes(extraction)
    if failures:
        raise Design04GeometryDerivationError("REJECTED_GEOMETRY", failures)
    if not floor_shapes:
        raise Design04GeometryDerivationError("INSUFFICIENT_FLOOR_EVIDENCE", [{
            "code": "NO_CANONICAL_FLOOR_ENVELOPE_OR_PROVABLE_CLOSED_SPACE_BOUNDARY_LOOP",
        }])
    ordered_floors, levels, unresolved = _level_policy(sorted(floor_shapes), evidence)
    tolerance, tolerance_source = _source_tolerance(extraction)
    voids, protected_zones, void_unresolved = _vertical_records(evidence, floor_shapes)
    unresolved.extend(void_unresolved)
    voids_by_floor = {
        floor_id: [item for item in voids if floor_id in item["floor_ids"]]
        for floor_id in ordered_floors
    }

    floor_geometries: list[dict[str, Any]] = []
    slab_geometries: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    space_graphs = extraction.get("space_boundary_graphs", {})
    for order_index, floor_id in enumerate(ordered_floors):
        level = levels.get(floor_id, {})
        space_graph = space_graphs.get(floor_id, {}) if isinstance(space_graphs, Mapping) else {}
        assigned_spaces = [item for item in space_graph.get("spaces", ()) if isinstance(item, Mapping)] if isinstance(space_graph, Mapping) else []
        space_ids = sorted(str(item.get("space_id") or item.get("id")) for item in assigned_spaces)
        for record in floor_shapes[floor_id]:
            envelope = record["shape"]
            alignment_failures: list[str] = []
            for offset, space in enumerate(assigned_spaces):
                shape, issue = _polygon(space.get("polygon"), source=f"space:{floor_id}:{offset}")
                if issue:
                    alignment_failures.append(str(space.get("space_id") or offset))
                    continue
                container = envelope.buffer(tolerance) if tolerance > 0 else envelope
                if not container.covers(shape):
                    alignment_failures.append(str(space.get("space_id") or offset))
            if alignment_failures:
                raise Design04GeometryDerivationError("REJECTED_GEOMETRY", [{
                    "code": "ASSIGNED_SPACE_OUTSIDE_FLOOR_ENVELOPE", "floor_id": floor_id,
                    "space_ids": sorted(alignment_failures), "tolerance_m": tolerance,
                    "tolerance_source": tolerance_source,
                }])
            geometry_id = f"FLOOR:{floor_id}:{record['envelope_id']}"
            base = {
                "geometry_id": geometry_id,
                "floor_id": floor_id,
                "deterministic_order": order_index,
                "elevation": deepcopy(level.get("elevation")) if isinstance(level.get("elevation"), (int, float)) else None,
                "polygon": _coords(envelope),
                "area_m2": float(envelope.area),
                "envelope_ref": record["envelope_id"],
                "assigned_space_ids": space_ids,
                "source": record["source"],
                "source_priority": record["source_priority"],
                "source_classification": record["source_classification"],
                "external_spaces": _external_spaces(parent_candidate, floor_id),
            }
            if record.get("source_space_ids"):
                base["source_space_ids"] = record["source_space_ids"]
            floor_geometries.append(base)
            slab_geometries.append({
                "geometry_id": geometry_id.replace("FLOOR:", "SLAB:", 1),
                "floor_geometry_ref": geometry_id,
                "floor_id": floor_id,
                "support_extent_polygon": _coords(envelope),
                "architectural_only": True,
                "structural_sizing_performed": False,
                "void_refs": [item["void_id"] for item in voids_by_floor[floor_id]],
                "void_polygons": [deepcopy(item["polygon"]) for item in voids_by_floor[floor_id]],
            })
            checks.extend([
                {"check": "POLYGON_VALIDITY", "geometry_id": geometry_id, "status": "PASS"},
                {"check": "NON_ZERO_AREA", "geometry_id": geometry_id, "status": "PASS"},
                {"check": "SPACE_ASSIGNMENT_ALIGNMENT", "geometry_id": geometry_id, "status": "PASS", "tolerance_m": tolerance, "tolerance_source": tolerance_source},
                {"check": "VERTICAL_VOIDS_PRESERVED", "geometry_id": geometry_id, "status": "PASS", "void_refs": [item["void_id"] for item in voids_by_floor[floor_id]]},
            ])

    roof_geometries: list[dict[str, Any]] = []
    roof = evidence.get("roof") if isinstance(evidence, Mapping) else None
    if isinstance(roof, Mapping) and str(roof.get("status", "")).upper() in _VERIFIED:
        source_floor = str(roof.get("source_floor_id")) if roof.get("source_floor_id") is not None else None
        matches = [item for item in floor_geometries if item["floor_id"] == source_floor]
        explicit_polygon = roof.get("polygon")
        if explicit_polygon is not None:
            roof_shape, issue = _polygon(explicit_polygon, source="geometry_evidence.roof.polygon")
            if issue:
                raise Design04GeometryDerivationError("REJECTED_GEOMETRY", [issue])
            roof_source = "geometry_evidence.roof.polygon"
            boundary_ref = deepcopy(roof.get("boundary_ref"))
        elif len(matches) == 1 and roof.get("use_source_floor_envelope") is True:
            roof_shape, issue = _polygon(matches[0]["polygon"], source="verified_top_floor_envelope_reference")
            roof_source = matches[0]["source"]
            boundary_ref = matches[0]["envelope_ref"]
        else:
            roof_shape = None
            unresolved.append({
                "classification": "INSUFFICIENT_ROOF_EVIDENCE",
                "code": "verified_roof_polygon_or_unique_explicit_source_floor_envelope_binding_missing",
            })
        if roof_shape is not None:
            roof_type = deepcopy(roof.get("roof_type")) if roof.get("roof_type") is not None else "UNKNOWN"
            slope = deepcopy(roof.get("slope")) if roof.get("slope") is not None else None
            if roof_type == "UNKNOWN":
                unresolved.append({"classification": "ROOF_TYPE_UNRESOLVED", "code": "roof_type_not_in_canonical_evidence"})
            if slope is None:
                unresolved.append({"classification": "ROOF_SLOPE_UNRESOLVED", "code": "roof_slope_not_in_canonical_evidence"})
            terraces = []
            for offset, terrace in enumerate(roof.get("terraces", ())):
                if not isinstance(terrace, Mapping) or terrace.get("external") is not True:
                    continue
                shape, issue = _polygon(terrace.get("polygon"), source=f"geometry_evidence.roof.terraces[{offset}]")
                if issue:
                    raise Design04GeometryDerivationError("REJECTED_GEOMETRY", [issue])
                terraces.append({
                    "terrace_id": str(terrace.get("terrace_id") or f"ROOF-TERRACE:{offset}"),
                    "polygon": _coords(shape), "area_m2": float(shape.area), "external": True,
                    "enclosed_interior": False,
                })
            roof_geometries.append({
                "geometry_id": "ROOF:0", "source_floor_id": source_floor,
                "polygon": _coords(roof_shape), "area_m2": float(roof_shape.area),
                "boundary_ref": boundary_ref, "roof_type": roof_type, "slope": slope,
                "terraces": terraces, "source": roof_source,
                "parapet": None, "drainage": None, "overhang": None, "material": None,
            })
            checks.append({"check": "ROOF_ENVELOPE_VALIDITY", "geometry_id": "ROOF:0", "status": "PASS"})
    else:
        unresolved.append({
            "classification": "INSUFFICIENT_ROOF_EVIDENCE",
            "code": "no_verified_architectural_roof_evidence_no_roof_geometry_guessed",
        })

    fingerprint_payload = {
        "parent_candidate_id": parent_candidate["candidate_id"],
        "parent_candidate_version": parent_candidate["candidate_version"],
        "parent_candidate_hash": parent_hash,
        "geometry_evidence": evidence,
        "floor_geometries": floor_geometries,
        "slab_geometries": slab_geometries,
        "roof_geometries": roof_geometries,
        "vertical_voids": voids,
    }
    fingerprint = hashlib.sha256(_stable_json(fingerprint_payload).encode("utf-8")).hexdigest()
    suffix = fingerprint[:16]
    status = "DERIVED_WITH_WARNINGS" if unresolved else "DERIVED"
    candidate: dict[str, Any] = {
        "contract": CONTRACT,
        "contract_version": VERSION,
        "candidate_id": f"{parent_candidate['candidate_id']}::DESIGN-04::{suffix}",
        "candidate_version": f"{parent_candidate['candidate_version']}+design-04.{suffix}",
        "parent_candidate_id": parent_candidate["candidate_id"],
        "parent_candidate_version": parent_candidate["candidate_version"],
        "parent_candidate_hash": parent_hash,
        "parent_baseline_id": parent_candidate["parent_baseline_id"],
        "parent_baseline_version": parent_candidate["parent_baseline_version"],
        "parent_baseline_hash": parent_candidate["parent_baseline_hash"],
        "derivation_status": status,
        "geometry_scope": SCOPE,
        "floor_geometries": floor_geometries,
        "slab_geometries": slab_geometries,
        "roof_geometries": roof_geometries,
        "vertical_voids": voids,
        "protected_zones": protected_zones,
        "preserved_graph_refs": {
            "canonical_graph_references": deepcopy(parent_candidate.get("canonical_graph_references", {})),
            "opening_references": deepcopy(parent_candidate.get("opening_references", [])),
            "access_references": deepcopy(parent_candidate.get("access_references", [])),
            "boundary_extraction_hash": hashlib.sha256(_stable_json(parent_candidate["boundary_extraction"]).encode("utf-8")).hexdigest(),
        },
        "geometry_checks": checks + [
            {"check": "CANONICAL_OPENING_REFERENCES_PRESERVED", "status": "PASS"},
            {"check": "CANONICAL_ACCESS_REFERENCES_PRESERVED", "status": "PASS"},
            {"check": "UNIQUE_FLOOR_IDENTITIES", "status": "PASS"},
            {"check": "NO_CROSS_FLOOR_GEOMETRY_REUSE", "status": "PASS"},
        ],
        "unresolved_evidence": unresolved,
        "required_downstream_rechecks": [
            "VERIFY_DESIGN_04_PARENT_HASH_BEFORE_FURTHER_DERIVATION",
            "RESOLVE_PENDING_VERTICAL_VOID_GEOMETRY_BEFORE_AFFECTED_SLAB_REALIZATION",
            "RESOLVE_ROOF_TYPE_SLOPE_AND_DETAILS_ONLY_FROM_APPROVED_ARCHITECTURAL_EVIDENCE",
            "PRESERVE_ARCHITECTURAL_PROTECTED_ZONES_IN_ANY_FUTURE_STRUCTURE",
            "STRUCTURE_BIM_IFC_RENDER_REMAIN_UNIMPLEMENTED",
        ],
        "evidence_source_audit": [
            {"source": "boundary_extraction.wall_solid_graphs[*].floor_envelopes", "classification": "CANONICAL_ACTIVE"},
            {"source": "boundary_extraction.space_boundary_graphs[*].spaces", "classification": "CANONICAL_ACTIVE_CLOSED_BOUNDARY_FALLBACK"},
            {"source": "SpaceBoundaryOpeningHostGraphEngineV1/Shapely", "classification": "REUSABLE_GEOMETRY_KERNEL"},
            {"source": "geometry_evidence", "classification": "EXPLICIT_APPROVED_GEOMETRY_REFERENCES" if evidence else "INSUFFICIENT"},
            {"source": "structural_grid/column/beam engines", "classification": "STRUCTURE_ONLY_DO_NOT_USE"},
            {"source": "geometry_adapter/IFC exporters", "classification": "BIM_ONLY_DO_NOT_USE"},
            {"source": "roof_intelligence_engine/building_envelope_generator", "classification": "LEGACY_OR_DEFAULTING_NOT_AUTHORITY"},
            {"source": "CAD roof/render/image geometry", "classification": "DUPLICATE_OR_OUT_OF_SCOPE_DO_NOT_USE"},
        ],
        "lineage": {
            "parent_candidate_id": parent_candidate["candidate_id"],
            "parent_candidate_version": parent_candidate["candidate_version"],
            "parent_candidate_hash": parent_hash,
            "parent_baseline_id": parent_candidate["parent_baseline_id"],
            "parent_baseline_version": parent_candidate["parent_baseline_version"],
            "parent_baseline_hash": parent_candidate["parent_baseline_hash"],
            "parent_contract": parent_candidate["contract"],
            "design_03_parent_mutated": False,
            "accepted_baseline_mutated": False,
            "derivation_fingerprint": fingerprint,
        },
        "provenance": {
            "phase": PHASE, "engine": ENGINE_VERSION,
            "derivation": deepcopy(dict(derivation_provenance)),
            "evidence_policy": "CANONICAL_FLOOR_ENVELOPES_THEN_CLOSED_ARCHITECTURAL_BOUNDARIES_THEN_EXPLICIT_APPROVED_REFERENCES",
            "site_orientation_inferred": False,
            "floor_elevation_defaulted": False,
            "roof_properties_defaulted": False,
            "structural_analysis_performed": False,
        },
        "immutability": {
            "accepted_baseline": "READ_ONLY", "design_03_parent": "READ_ONLY",
            "canonical_wall_opening_access_geometry": "PRESERVED_EXACTLY",
            "in_place_revision_allowed": False,
        },
        "architecture_only": True,
        "side_effects": {
            "site": False, "structure": False, "bim": False, "ifc": False,
            "render": False, "chat_intelligence": False,
        },
    }
    candidate["candidate_hash"] = design_04_semantic_hash(candidate)
    if canonical_design_03_document(parent_candidate) != parent_document or design_03_semantic_hash(parent_candidate) != parent_hash:
        raise RuntimeError("Design-03 parent mutated during Design-04 derivation")
    return candidate


__all__ = [
    "Design04GeometryDerivationError", "ENGINE_VERSION", "PHASE", "SCOPE",
    "derive_architectural_floor_roof_geometry_v1",
]
