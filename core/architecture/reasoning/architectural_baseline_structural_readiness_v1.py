"""Evidence-bound Design-05 architectural protection and readiness analysis."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
from typing import Any

from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.ops import unary_union

from core.architecture.contracts.architectural_floor_roof_geometry_v1 import (
    canonical_design_04_document,
    design_04_semantic_hash,
    verify_design_04_candidate,
)
from core.architecture.contracts.architectural_structural_readiness_v1 import (
    CONTRACT,
    INPUT_CONTRACT,
    VERSION,
    design_05_semantic_hash,
)


ENGINE_VERSION = "architectural_baseline_structural_readiness_v1"
PHASE = "ARCHITECTURAL-BASELINE-DESIGN-05"
SCOPE = "ARCHITECTURE_OWNED_STRUCTURAL_PROTECTION_AND_READINESS_NO_SYNTHESIS"
_VERIFIED = {"ACCEPTED", "APPROVED", "CANONICAL", "RESOLVED", "VERIFIED"}
_GEOMETRIC_COLLECTIONS = (
    "protected_zones", "opening_clearances", "access_circulation_zones"
)


class Design05ReadinessAnalysisError(ValueError):
    """Transactional failure: no Design-05 candidate has been committed."""

    def __init__(self, status: str, conflicts: Sequence[Mapping[str, Any]]):
        self.status = status
        self.conflicts = [deepcopy(dict(item)) for item in conflicts]
        super().__init__(f"{status}: {json.dumps(self.conflicts, sort_keys=True)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": PHASE, "status": self.status, "candidate_committed": False,
            "conflicts": deepcopy(self.conflicts),
        }


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _polygon(value: Any, *, source: str) -> Polygon:
    try:
        shape = Polygon(value)
    except (TypeError, ValueError) as error:
        raise Design05ReadinessAnalysisError("FAILED", [{
            "code": "INVALID_POLYGON_COORDINATES", "source": source,
        }]) from error
    if shape.is_empty or shape.area <= 0 or not shape.is_valid:
        raise Design05ReadinessAnalysisError("FAILED", [{
            "code": "INVALID_OR_ZERO_AREA_POLYGON", "source": source,
        }])
    return shape


def _coords(shape: Polygon) -> list[list[float]]:
    return [[float(x), float(y)] for x, y in shape.exterior.coords]


def _surface(shape: Polygon) -> dict[str, Any]:
    return {
        "exterior": _coords(shape),
        "holes": [
            [[float(x), float(y)] for x, y in ring.coords]
            for ring in shape.interiors
        ],
    }


def _polygon_parts(shape: Any) -> list[Polygon]:
    if shape.is_empty:
        return []
    if isinstance(shape, Polygon):
        return [shape]
    if isinstance(shape, MultiPolygon):
        return list(shape.geoms)
    if isinstance(shape, GeometryCollection):
        return [item for item in shape.geoms if isinstance(item, Polygon) and item.area > 0]
    return []


def _readiness_evidence(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise Design05ReadinessAnalysisError("FAILED", [{
            "code": "READINESS_EVIDENCE_NOT_A_MAPPING",
        }])
    if str(value.get("status", "")).upper() not in _VERIFIED:
        raise Design05ReadinessAnalysisError("FAILED", [{
            "code": "READINESS_EVIDENCE_NOT_VERIFIED",
        }])
    evidence = deepcopy(dict(value))
    for key in _GEOMETRIC_COLLECTIONS:
        records = evidence.get(key, [])
        if not isinstance(records, (list, tuple)):
            raise Design05ReadinessAnalysisError("FAILED", [{
                "code": "INVALID_EVIDENCE_COLLECTION", "collection": key,
            }])
    return evidence


def _authority_refs(parent: Mapping[str, Any]) -> list[dict[str, Any]]:
    refs = [
        {"authority": "FLOOR_SLAB_ARCHITECTURAL_EXTENTS", "canonical_path": "floor_geometries|slab_geometries", "policy": "STRUCTURE_READ_ONLY"},
        {"authority": "ROOF_ARCHITECTURAL_EXTENTS", "canonical_path": "roof_geometries", "policy": "STRUCTURE_READ_ONLY"},
        {"authority": "VERTICAL_CIRCULATION_VOIDS", "canonical_path": "vertical_voids", "policy": "MUST_REMAIN_OPEN"},
        {"authority": "ARCHITECTURAL_PROTECTED_ZONES", "canonical_path": "protected_zones", "policy": "NO_STRUCTURAL_OCCUPATION"},
        {"authority": "WALL_AND_BOUNDARY_GEOMETRY", "canonical_path": "preserved_graph_refs.canonical_graph_references", "policy": "REFERENCE_ONLY_NO_RELOCATION"},
        {"authority": "OPENINGS", "canonical_path": "preserved_graph_refs.opening_references", "policy": "MUST_NOT_BLOCK"},
        {"authority": "ACCESS_CONNECTIONS", "canonical_path": "preserved_graph_refs.access_references", "policy": "MUST_NOT_BLOCK"},
        {"authority": "EXTERNAL_SPACE_SEMANTICS", "canonical_path": "floor_geometries[*].external_spaces|roof_geometries[*].terraces", "policy": "NO_STRUCTURE_DRIVEN_ENCLOSURE"},
    ]
    return [item for item in refs if parent.get(item["canonical_path"].split("|")[0].split(".")[0]) is not None]


def _parent_zones(parent: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    protected: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for offset, item in enumerate(parent.get("protected_zones", [])):
        if not isinstance(item, Mapping):
            continue
        record = deepcopy(dict(item))
        record["zone_id"] = str(item.get("zone_id") or item.get("void_id") or f"DESIGN04-ZONE:{offset}")
        record["zone_type"] = str(item.get("zone_type") or item.get("circulation_type") or "PROTECTED_ARCHITECTURAL_ZONE").upper()
        record["authority"] = "DESIGN_04_ARCHITECTURAL_PROTECTED_ZONE"
        record["structural_policy"] = "EXCLUDED_FROM_SUPPORT_PLACEMENT"
        if item.get("polygon") is None:
            record["geometry_status"] = "SEMANTIC_ONLY_NO_COORDINATES_GUESSED"
            unresolved.append({
                "classification": "ARCHITECTURE_BLOCKING_GAP",
                "code": "PROTECTED_ZONE_GEOMETRY_UNRESOLVED",
                "zone_id": record["zone_id"], "blocks_full_structural_synthesis": True,
            })
        else:
            shape = _polygon(item.get("polygon"), source=f"protected_zones[{offset}]")
            record["polygon"] = _coords(shape)
            record["geometry_status"] = "EXPLICIT"
        protected.append(record)
    return protected, unresolved


def _explicit_constraints(
    evidence: Mapping[str, Any] | None,
    key: str,
    *, kind: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    constraints: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    raw = evidence.get(key, []) if evidence else []
    for offset, item in enumerate(raw):
        if not isinstance(item, Mapping) or str(item.get("status", "")).upper() not in _VERIFIED:
            continue
        identity = str(item.get("constraint_id") or item.get("zone_id") or f"{kind}:{offset}")
        record = deepcopy(dict(item))
        record.update({
            "constraint_id": identity, "constraint_type": kind,
            "authority": "EXPLICIT_VERIFIED_ARCHITECTURAL_READINESS_EVIDENCE",
            "structural_policy": "EXCLUDED_FROM_SUPPORT_PLACEMENT",
        })
        if item.get("polygon") is None:
            record["polygon"] = None
            record["geometry_status"] = "SEMANTIC_ONLY_NO_COORDINATES_GUESSED"
            unresolved.append({
                "classification": "ARCHITECTURE_BLOCKING_GAP",
                "code": f"{kind}_GEOMETRY_UNRESOLVED", "constraint_id": identity,
                "blocks_full_structural_synthesis": True,
            })
        else:
            shape = _polygon(item.get("polygon"), source=f"readiness_evidence.{key}[{offset}]")
            record["polygon"] = _coords(shape)
            record["area_m2"] = float(shape.area)
            record["geometry_status"] = "EXPLICIT"
            if not _zone_floor_ids(record):
                unresolved.append({
                    "classification": "ARCHITECTURE_BLOCKING_GAP",
                    "code": f"{kind}_FLOOR_BINDING_UNRESOLVED",
                    "constraint_id": identity,
                    "blocks_full_structural_synthesis": True,
                })
        constraints.append(record)
    return constraints, unresolved


def _semantic_opening_constraints(parent: Mapping[str, Any]) -> list[dict[str, Any]]:
    output = []
    for item in parent.get("preserved_graph_refs", {}).get("opening_references", []):
        if not isinstance(item, Mapping):
            continue
        output.append({
            "constraint_id": f"OPENING:{item.get('opening_id')}",
            "opening_id": str(item.get("opening_id")), "floor_id": item.get("floor"),
            "opening_type": str(item.get("kind") or "UNKNOWN").upper(),
            "canonical_path": item.get("canonical_path"), "polygon": None,
            "geometry_status": "CANONICAL_REFERENCE_ONLY",
            "structural_policy": "DO_NOT_BLOCK_HOST_OR_OPENING_GEOMETRY",
            "door_swing_inferred": False,
        })
    return sorted(output, key=lambda item: item["constraint_id"])


def _semantic_access_constraints(parent: Mapping[str, Any]) -> list[dict[str, Any]]:
    output = []
    for item in parent.get("preserved_graph_refs", {}).get("access_references", []):
        if not isinstance(item, Mapping):
            continue
        output.append({
            "constraint_id": f"ACCESS:{item.get('relation_id')}",
            "relation_id": str(item.get("relation_id")), "from": item.get("from"),
            "to": item.get("to"), "kind": item.get("kind"),
            "canonical_path": item.get("canonical_path"), "polygon": None,
            "geometry_status": "CANONICAL_REFERENCE_ONLY",
            "structural_policy": "DO_NOT_BLOCK_VERIFIED_ACCESS_CONNECTION",
        })
    return sorted(output, key=lambda item: item["constraint_id"])


def _external_constraints(parent: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    semantic: list[dict[str, Any]] = []
    geometric: list[dict[str, Any]] = []
    for floor in parent.get("floor_geometries", []):
        for item in floor.get("external_spaces", []) if isinstance(floor, Mapping) else []:
            semantic.append({
                "constraint_id": f"EXTERNAL-SPACE:{item.get('space_id')}",
                "constraint_type": "EXTERNAL_SPACE_NO_ENCLOSURE_ZONE",
                "floor_id": floor.get("floor_id"), "space_id": item.get("space_id"),
                "polygon": None, "geometry_status": "SEMANTIC_ONLY",
                "structural_policy": "NO_STRUCTURE_DRIVEN_INTERIOR_CONVERSION",
            })
    for roof in parent.get("roof_geometries", []):
        for item in roof.get("terraces", []) if isinstance(roof, Mapping) else []:
            if item.get("external") is not True or item.get("polygon") is None:
                continue
            record = {
                "constraint_id": f"ROOF-TERRACE:{item.get('terrace_id')}",
                "constraint_type": "EXTERNAL_SPACE_NO_ENCLOSURE_ZONE",
                "floor_id": roof.get("source_floor_id"), "roof_geometry_ref": roof.get("geometry_id"),
                "polygon": deepcopy(item["polygon"]), "geometry_status": "EXPLICIT",
                "structural_policy": "NO_STRUCTURE_DRIVEN_ENCLOSURE",
            }
            semantic.append(deepcopy(record))
            geometric.append(record)
    return semantic, geometric


def _zone_floor_ids(item: Mapping[str, Any]) -> set[str]:
    values = item.get("floor_ids")
    if isinstance(values, (list, tuple)):
        return {str(value) for value in values}
    value = item.get("floor_id")
    return {str(value)} if value is not None else set()


def _eligible_regions(
    floors: list[dict[str, Any]], exclusions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    regions: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for floor in floors:
        floor_id = str(floor["floor_id"])
        envelope = _polygon(floor.get("polygon"), source=f"floor_geometries.{floor_id}")
        active: list[tuple[dict[str, Any], Polygon]] = []
        for exclusion in exclusions:
            if exclusion.get("polygon") is None or floor_id not in _zone_floor_ids(exclusion):
                continue
            shape = _polygon(exclusion["polygon"], source=str(exclusion.get("constraint_id") or exclusion.get("zone_id")))
            zone_type = str(exclusion.get("constraint_type") or exclusion.get("zone_type") or "")
            if zone_type in {"PROTECTED_ARCHITECTURAL_ZONE", "VERTICAL_CIRCULATION_PROTECTED_VOID"} and not envelope.covers(shape):
                conflicts.append({
                    "code": "PROTECTED_ZONE_OUTSIDE_ARCHITECTURAL_ENVELOPE",
                    "floor_id": floor_id,
                    "zone_id": exclusion.get("zone_id") or exclusion.get("constraint_id"),
                })
            intersection = envelope.intersection(shape)
            if not intersection.is_empty and intersection.area > 0:
                active.append((exclusion, shape))
        cut = unary_union([shape for _, shape in active]) if active else None
        eligible = envelope.difference(cut) if cut is not None else envelope
        parts = sorted(_polygon_parts(eligible), key=lambda item: item.wkb_hex)
        regions.append({
            "region_id": f"ELIGIBLE:{floor['geometry_id']}",
            "floor_id": floor_id, "architectural_envelope_ref": floor["geometry_id"],
            "polygons": [_surface(item) for item in parts],
            "area_m2": float(sum(item.area for item in parts)),
            "excluded_constraint_refs": sorted(str(item.get("constraint_id") or item.get("zone_id")) for item, _ in active),
            "eligibility_status": "DETERMINED_FROM_ARCHITECTURE_MINUS_PROVEN_EXCLUSIONS",
            "placement_points_generated": False, "grid_generated": False,
            "beam_lines_generated": False,
        })
    return regions, conflicts


def _floor_roof_constraints(parent: Mapping[str, Any], protected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for floor in parent.get("floor_geometries", []):
        floor_id = str(floor["floor_id"])
        output.append({
            "record_type": "FLOOR_ARCHITECTURAL_INPUT", "floor_id": floor_id,
            "architectural_envelope_ref": floor["geometry_id"], "envelope_ref": floor.get("envelope_ref"),
            "elevation": deepcopy(floor.get("elevation")),
            "void_refs": sorted(str(item.get("void_id")) for item in parent.get("vertical_voids", []) if floor_id in _zone_floor_ids(item)),
            "protected_zone_refs": sorted(str(item.get("zone_id")) for item in protected if floor_id in _zone_floor_ids(item)),
            "external_space_refs": sorted(str(item.get("space_id")) for item in floor.get("external_spaces", [])),
            "support_eligibility": "EVALUATED_SEPARATELY_NO_SUPPORTS_PLACED",
            "structural_system_inferred": False,
        })
    for roof in parent.get("roof_geometries", []):
        output.append({
            "record_type": "ROOF_ARCHITECTURAL_INPUT", "roof_geometry_ref": roof.get("geometry_id"),
            "source_floor_id": roof.get("source_floor_id"), "boundary_ref": roof.get("boundary_ref"),
            "roof_type": roof.get("roof_type"), "slope": deepcopy(roof.get("slope")),
            "terrace_refs": sorted(str(item.get("terrace_id")) for item in roof.get("terraces", [])),
            "support_eligibility": "ENVELOPE_REFERENCE_ONLY_NO_ROOF_STRUCTURE_INFERRED",
            "structural_system_inferred": False,
        })
    return output


def analyze_architectural_structural_readiness_v1(
    parent_candidate: Mapping[str, Any], *,
    readiness_evidence: Mapping[str, Any] | None = None,
    analysis_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a Design-05 child without invoking or modifying structure."""
    if not verify_design_04_candidate(parent_candidate):
        raise Design05ReadinessAnalysisError("STALE_PARENT", [{
            "code": "INVALID_OR_STALE_DESIGN_04_PARENT",
        }])
    if not isinstance(analysis_provenance, Mapping) or not analysis_provenance:
        raise Design05ReadinessAnalysisError("FAILED", [{
            "code": "ANALYSIS_PROVENANCE_REQUIRED",
        }])
    parent_document = canonical_design_04_document(parent_candidate)
    parent_hash = design_04_semantic_hash(parent_candidate)
    evidence = _readiness_evidence(readiness_evidence)

    floors = [deepcopy(dict(item)) for item in parent_candidate.get("floor_geometries", []) if isinstance(item, Mapping)]
    if not floors:
        raise Design05ReadinessAnalysisError("INSUFFICIENT_ARCHITECTURAL_EVIDENCE", [{
            "code": "DESIGN_04_FLOOR_GEOMETRY_MISSING",
        }])

    protected, gaps = _parent_zones(parent_candidate)
    explicit_protected, explicit_protected_gaps = _explicit_constraints(
        evidence, "protected_zones", kind="PROTECTED_ARCHITECTURAL_ZONE"
    )
    protected.extend({**item, "zone_id": item["constraint_id"]} for item in explicit_protected)
    gaps.extend(explicit_protected_gaps)

    opening_semantic = _semantic_opening_constraints(parent_candidate)
    opening_explicit, opening_gaps = _explicit_constraints(
        evidence, "opening_clearances", kind="OPENING_CLEARANCE_ZONE"
    )
    access_semantic = _semantic_access_constraints(parent_candidate)
    access_explicit, access_gaps = _explicit_constraints(
        evidence, "access_circulation_zones", kind="PRIMARY_CIRCULATION_ZONE"
    )
    opening_ids = {
        str(item.get("opening_id"))
        for item in parent_candidate.get("preserved_graph_refs", {}).get("opening_references", [])
        if isinstance(item, Mapping) and item.get("opening_id") is not None
    }
    access_ids = {
        str(item.get("relation_id"))
        for item in parent_candidate.get("preserved_graph_refs", {}).get("access_references", [])
        if isinstance(item, Mapping) and item.get("relation_id") is not None
    }
    for item in opening_explicit:
        if item.get("opening_id") is None or str(item.get("opening_id")) not in opening_ids:
            opening_gaps.append({
                "classification": "ARCHITECTURE_BLOCKING_GAP",
                "code": "OPENING_REFERENCE_UNRESOLVED",
                "constraint_id": item["constraint_id"],
                "blocks_full_structural_synthesis": True,
            })
    for item in access_explicit:
        if item.get("relation_id") is None or str(item.get("relation_id")) not in access_ids:
            access_gaps.append({
                "classification": "ARCHITECTURE_BLOCKING_GAP",
                "code": "ACCESS_REFERENCE_UNRESOLVED",
                "constraint_id": item["constraint_id"],
                "blocks_full_structural_synthesis": True,
            })
    gaps.extend(opening_gaps + access_gaps)
    external_constraints, geometric_external = _external_constraints(parent_candidate)

    exclusions = [
        *[item for item in protected if item.get("polygon") is not None],
        *[item for item in opening_explicit if item.get("polygon") is not None],
        *[item for item in access_explicit if item.get("polygon") is not None],
        *geometric_external,
    ]
    eligible, conflicts = _eligible_regions(floors, exclusions)

    for item in parent_candidate.get("unresolved_evidence", []):
        if not isinstance(item, Mapping):
            continue
        classification = str(item.get("classification") or "UNKNOWN")
        if classification == "VERTICAL_VOID_GEOMETRY_PENDING":
            gaps.append({
                "classification": "ARCHITECTURE_BLOCKING_GAP",
                "code": "VERTICAL_VOID_GEOMETRY_PENDING", "void_id": item.get("void_id"),
                "floor_ids": deepcopy(item.get("floor_ids", [])),
                "blocks_full_structural_synthesis": True,
            })
        elif classification == "FLOOR_ELEVATION_UNRESOLVED":
            gaps.append({
                "classification": "ARCHITECTURE_BLOCKING_GAP",
                "code": "FLOOR_ELEVATION_UNRESOLVED", "floor_id": item.get("floor_id"),
                "default_applied": False, "blocks_full_structural_synthesis": True,
            })
        elif classification in {"ROOF_TYPE_UNRESOLVED", "ROOF_SLOPE_UNRESOLVED", "INSUFFICIENT_ROOF_EVIDENCE"}:
            gaps.append({
                "classification": "NON_BLOCKING_FUTURE_RECHECK",
                "code": classification, "default_applied": False,
                "blocks_full_structural_synthesis": False,
            })

    pending_void = any(item.get("code") == "VERTICAL_VOID_GEOMETRY_PENDING" for item in gaps)
    unsafe_binding = any(
        str(item.get("code", "")).endswith("_BINDING_UNRESOLVED")
        or str(item.get("code", "")).endswith("_REFERENCE_UNRESOLVED")
        for item in gaps
    )
    if conflicts:
        readiness_status = "BLOCKED_PROTECTED_ZONE"
    elif pending_void:
        readiness_status = "BLOCKED_VERTICAL_VOID_EVIDENCE"
    elif unsafe_binding:
        readiness_status = "BLOCKED_GEOMETRY_EVIDENCE"
    elif any(item.get("classification") == "ARCHITECTURE_BLOCKING_GAP" for item in gaps):
        readiness_status = "READY_WITH_ARCHITECTURAL_GAPS"
    else:
        readiness_status = "READY_FOR_STRUCTURAL_SYNTHESIS"

    requirements = [
        {"classification": "STRUCTURAL_DESIGN_INPUT_GAP", "input": "STRUCTURAL_SYSTEM_SELECTION", "provided_by_architecture": False},
        {"classification": "STRUCTURAL_DESIGN_INPUT_GAP", "input": "MATERIAL_AND_MEMBER_SIZING", "provided_by_architecture": False},
        {"classification": "STRUCTURAL_DESIGN_INPUT_GAP", "input": "SPAN_AND_SUPPORT_STRATEGY", "provided_by_architecture": False},
        {"classification": "STRUCTURAL_DESIGN_INPUT_GAP", "input": "LOAD_AND_USE_CRITERIA", "provided_by_architecture": False},
    ]
    vertical_constraints = [deepcopy(item) for item in protected if "VOID" in str(item.get("zone_type", "")) or item.get("void_id")]
    vertical_checks = [{
        "check": "VERTICAL_VOID_CONTINUITY_FROM_EXPLICIT_LINKS_ONLY",
        "void_id": item.get("void_id"), "floor_ids": deepcopy(item.get("floor_ids", [])),
        "status": "PASS" if item.get("polygon") is not None else "UNRESOLVED",
        "support_stack_inferred": False,
    } for item in protected if item.get("void_id")]

    fingerprint_payload = {
        "parent_candidate_id": parent_candidate["candidate_id"],
        "parent_candidate_version": parent_candidate["candidate_version"],
        "parent_candidate_hash": parent_hash, "readiness_evidence": evidence,
        "protected_zones": protected, "exclusion_zones": exclusions,
        "eligible_support_regions": eligible, "gaps": gaps, "conflicts": conflicts,
    }
    fingerprint = hashlib.sha256(_stable_json(fingerprint_payload).encode("utf-8")).hexdigest()
    suffix = fingerprint[:16]
    candidate: dict[str, Any] = {
        "contract": CONTRACT, "contract_version": VERSION,
        "candidate_id": f"{parent_candidate['candidate_id']}::DESIGN-05::{suffix}",
        "candidate_version": f"{parent_candidate['candidate_version']}+design-05.{suffix}",
        "parent_candidate_id": parent_candidate["candidate_id"],
        "parent_candidate_version": parent_candidate["candidate_version"],
        "parent_candidate_hash": parent_hash,
        "parent_baseline_id": parent_candidate["parent_baseline_id"],
        "parent_baseline_version": parent_candidate["parent_baseline_version"],
        "parent_baseline_hash": parent_candidate["parent_baseline_hash"],
        "analysis_status": "ANALYZED", "readiness_status": readiness_status,
        "readiness_scope": SCOPE,
        "architectural_authority_refs": _authority_refs(parent_candidate),
        "protected_zones": protected, "exclusion_zones": exclusions,
        "eligible_support_regions": eligible,
        "vertical_void_constraints": vertical_constraints,
        "opening_clearance_constraints": opening_semantic + opening_explicit,
        "access_circulation_constraints": access_semantic + access_explicit,
        "floor_roof_constraints": _floor_roof_constraints(parent_candidate, protected),
        "external_space_constraints": external_constraints,
        "structural_input_requirements": requirements,
        "unresolved_architectural_evidence": gaps,
        "readiness_checks": [
            {"check": "ARCHITECTURAL_EXTENTS_ARE_AUTHORITATIVE", "status": "PASS"},
            {"check": "ELIGIBILITY_FROM_ARCHITECTURE_MINUS_PROVEN_EXCLUSIONS", "status": "PASS"},
            {"check": "NO_GRID_OR_BAY_ASSUMPTION", "status": "PASS"},
            {"check": "NO_COLUMNS_BEAMS_OR_SUPPORT_POINTS_GENERATED", "status": "PASS"},
            {"check": "PROTECTED_ZONE_COMPATIBILITY", "status": "FAIL" if conflicts else "PASS", "conflicts": conflicts},
            *vertical_checks,
        ],
        "required_downstream_rechecks": [
            "VERIFY_DESIGN_05_PARENT_AND_CANDIDATE_HASHES_BEFORE_CONSUMPTION",
            "RESOLVE_ALL_ARCHITECTURE_BLOCKING_GAPS_BEFORE_FULL_STRUCTURAL_SYNTHESIS",
            "STRUCTURAL_GRID_MUST_CONSUME_ARCHITECTURAL_EXTENTS_WITHOUT_RESIZING",
            "RECHECK_OPENING_ACCESS_VOID_AND_EXTERNAL_SPACE_CONSTRAINTS_AFTER_ANY_PROPOSAL",
            "STRUCTURE_BIM_IFC_RENDER_REMAIN_UNIMPLEMENTED_IN_DESIGN_05",
        ],
        "structural_architecture_input": {
            "contract": INPUT_CONTRACT, "version": "1.0",
            "authority": "DESIGN_05_ARCHITECTURE_OWNED_READ_ONLY",
            "readiness_status": readiness_status,
            "floor_envelopes": [{"floor_id": item["floor_id"], "geometry_ref": item["geometry_id"], "polygon": deepcopy(item["polygon"]), "elevation": deepcopy(item.get("elevation"))} for item in floors],
            "roof_envelopes": [{"roof_geometry_ref": item.get("geometry_id"), "polygon": deepcopy(item.get("polygon")), "roof_type": item.get("roof_type"), "slope": deepcopy(item.get("slope"))} for item in parent_candidate.get("roof_geometries", [])],
            "voids": deepcopy(vertical_constraints), "protected_zones": deepcopy(protected),
            "eligible_support_regions": deepcopy(eligible),
            "opening_access_restrictions": deepcopy(opening_semantic + opening_explicit + access_semantic + access_explicit),
            "unresolved_architectural_gaps": deepcopy(gaps),
            "grid_spacing": None, "column_count": None, "beam_layout": None,
            "member_sizes": None, "material_grades": None, "loads": None,
        },
        "legacy_structural_grid_guard": {
            "fixed_grid_authoritative": False, "equal_bay_grid_authoritative": False,
            "four_meter_grid_authoritative": False,
            "architecture_resize_to_grid_allowed": False,
            "future_consumer_requirement": "CONSUME_DESIGN_05_EXTENTS_CONSTRAINTS_AND_ELIGIBILITY_WITHOUT_ARCHITECTURAL_MUTATION",
            "structural_grid_engine_modified": False,
        },
        "evidence_source_audit": [
            {"source": "Design04DerivedArchitecturalGeometryCandidateV1", "classification": "ARCHITECTURAL_AUTHORITY"},
            {"source": "floor_geometries/slab_geometries/roof_geometries", "classification": "ARCHITECTURAL_AUTHORITY"},
            {"source": "vertical_voids/protected_zones", "classification": "ARCHITECTURAL_AUTHORITY"},
            {"source": "preserved opening/access/boundary graph references", "classification": "ARCHITECTURAL_AUTHORITY"},
            {"source": "explicit verified readiness evidence", "classification": "REUSABLE_INTERFACE" if evidence else "OUT_OF_SCOPE_NOT_SUPPLIED"},
            {"source": "architecture_structure_handoff_v1", "classification": "REUSABLE_INTERFACE_FUTURE_ADAPTER"},
            {"source": "structural_grid_engine/structural_element_engine", "classification": "STRUCTURAL_CONSUMER_NOT_EXECUTED"},
            {"source": "fixed width/depth/equal-bay/grid assumptions", "classification": "LEGACY_STRUCTURAL_ASSUMPTION_NOT_AUTHORITY"},
            {"source": "BIM/IFC/CAD/render geometry", "classification": "OUT_OF_SCOPE"},
        ],
        "lineage": {
            "parent_candidate_id": parent_candidate["candidate_id"],
            "parent_candidate_version": parent_candidate["candidate_version"],
            "parent_candidate_hash": parent_hash,
            "parent_baseline_id": parent_candidate["parent_baseline_id"],
            "parent_baseline_version": parent_candidate["parent_baseline_version"],
            "parent_baseline_hash": parent_candidate["parent_baseline_hash"],
            "parent_contract": parent_candidate["contract"],
            "design_04_parent_mutated": False, "accepted_baseline_mutated": False,
            "analysis_fingerprint": fingerprint,
        },
        "provenance": {
            "phase": PHASE, "engine": ENGINE_VERSION,
            "analysis": deepcopy(dict(analysis_provenance)),
            "evidence_policy": "DESIGN_04_AUTHORITY_PLUS_EXPLICIT_VERIFIED_READINESS_EVIDENCE_ONLY",
            "clearance_dimensions_inferred": False, "floor_elevation_defaulted": False,
            "roof_properties_defaulted": False, "vertical_support_stacks_inferred": False,
            "structural_synthesis_performed": False,
        },
        "immutability": {
            "accepted_baseline": "READ_ONLY", "design_04_parent": "READ_ONLY",
            "architectural_geometry": "AUTHORITATIVE_READ_ONLY",
            "in_place_revision_allowed": False,
        },
        "architecture_only": True,
        "generated_structural_elements": [],
        "side_effects": {"structure": False, "bim": False, "ifc": False, "render": False, "chat_intelligence": False},
    }
    candidate["candidate_hash"] = design_05_semantic_hash(candidate)
    if canonical_design_04_document(parent_candidate) != parent_document or design_04_semantic_hash(parent_candidate) != parent_hash:
        raise RuntimeError("Design-04 parent mutated during Design-05 analysis")
    return candidate


__all__ = [
    "Design05ReadinessAnalysisError", "ENGINE_VERSION", "PHASE", "SCOPE",
    "analyze_architectural_structural_readiness_v1",
]
