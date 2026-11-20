"""Evidence-bound Design-03 opening, privacy, and parcel-edge intelligence."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
from typing import Any

from core.architecture.contracts.architectural_opening_privacy_parcel_edge_intelligence_v1 import (
    CONTRACT,
    DERIVATION_STATUS,
    OPENING_CONTRACT,
    OPENING_PARCEL_CONTRACT,
    PARCEL_EDGE_CONTRACT,
    PRIVACY_CONTRACT,
    VERSION,
    design_03_semantic_hash,
)
from core.architecture.contracts.derived_architectural_candidate_v1 import (
    canonical_derived_candidate_document,
    derived_candidate_semantic_hash,
    verify_derived_architectural_candidate,
)
from core.architecture.knowledge.architectural_space_knowledge_v1 import SPACE_SPECS


PHASE = "ARCHITECTURAL-BASELINE-DESIGN-03"
ENGINE_VERSION = "architectural_baseline_opening_privacy_parcel_edge_intelligence_v1"
SCOPE = "OPENING_PRIVACY_PARCEL_EDGE_INTELLIGENCE_NO_GEOMETRY"
_VERIFIED = {"ACCEPTED", "RESOLVED", "VERIFIED", "ACCEPTED_FROZEN"}
_HOST_FIELDS = ("host_wall_solid_id", "host_wall_pair_id", "host_face_a", "host_face_b", "host_boundary_id")


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _records_by_floor(root: Any, record_key: str) -> list[tuple[str, dict[str, Any]]]:
    records: list[tuple[str, dict[str, Any]]] = []
    if not isinstance(root, Mapping):
        return records
    for floor in sorted(root, key=str):
        graph = root[floor]
        raw = graph.get(record_key, ()) if isinstance(graph, Mapping) else ()
        if isinstance(raw, (list, tuple)):
            records.extend(
                (str(floor), deepcopy(dict(item))) for item in raw if isinstance(item, Mapping)
            )
    return records


def _identity(record: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    value = next((record.get(key) for key in keys if record.get(key) is not None), None)
    return str(value) if value is not None else None


def _evidence(source_class: str, path: str, record_ids: Sequence[str], provenance: str) -> dict[str, Any]:
    return {
        "source_class": source_class,
        "canonical_path": path,
        "source_record_ids": sorted({str(item) for item in record_ids if item is not None}),
        "confidence": "DIRECT_VERIFIED_RECORD",
        "provenance": provenance,
    }


def _opening_catalog(parent: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    extraction = parent.get("boundary_extraction", {})
    spaces = {
        identity: {"floor": floor, "record": record}
        for floor, record in _records_by_floor(extraction.get("space_boundary_graphs"), "spaces")
        if (identity := _identity(record, ("space_id", "id")))
    }
    openings = {
        identity: {"floor": floor, "record": record}
        for floor, record in _records_by_floor(extraction.get("opening_host_graphs"), "openings")
        if (identity := _identity(record, ("opening_id", "id")))
    }
    access = extraction.get("access_graph", {})
    raw_nodes = access.get("nodes", ()) if isinstance(access, Mapping) else ()
    raw_edges = access.get("edges", ()) if isinstance(access, Mapping) else ()
    nodes = {
        identity: deepcopy(dict(item))
        for item in raw_nodes if isinstance(item, Mapping)
        if (identity := _identity(item, ("node_id", "id")))
    } if isinstance(raw_nodes, (list, tuple)) else {}
    edges = {
        identity: deepcopy(dict(item))
        for item in raw_edges if isinstance(item, Mapping)
        if (identity := _identity(item, ("edge_id", "id")))
    } if isinstance(raw_edges, (list, tuple)) else {}
    return spaces, openings, nodes, edges


def _opening_intelligence(
    parent: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    spaces, openings, nodes, edges = _opening_catalog(parent)
    protected = set(str(item) for item in parent.get("constraints", {}).get("protected_entities", ()))
    for constraint in parent.get("constraints", {}).get("protected_constraints", ()):
        if isinstance(constraint, Mapping):
            protected.update(
                str(constraint[key]) for key in ("entity_id", "opening_id", "boundary_ref")
                if constraint.get(key) is not None
            )
    records: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    index: dict[str, dict[str, Any]] = {}
    for opening_id, item in sorted(openings.items()):
        source = item["record"]
        path = f"boundary_extraction.opening_host_graphs.{item['floor']}.openings"
        evidence_refs = [_evidence("CANONICAL_EVIDENCE", path, [opening_id], "ACCEPTED_BASELINE_OPENING_HOST_GRAPH")]
        kind = str(source.get("kind") or source.get("opening_type") or "").upper()
        opening_type = kind.lower() if kind in {"DOOR", "WINDOW"} else "unknown"
        host_refs = sorted({str(source[key]) for key in _HOST_FIELDS if source.get(key) is not None})
        host_verified = bool(host_refs) and str(source.get("status", "")).upper() in _VERIFIED
        sides = [str(source[key]) for key in ("side_a", "side_b") if source.get(key) is not None]
        connected_spaces = sorted({side for side in sides if side in spaces})
        exterior_refs = sorted({
            side for side in sides
            if side in nodes and str(nodes[side].get("semantic_class", "")).upper() == "EXTERIOR"
        })
        for space_id in connected_spaces:
            space_item = spaces[space_id]
            evidence_refs.append(_evidence(
                "CANONICAL_EVIDENCE",
                f"boundary_extraction.space_boundary_graphs.{space_item['floor']}.spaces",
                [space_id], "ACCEPTED_BASELINE_SPACE_BOUNDARY_GRAPH",
            ))
        if exterior_refs:
            evidence_refs.append(_evidence(
                "CANONICAL_EVIDENCE", "boundary_extraction.access_graph.nodes",
                exterior_refs, "ACCEPTED_BASELINE_EXTERIOR_NODE",
            ))
        edge = edges.get(opening_id)
        edge_endpoints = []
        if isinstance(edge, Mapping):
            edge_endpoints = [str(edge[key]) for key in ("from", "to") if edge.get(key) is not None]
            if all(endpoint in nodes for endpoint in edge_endpoints) and edge_endpoints:
                evidence_refs.append(_evidence(
                    "CANONICAL_EVIDENCE", "boundary_extraction.access_graph.edges",
                    [opening_id, *edge_endpoints], "ACCEPTED_BASELINE_ACCESS_GRAPH",
                ))
        if exterior_refs and connected_spaces:
            host_relation = "EXTERIOR"
        elif len(connected_spaces) == 2:
            host_relation = "INTERIOR"
        else:
            host_relation = "UNKNOWN"
        access_role = "NONE"
        if opening_type == "door" and edge_endpoints and set(edge_endpoints) == set(sides):
            access_role = "VERIFIED_ACCESS_CONNECTION"
        elif opening_type == "door":
            access_role = "ACCESS_RELATION_UNRESOLVED"
        protected_refs = sorted((set(host_refs) | {opening_id}) & protected)
        if protected_refs:
            evidence_refs.append(_evidence(
                "CANONICAL_EVIDENCE", "constraints.protected_constraints|protected_entities",
                protected_refs, "DESIGN_02_CARRIED_PROTECTED_CONSTRAINTS",
            ))
        if not host_verified:
            status = "OPENING_HOST_UNRESOLVED"
            unresolved.append({
                "classification": "OPENING_HOST_UNRESOLVED", "opening_id": opening_id,
                "code": "verified_host_reference_missing", "inference_performed": False,
                "evidence_refs": deepcopy(evidence_refs),
            })
        elif host_relation == "UNKNOWN":
            status = "PARTIAL"
            unresolved.append({
                "classification": "INSUFFICIENT_EVIDENCE", "opening_id": opening_id,
                "code": "interior_exterior_relation_unresolved", "inference_performed": False,
                "evidence_refs": deepcopy(evidence_refs),
            })
        else:
            status = "VERIFIED"
        record = {
            "contract": OPENING_CONTRACT,
            "opening_id": opening_id,
            "opening_type": opening_type,
            "floor": item["floor"],
            "host_refs": host_refs,
            "host_relation": host_relation,
            "connected_spaces": connected_spaces,
            "exterior_refs": exterior_refs,
            "access_role": access_role,
            "daylight_view_opportunity": (
                "EXTERIOR_OPPORTUNITY_NO_PERFORMANCE_CLAIM"
                if opening_type == "window" and host_relation == "EXTERIOR" else "NOT_ASSERTED"
            ),
            "protected_constraint_refs": protected_refs,
            "unresolved_host_or_adjacency": status != "VERIFIED",
            "status": status,
            "evidence_refs": evidence_refs,
            "geometry_mutated": False,
        }
        records.append(record)
        index[opening_id] = record
    return records, unresolved, index


def _site_gate(site_evidence: Any) -> tuple[bool, str]:
    if not isinstance(site_evidence, Mapping) or not site_evidence:
        return False, "active_production_site_evidence_not_supplied"
    status = str(site_evidence.get("status", "")).upper()
    if status in _VERIFIED:
        return True, "verified_site_evidence"
    if (
        site_evidence.get("contract") == "SiteAccessEvidenceDerivationV1"
        and str(site_evidence.get("derivation_status", "")).lower() in {"resolved", "partial"}
    ):
        return True, "active_site_access_evidence_derivation"
    return False, "site_evidence_contract_or_status_not_verified"


def _parcel_intelligence(
    site_evidence: Any, opening_index: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str]:
    gate, gate_reason = _site_gate(site_evidence)
    if not gate:
        return [], [], [{
            "classification": "PARCEL_EDGE_ANALYSIS_PENDING",
            "code": gate_reason,
            "status": "INSUFFICIENT_SITE_EVIDENCE",
            "inference_performed": False,
        }], "INSUFFICIENT_SITE_EVIDENCE"
    site = dict(site_evidence)
    raw_edges = site.get("parcel_edges", ())
    raw_edges = raw_edges if isinstance(raw_edges, (list, tuple)) else ()
    road_ids = {
        str(item.get("edge_id")) for item in site.get("road_frontages", ())
        if isinstance(item, Mapping) and item.get("edge_id") is not None
    } if isinstance(site.get("road_frontages", ()), (list, tuple)) else set()
    edges: list[dict[str, Any]] = []
    edge_index: dict[str, dict[str, Any]] = {}
    for offset, source in enumerate(raw_edges):
        if not isinstance(source, Mapping):
            continue
        edge_id = _identity(source, ("edge_id", "id"))
        if edge_id is None and source.get("edge_index") is not None:
            edge_id = str(source["edge_index"])
        individually_verified = (
            source.get("confirmed") is True
            or str(source.get("status", "")).upper() in _VERIFIED
            or source.get("source") == "authoritative_parcel_polygon"
        )
        if edge_id is None or not individually_verified:
            continue
        raw_relation = str(source.get("relation") or source.get("type") or "").lower()
        if edge_id in road_ids or raw_relation in {"road", "road_access", "public_road", "street"}:
            relation_type = "ROAD_EDGE"
        elif raw_relation in {"neighbor", "neighbor_parcel", "adjacent_private_parcel"}:
            relation_type = "NEIGHBOR_EDGE"
        elif raw_relation in {"setback", "setback_edge"}:
            relation_type = "SETBACK_EDGE"
        else:
            relation_type = "INTERNAL/UNKNOWN_EDGE"
        neighbor_id = source.get("neighbor_parcel_id", source.get("parcel_id"))
        evidence = _evidence(
            "SITE_EVIDENCE", f"site_evidence.parcel_edges[{offset}]", [edge_id],
            str(site.get("contract") or "VERIFIED_SITE_EVIDENCE"),
        )
        record = {
            "contract": PARCEL_EDGE_CONTRACT,
            "boundary_ref": None,
            "parcel_edge_ref": edge_id,
            "relation_type": relation_type,
            "neighbor_parcel_id": deepcopy(neighbor_id) if relation_type == "NEIGHBOR_EDGE" else None,
            "road_relation": "VERIFIED" if relation_type == "ROAD_EDGE" else "NOT_ASSERTED",
            "distance_or_setback": deepcopy(source.get("distance", source.get("setback"))),
            "status": "VERIFIED",
            "evidence_refs": [evidence],
            "orientation": None,
        }
        edges.append(record)
        edge_index[edge_id] = record

    bindings: list[tuple[int, Mapping[str, Any]]] = []
    for key in ("boundary_edge_bindings", "opening_edge_bindings"):
        raw = site.get(key, ())
        if isinstance(raw, (list, tuple)):
            bindings.extend((offset, item) for offset, item in enumerate(raw) if isinstance(item, Mapping))
    opening_relations: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for opening_id, opening in sorted(opening_index.items()):
        if opening.get("host_relation") != "EXTERIOR":
            continue
        matches: list[tuple[int, Mapping[str, Any], str]] = []
        for offset, binding in bindings:
            binding_status = str(binding.get("status", "")).upper()
            if not (binding.get("confirmed") is True or binding_status in _VERIFIED):
                continue
            edge_ref = binding.get("parcel_edge_ref", binding.get("edge_id"))
            boundary_ref = binding.get("boundary_ref", binding.get("host_boundary_ref"))
            direct_opening = str(binding.get("opening_id")) == opening_id if binding.get("opening_id") is not None else False
            host_match = boundary_ref is not None and str(boundary_ref) in opening.get("host_refs", ())
            if edge_ref is not None and str(edge_ref) in edge_index and (direct_opening or host_match):
                matches.append((offset, binding, str(edge_ref)))
        if len(matches) == 1:
            offset, binding, edge_ref = matches[0]
            edge = edge_index[edge_ref]
            refs = deepcopy(opening["evidence_refs"])
            refs.extend(deepcopy(edge["evidence_refs"]))
            refs.append(_evidence(
                "SITE_EVIDENCE", f"site_evidence.verified_edge_bindings[{offset}]",
                [opening_id, edge_ref, str(binding.get("boundary_ref") or "")],
                str(site.get("contract") or "VERIFIED_SITE_EVIDENCE"),
            ))
            opening_relations.append({
                "contract": OPENING_PARCEL_CONTRACT,
                "opening_id": opening_id,
                "host_boundary_refs": deepcopy(opening["host_refs"]),
                "parcel_edge_ref": edge_ref,
                "relation_type": edge["relation_type"],
                "neighbor_parcel_id": deepcopy(edge["neighbor_parcel_id"]),
                "status": "VERIFIED",
                "evidence_refs": refs,
                "orientation_inferred": False,
            })
        else:
            opening_relations.append({
                "contract": OPENING_PARCEL_CONTRACT,
                "opening_id": opening_id,
                "host_boundary_refs": deepcopy(opening["host_refs"]),
                "parcel_edge_ref": None,
                "relation_type": "PARCEL_RELATION_UNRESOLVED",
                "neighbor_parcel_id": None,
                "status": "PARCEL_RELATION_UNRESOLVED",
                "evidence_refs": deepcopy(opening["evidence_refs"]),
                "orientation_inferred": False,
            })
            unresolved.append({
                "classification": "PARCEL_RELATION_UNRESOLVED", "opening_id": opening_id,
                "code": "unique_verified_opening_or_host_boundary_to_parcel_edge_binding_missing",
                "inference_performed": False,
            })
    site_status = "VERIFIED" if edges and not unresolved else "PARTIAL"
    if not edges:
        unresolved.append({
            "classification": "PARCEL_EDGE_ANALYSIS_PENDING",
            "code": "no_individually_verified_parcel_edges",
            "status": "INSUFFICIENT_SITE_EVIDENCE",
            "inference_performed": False,
        })
        site_status = "INSUFFICIENT_SITE_EVIDENCE"
    return edges, opening_relations, unresolved, site_status


def _space_semantics(parent: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in parent.get("semantic_state", {}).get("spaces", ()):
        if not isinstance(item, Mapping) or item.get("space_id") is None:
            continue
        labels = item.get("semantic_labels", {})
        labels = labels if isinstance(labels, Mapping) else {}
        raw = next((labels.get(key) for key in ("semantic_class", "semantic_role", "label") if labels.get(key)), None)
        semantic = "_".join(str(raw).strip().upper().replace("-", " ").split()) if raw is not None else None
        output[str(item["space_id"])] = {
            "semantic": semantic,
            "canonical_path": str(item.get("canonical_path") or "semantic_state.spaces"),
        }
    return output


def _privacy_assessments(
    parent: Mapping[str, Any], openings: Sequence[Mapping[str, Any]],
    opening_parcel: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    semantic_index = _space_semantics(parent)
    parcel_index = {str(item["opening_id"]): item for item in opening_parcel if item.get("opening_id") is not None}
    assessments: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for opening in openings:
        opening_id = str(opening["opening_id"])
        for space_id in opening.get("connected_spaces", ()): 
            semantic_info = semantic_index.get(str(space_id), {"semantic": None, "canonical_path": "semantic_state.spaces"})
            semantic = semantic_info["semantic"]
            spec = SPACE_SPECS.get(semantic) if semantic else None
            privacy_class = str(spec.get("privacy_class")) if isinstance(spec, Mapping) and spec.get("privacy_class") else "UNKNOWN"
            refs = deepcopy(opening["evidence_refs"])
            refs.append(_evidence(
                "DERIVED_SEMANTIC_EVIDENCE", semantic_info["canonical_path"], [str(space_id)],
                "DESIGN_02_EFFECTIVE_SEMANTIC_IDENTITY",
            ))
            if spec is not None:
                refs.append(_evidence(
                    "DERIVED_SEMANTIC_EVIDENCE",
                    f"core.architecture.knowledge.architectural_space_knowledge_v1.SPACE_SPECS.{semantic}",
                    [semantic], "ACTIVE_ARCHITECTURAL_SPACE_ONTOLOGY",
                ))
            parcel = parcel_index.get(opening_id)
            if parcel and parcel.get("status") == "VERIFIED":
                refs.extend(deepcopy(parcel.get("evidence_refs", ())))
            risks: list[str] = []
            is_exterior = opening.get("host_relation") == "EXTERIOR"
            if is_exterior and semantic and ("BEDROOM" in semantic or semantic == "MASTER_BEDROOM_SLEEPING"):
                risks.append("BEDROOM_EXPOSURE")
            if is_exterior and semantic and any(token in semantic for token in ("BATHROOM", "ENSUITE", "WC")):
                risks.append("BATHROOM_EXPOSURE")
            if (
                is_exterior and privacy_class == "PRIVATE" and parcel
                and parcel.get("relation_type") == "NEIGHBOR_EDGE" and parcel.get("status") == "VERIFIED"
            ):
                risks.append("NEIGHBOR_FACING_EXPOSURE")
            other_spaces = [value for value in opening.get("connected_spaces", ()) if value != space_id]
            other_classes = []
            for other in other_spaces:
                other_semantic = semantic_index.get(str(other), {}).get("semantic")
                other_spec = SPACE_SPECS.get(other_semantic) if other_semantic else None
                if isinstance(other_spec, Mapping):
                    other_classes.append(str(other_spec.get("privacy_class", "UNKNOWN")))
                    refs.append(_evidence(
                        "DERIVED_SEMANTIC_EVIDENCE",
                        semantic_index[str(other)]["canonical_path"], [str(other)],
                        "DESIGN_02_CONNECTED_SPACE_SEMANTIC_IDENTITY",
                    ))
                    refs.append(_evidence(
                        "DERIVED_SEMANTIC_EVIDENCE",
                        f"core.architecture.knowledge.architectural_space_knowledge_v1.SPACE_SPECS.{other_semantic}",
                        [str(other_semantic)], "ACTIVE_ARCHITECTURAL_SPACE_ONTOLOGY",
                    ))
            if opening.get("opening_type") == "door" and privacy_class == "PRIVATE" and any(
                value in {"PUBLIC", "SEMI_PUBLIC", "COMMON"} for value in other_classes
            ):
                risks.extend(("PRIVATE_TO_PUBLIC_OPENING", "PRIVATE_SPACE_DIRECT_ACCESS"))
            risks = sorted(set(risks))
            gaps: list[str] = []
            if privacy_class == "UNKNOWN":
                gaps.append("canonical_room_semantic_identity_or_ontology_entry_missing")
            if is_exterior and (parcel is None or parcel.get("status") != "VERIFIED"):
                gaps.append("opening_parcel_edge_relation_unresolved")
            if gaps:
                unresolved.append({
                    "classification": "INSUFFICIENT_EVIDENCE", "space_id": str(space_id),
                    "opening_id": opening_id, "code": ";".join(sorted(gaps)),
                    "inference_performed": False,
                })
            status = "PRIVACY_RISK_IDENTIFIED" if risks else ("PARTIAL" if gaps else "VERIFIED")
            assessments.append({
                "contract": PRIVACY_CONTRACT,
                "space_id": str(space_id),
                "privacy_class": privacy_class,
                "opening_id": opening_id,
                "boundary_refs": deepcopy(opening.get("host_refs", ())),
                "exposure_type": "EXTERIOR_OPENING" if is_exterior else (
                    "INTERNAL_ACCESS" if opening.get("host_relation") == "INTERIOR" else "UNKNOWN"
                ),
                "exposure_target": (
                    parcel.get("relation_type") if parcel and parcel.get("status") == "VERIFIED" else "UNRESOLVED"
                ),
                "direct_view_risk": "POTENTIAL_NOT_GEOMETRICALLY_VERIFIED" if risks else "NOT_ASSERTED",
                "access_privacy_risk": any(risk in risks for risk in ("PRIVATE_TO_PUBLIC_OPENING", "PRIVATE_SPACE_DIRECT_ACCESS")),
                "adjacency_privacy_risk": "NOT_ASSERTED_WITHOUT_VIEW_OR_ADJACENCY_EVIDENCE",
                "privacy_risks": risks,
                "evidence_refs": refs,
                "unresolved_evidence": gaps,
                "privacy_constraints": ["NO_GEOMETRY_CHANGE_IN_DESIGN_03"] + (
                    ["FUTURE_PRIVACY_REALIZATION_REQUIRES_EXPLICIT_REVIEW"] if risks else []
                ),
                "status": status,
                "provenance": "EVIDENCE_BOUND_DESIGN_03_ASSESSMENT",
            })
    return assessments, unresolved


def enrich_opening_privacy_parcel_edge_intelligence_v1(
    parent_candidate: Mapping[str, Any], *, site_evidence: Mapping[str, Any] | None = None,
    enrichment_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a new immutable Design-03 child without realizing geometry."""
    if not verify_derived_architectural_candidate(parent_candidate):
        raise ValueError("valid non-stale DerivedArchitecturalCandidateV1 parent required")
    if not isinstance(enrichment_provenance, Mapping) or not enrichment_provenance:
        raise ValueError("evidence-bearing enrichment_provenance is required")
    parent_document = canonical_derived_candidate_document(parent_candidate)
    parent_hash = derived_candidate_semantic_hash(parent_candidate)
    site_input = deepcopy(dict(site_evidence)) if isinstance(site_evidence, Mapping) else None

    openings, opening_gaps, opening_index = _opening_intelligence(parent_candidate)
    parcel_edges, opening_parcel, parcel_gaps, site_status = _parcel_intelligence(site_input, opening_index)
    privacy, privacy_gaps = _privacy_assessments(parent_candidate, openings, opening_parcel)
    unresolved = opening_gaps + parcel_gaps + privacy_gaps
    fingerprint_payload = {
        "parent_candidate_id": parent_candidate["candidate_id"],
        "parent_candidate_version": parent_candidate["candidate_version"],
        "parent_candidate_hash": parent_hash,
        "scope": SCOPE,
        "site_evidence": site_input,
    }
    fingerprint = hashlib.sha256(_stable_json(fingerprint_payload).encode("utf-8")).hexdigest()
    suffix = fingerprint[:16]
    overall = "VERIFIED" if not unresolved else "PARTIAL"
    if not openings:
        overall = "INSUFFICIENT_EVIDENCE"
    candidate: dict[str, Any] = {
        "contract": CONTRACT,
        "contract_version": VERSION,
        "candidate_id": f"{parent_candidate['candidate_id']}::DESIGN-03::{suffix}",
        "candidate_version": f"{parent_candidate['candidate_version']}+design-03.{suffix}",
        "parent_candidate_id": parent_candidate["candidate_id"],
        "parent_candidate_version": parent_candidate["candidate_version"],
        "parent_candidate_hash": parent_hash,
        "parent_baseline_id": parent_candidate["parent_baseline_id"],
        "parent_baseline_version": parent_candidate["parent_baseline_version"],
        "parent_baseline_hash": parent_candidate["parent_baseline_hash"],
        "derivation_status": DERIVATION_STATUS,
        "intelligence_scope": SCOPE,
        "status": overall,
        "boundary_extraction": deepcopy(parent_candidate["boundary_extraction"]),
        "canonical_graph_references": deepcopy(parent_candidate.get("canonical_graph_references", {})),
        "semantic_state": deepcopy(parent_candidate.get("semantic_state", {})),
        "opening_references": deepcopy(parent_candidate.get("opening_references", [])),
        "access_references": deepcopy(parent_candidate.get("access_references", [])),
        "constraints": deepcopy(parent_candidate.get("constraints", {})),
        "opening_intelligence": openings,
        "privacy_assessments": privacy,
        "parcel_edge_relations": parcel_edges,
        "opening_parcel_relations": opening_parcel,
        "parent_unresolved_evidence": deepcopy(parent_candidate.get("unresolved_evidence", [])),
        "unresolved_evidence": unresolved,
        "required_rechecks": [
            "VERIFY_PARENT_DESIGN_02_HASH_BEFORE_FURTHER_DERIVATION",
            "RECHECK_PROTECTED_OPENINGS_AND_BOUNDARIES_BEFORE_GEOMETRY_REALIZATION",
            "RESOLVE_UNBOUND_OPENING_PARCEL_RELATIONS",
            "VERIFY_SITE_ORIENTATION_BEFORE_ORIENTATION_DEPENDENT_ANALYSIS",
            "RUN_DAYLIGHT_SIMULATION_BEFORE_PERFORMANCE_CLAIMS",
            "FLOOR_ROOF_GEOMETRY_REMAINS_DESIGN_04_SCOPE",
        ],
        "design_04_readiness": {
            "opening_intelligence": "VERIFIED_WITH_WARNINGS" if opening_gaps else "VERIFIED",
            "privacy_intelligence": "VERIFIED_WITH_WARNINGS" if privacy_gaps else "VERIFIED",
            "parcel_edge_intelligence": site_status,
            "geometry_realization_performed": False,
        },
        "evidence_source_audit": [
            {"source": "DerivedArchitecturalCandidateV1", "classification": "DERIVED_SEMANTIC_EVIDENCE"},
            {"source": "boundary_extraction.space_boundary_graphs", "classification": "CANONICAL_EVIDENCE"},
            {"source": "boundary_extraction.opening_host_graphs", "classification": "CANONICAL_EVIDENCE"},
            {"source": "boundary_extraction.wall_face_graphs", "classification": "CANONICAL_EVIDENCE"},
            {"source": "boundary_extraction.wall_solid_graphs", "classification": "CANONICAL_EVIDENCE"},
            {"source": "boundary_extraction.access_graph", "classification": "CANONICAL_EVIDENCE"},
            {"source": "architectural_space_knowledge_v1.SPACE_SPECS", "classification": "DERIVED_SEMANTIC_EVIDENCE"},
            {"source": "supplied active site evidence", "classification": "SITE_EVIDENCE" if site_status != "INSUFFICIENT_SITE_EVIDENCE" else "INSUFFICIENT"},
            {"source": "opening_reasoner_v1/v2", "classification": "OUT_OF_SCOPE_REALIZATION_OR_SYNTHESIS"},
            {"source": "shared_court_privacy_*", "classification": "OUT_OF_SCOPE_SCENARIO_SPECIFIC"},
        ],
        "lineage": {
            "parent_candidate_id": parent_candidate["candidate_id"],
            "parent_candidate_version": parent_candidate["candidate_version"],
            "parent_candidate_hash": parent_hash,
            "parent_baseline_id": parent_candidate["parent_baseline_id"],
            "parent_baseline_version": parent_candidate["parent_baseline_version"],
            "parent_baseline_hash": parent_candidate["parent_baseline_hash"],
            "parent_contract": parent_candidate["contract"],
            "accepted_parent_mutated": False,
            "design_02_parent_mutated": False,
            "enrichment_fingerprint": fingerprint,
        },
        "provenance": {
            "phase": PHASE,
            "engine": ENGINE_VERSION,
            "enrichment": deepcopy(dict(enrichment_provenance)),
            "evidence_policy": "CANONICAL_OR_EXPLICITLY_VERIFIED_EVIDENCE_ONLY",
            "geometry_created": False,
            "geometry_modified": False,
            "site_orientation_inferred": False,
            "front_rear_side_inferred": False,
            "daylight_performance_claimed": False,
        },
        "immutability": {
            "accepted_baseline": "READ_ONLY",
            "design_02_parent": "READ_ONLY",
            "canonical_geometry": "PRESERVED_EXACTLY",
            "in_place_revision_allowed": False,
            "future_realization_requires_new_derived_candidate": True,
        },
        "architecture_only": True,
        "side_effects": {
            "site": False, "structure": False, "bim": False, "ifc": False,
            "render": False, "chat_intelligence": False,
        },
    }
    candidate["candidate_hash"] = design_03_semantic_hash(candidate)
    if canonical_derived_candidate_document(parent_candidate) != parent_document:
        raise RuntimeError("Design-02 parent mutated during Design-03 enrichment")
    if derived_candidate_semantic_hash(parent_candidate) != parent_hash:
        raise RuntimeError("Design-02 parent semantic hash changed during Design-03 enrichment")
    return candidate


__all__ = ["ENGINE_VERSION", "PHASE", "SCOPE", "enrich_opening_privacy_parcel_edge_intelligence_v1"]
