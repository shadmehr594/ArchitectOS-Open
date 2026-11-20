"""Evidence-bound, semantic/reference-only baseline refinement for Design-02."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
from typing import Any

from core.architecture.contracts.accepted_architectural_baseline_envelope_v1 import (
    GRAPH_KEYS,
    accepted_baseline_semantic_hash,
    canonical_accepted_baseline_document,
    verify_accepted_baseline_envelope,
)
from core.architecture.contracts.derived_architectural_candidate_v1 import (
    CONTRACT,
    DERIVATION_STATUS,
    VERSION,
    derived_candidate_semantic_hash,
)
from core.architecture.reasoning.architectural_change_baseline_adapter_v1 import (
    adapt_accepted_baseline_for_architectural_change,
)


REFINER_VERSION = "architectural_baseline_derived_candidate_refinement_v1"
PHASE = "ARCHITECTURAL-BASELINE-DESIGN-02"
SCOPE = "EVIDENCE_BOUND_SEMANTIC_AND_REFERENCE_REFINEMENT"
_LABEL_FIELDS = ("semantic_class", "semantic_role", "circulation_role", "label")


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _records_by_floor(root: Any, record_key: str) -> list[tuple[str, dict[str, Any]]]:
    records: list[tuple[str, dict[str, Any]]] = []
    if not isinstance(root, Mapping):
        return records
    for floor in sorted(root, key=str):
        graph = root[floor]
        if not isinstance(graph, Mapping):
            continue
        raw = graph.get(record_key, ())
        if isinstance(raw, (list, tuple)):
            records.extend(
                (str(floor), deepcopy(dict(item)))
                for item in raw
                if isinstance(item, Mapping)
            )
    return records


def _identity(record: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    value = next((record.get(key) for key in keys if record.get(key) is not None), None)
    return str(value) if value is not None else None


def _normalize_label(value: str) -> str:
    return "_".join(value.strip().upper().replace("-", " ").split())


def _graph_reference(key: str, graph: Mapping[str, Any]) -> dict[str, Any]:
    ids: set[str] = set()
    identity_keys = {
        "wall_face_graphs": ("face_id", "id"),
        "wall_solid_graphs": ("wall_solid_id", "envelope_id", "id"),
        "opening_host_graphs": ("opening_id", "id"),
        "space_boundary_graphs": ("space_id", "id"),
    }
    record_keys = {
        "wall_face_graphs": ("faces",),
        "wall_solid_graphs": ("solids", "floor_envelopes"),
        "opening_host_graphs": ("openings",),
        "space_boundary_graphs": ("spaces",),
    }
    if key == "access_graph":
        for record_key in ("nodes", "edges"):
            raw = graph.get(record_key, ())
            if isinstance(raw, (list, tuple)):
                for record in raw:
                    if isinstance(record, Mapping):
                        identity = _identity(record, ("edge_id", "node_id", "id"))
                        if identity:
                            ids.add(identity)
    else:
        for record_key in record_keys.get(key, ()):
            for _, record in _records_by_floor(graph, record_key):
                identity = _identity(record, identity_keys[key])
                if identity:
                    ids.add(identity)
    digest = hashlib.sha256(_stable_json(graph).encode("utf-8")).hexdigest()
    return {
        "canonical_path": f"boundary_extraction.{key}",
        "content_sha256": digest,
        "record_ids": sorted(ids),
        "preservation": "EXACT_ACCEPTED_CONTENT",
    }


def _evidence(
    canonical_path: str,
    source_record_ids: Sequence[str],
    *,
    confidence: str = "DIRECT_CANONICAL_RECORD",
) -> dict[str, Any]:
    return {
        "canonical_path": canonical_path,
        "source_record_ids": sorted({str(item) for item in source_record_ids}),
        "confidence": confidence,
        "provenance": "ACCEPTED_BASELINE_CANONICAL_EVIDENCE",
    }


def _pending_opportunity(opportunity_type: str, code: str) -> dict[str, Any]:
    return {
        "contract": "ArchitecturalRefinementOpportunityV1",
        "opportunity_type": opportunity_type,
        "status": "PENDING_EVIDENCE",
        "code": code,
        "geometry_change_allowed": False,
    }


def _catalog(extraction: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    spaces = _records_by_floor(extraction.get("space_boundary_graphs"), "spaces")
    openings = _records_by_floor(extraction.get("opening_host_graphs"), "openings")
    access = extraction.get("access_graph")
    nodes = access.get("nodes", ()) if isinstance(access, Mapping) else ()
    edges = access.get("edges", ()) if isinstance(access, Mapping) else ()
    nodes = [deepcopy(dict(item)) for item in nodes if isinstance(item, Mapping)] if isinstance(nodes, (list, tuple)) else []
    edges = [deepcopy(dict(item)) for item in edges if isinstance(item, Mapping)] if isinstance(edges, (list, tuple)) else []

    space_index = {
        identity: {"floor": floor, "record": record}
        for floor, record in spaces
        if (identity := _identity(record, ("space_id", "id")))
    }
    opening_index = {
        identity: {"floor": floor, "record": record}
        for floor, record in openings
        if (identity := _identity(record, ("opening_id", "id")))
    }
    node_index = {
        identity: record
        for record in nodes
        if (identity := _identity(record, ("node_id", "id")))
    }
    edge_index = {
        identity: record
        for record in edges
        if (identity := _identity(record, ("edge_id", "id")))
    }

    opportunities: list[dict[str, Any]] = []
    for identity, item in sorted(space_index.items()):
        record = item["record"]
        for field in _LABEL_FIELDS:
            value = record.get(field)
            if isinstance(value, str) and value and value != _normalize_label(value):
                opportunities.append({
                    "contract": "ArchitecturalRefinementOpportunityV1",
                    "opportunity_type": "SEMANTIC_LABEL_NORMALIZATION",
                    "status": "READY",
                    "target_kind": "space",
                    "target_id": identity,
                    "field": field,
                    "normalized_value": _normalize_label(value),
                    "source_evidence": _evidence(
                        f"boundary_extraction.space_boundary_graphs.{item['floor']}.spaces",
                        [identity],
                    ),
                    "changes": "SEMANTICS_ONLY",
                })
    for identity, edge in sorted(edge_index.items()):
        source = str(edge.get("from")) if edge.get("from") is not None else None
        target = str(edge.get("to")) if edge.get("to") is not None else None
        if source and target and source in node_index and target in node_index:
            opportunities.append({
                "contract": "ArchitecturalRefinementOpportunityV1",
                "opportunity_type": "PROVEN_RELATION_BINDING",
                "status": "READY",
                "target_kind": "access_relation",
                "target_id": identity,
                "source_evidence": _evidence(
                    "boundary_extraction.access_graph.edges",
                    [identity, source, target],
                ),
                "changes": "REFERENCES_ONLY",
            })
    for identity, item in sorted(opening_index.items()):
        record = item["record"]
        host_ids = [
            str(record[key]) for key in (
                "host_wall_solid_id", "host_wall_pair_id", "host_face_a", "host_face_b"
            ) if record.get(key) is not None
        ]
        if str(record.get("status", "")).upper() in {"RESOLVED", "VERIFIED", "ACCEPTED"} and host_ids:
            opportunities.append({
                "contract": "ArchitecturalRefinementOpportunityV1",
                "opportunity_type": "OPENING_HOST_REFERENCE_REPAIR",
                "status": "READY",
                "target_kind": "opening",
                "target_id": identity,
                "source_evidence": _evidence(
                    f"boundary_extraction.opening_host_graphs.{item['floor']}.openings",
                    [identity, *host_ids],
                ),
                "changes": "REFERENCES_ONLY",
            })

    opportunities.extend((
        _pending_opportunity("PRIVACY_ANALYSIS_PENDING", "privacy_evidence_not_resolved_in_design_02"),
        _pending_opportunity("PARCEL_EDGE_ANALYSIS_PENDING", "parcel_edge_and_site_orientation_not_resolved_in_design_02"),
        _pending_opportunity("FLOOR_ROOF_REFINEMENT_PENDING", "floor_roof_domain_out_of_scope_design_02"),
    ))
    return {
        "spaces": space_index,
        "openings": opening_index,
        "nodes": node_index,
        "edges": edge_index,
    }, opportunities


def _apply_request(
    request: Mapping[str, Any],
    catalog: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    refinement_id = str(request.get("refinement_id") or "")
    operation = str(request.get("opportunity_type") or "")
    if not refinement_id:
        return None, {"code": "refinement_id_required", "request": deepcopy(dict(request))}

    if operation == "SEMANTIC_LABEL_NORMALIZATION":
        target_id = str(request.get("target_id") or "")
        field = str(request.get("field") or "")
        item = catalog["spaces"].get(target_id)
        if item is None or field not in _LABEL_FIELDS:
            return None, {"refinement_id": refinement_id, "code": "canonical_semantic_source_not_found"}
        source_value = item["record"].get(field)
        if not isinstance(source_value, str) or not source_value:
            return None, {"refinement_id": refinement_id, "code": "semantic_label_evidence_missing"}
        normalized = _normalize_label(source_value)
        requested = request.get("normalized_value", normalized)
        if requested != normalized:
            return None, {"refinement_id": refinement_id, "code": "requested_label_not_proven_by_normalization"}
        return {
            "refinement_id": refinement_id,
            "opportunity_type": operation,
            "target_kind": "space",
            "target_id": target_id,
            "field": field,
            "source_value": source_value,
            "normalized_value": normalized,
            "change_class": "SEMANTICS_ONLY",
            "source_evidence": _evidence(
                f"boundary_extraction.space_boundary_graphs.{item['floor']}.spaces",
                [target_id],
            ),
        }, None

    if operation == "PROVEN_RELATION_BINDING":
        target_id = str(request.get("target_id") or "")
        edge = catalog["edges"].get(target_id)
        source = str(edge.get("from")) if isinstance(edge, Mapping) and edge.get("from") is not None else None
        target = str(edge.get("to")) if isinstance(edge, Mapping) and edge.get("to") is not None else None
        if not source or not target or source not in catalog["nodes"] or target not in catalog["nodes"]:
            return None, {"refinement_id": refinement_id, "code": "canonical_relation_evidence_incomplete"}
        return {
            "refinement_id": refinement_id,
            "opportunity_type": operation,
            "target_kind": "access_relation",
            "target_id": target_id,
            "bound_endpoint_ids": [source, target],
            "change_class": "REFERENCES_ONLY",
            "source_evidence": _evidence(
                "boundary_extraction.access_graph.edges",
                [target_id, source, target],
            ),
        }, None

    if operation == "OPENING_HOST_REFERENCE_REPAIR":
        target_id = str(request.get("target_id") or "")
        item = catalog["openings"].get(target_id)
        record = item["record"] if item else {}
        host_ids = [
            str(record[key]) for key in (
                "host_wall_solid_id", "host_wall_pair_id", "host_face_a", "host_face_b"
            ) if record.get(key) is not None
        ]
        if not item or not host_ids or str(record.get("status", "")).upper() not in {"RESOLVED", "VERIFIED", "ACCEPTED"}:
            return None, {"refinement_id": refinement_id, "code": "proven_opening_host_evidence_missing"}
        return {
            "refinement_id": refinement_id,
            "opportunity_type": operation,
            "target_kind": "opening",
            "target_id": target_id,
            "bound_host_ids": sorted(set(host_ids)),
            "change_class": "REFERENCES_ONLY",
            "source_evidence": _evidence(
                f"boundary_extraction.opening_host_graphs.{item['floor']}.openings",
                [target_id, *host_ids],
            ),
        }, None

    return None, {"refinement_id": refinement_id, "code": "unsupported_or_out_of_scope_refinement"}


def derive_architectural_candidate_v1(
    accepted_baseline: Mapping[str, Any],
    *,
    refinement_requests: Sequence[Mapping[str, Any]] = (),
    derivation_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Create one immutable-parent Design-02 candidate.

    Invalid or under-evidenced refinement requests become structured rejections
    and readiness gaps.  A stale/non-canonical accepted parent is rejected
    before any candidate is created.
    """
    if not verify_accepted_baseline_envelope(accepted_baseline):
        raise ValueError("valid non-stale AcceptedArchitecturalBaselineEnvelopeV1 required")
    if not isinstance(derivation_provenance, Mapping) or not derivation_provenance:
        raise ValueError("evidence-bearing derivation_provenance is required")
    if not isinstance(refinement_requests, Sequence) or isinstance(refinement_requests, (str, bytes)):
        raise ValueError("refinement_requests must be a sequence of mappings")

    parent_document = canonical_accepted_baseline_document(accepted_baseline)
    parent_hash = accepted_baseline_semantic_hash(accepted_baseline)
    adapter = adapt_accepted_baseline_for_architectural_change(accepted_baseline)
    if adapter.get("parent_candidate") is None:
        raise ValueError("frozen 01I adapter rejected the accepted baseline")

    extraction = accepted_baseline.get("boundary_extraction")
    if not isinstance(extraction, Mapping):
        raise ValueError("accepted baseline canonical boundary_extraction required")
    catalog, opportunities = _catalog(extraction)

    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    ordered_requests = sorted(
        (deepcopy(dict(item)) for item in refinement_requests if isinstance(item, Mapping)),
        key=_stable_json,
    )
    if len(ordered_requests) != len(refinement_requests):
        raise ValueError("every refinement request must be a mapping")
    for request in ordered_requests:
        request_id = str(request.get("refinement_id") or "")
        if request_id and request_id in seen_ids:
            rejected.append({"refinement_id": request_id, "code": "duplicate_refinement_id"})
            continue
        if request_id:
            seen_ids.add(request_id)
        accepted, failure = _apply_request(request, catalog)
        if accepted is not None:
            applied.append(accepted)
        if failure is not None:
            rejected.append(failure)

    unresolved = [
        {
            "classification": "READINESS_GAP",
            "code": item["code"],
            "refinement_id": item.get("refinement_id"),
            "resolution": "SUPPLY_CANONICAL_ACCEPTED_BASELINE_EVIDENCE",
        }
        for item in rejected
    ]
    unresolved.extend((
        {
            "classification": "NEXT_DOMAIN_EVIDENCE_REQUIRED",
            "code": "privacy_evidence_unresolved",
            "inference_performed": False,
        },
        {
            "classification": "NEXT_DOMAIN_EVIDENCE_REQUIRED",
            "code": "parcel_edge_and_site_orientation_evidence_unresolved",
            "inference_performed": False,
        },
    ))

    request_fingerprint_payload = {
        "parent_baseline_id": accepted_baseline["candidate_id"],
        "parent_baseline_version": accepted_baseline["candidate_version"],
        "parent_baseline_hash": parent_hash,
        "scope": SCOPE,
        "requests": ordered_requests,
    }
    refinement_fingerprint = hashlib.sha256(
        _stable_json(request_fingerprint_payload).encode("utf-8")
    ).hexdigest()
    suffix = refinement_fingerprint[:16]

    graph_references = {
        key: _graph_reference(key, extraction[key])
        for key in GRAPH_KEYS
        if isinstance(extraction.get(key), Mapping)
    }
    semantic_overrides = {
        (item["target_id"], item["field"]): item["normalized_value"]
        for item in applied
        if item["opportunity_type"] == "SEMANTIC_LABEL_NORMALIZATION"
    }
    spaces = []
    for identity, item in sorted(catalog["spaces"].items()):
        source_labels = {
            key: item["record"][key]
            for key in _LABEL_FIELDS
            if item["record"].get(key) is not None
        }
        effective_labels = {
            key: semantic_overrides.get((identity, key), value)
            for key, value in source_labels.items()
        }
        spaces.append({
            "space_id": identity,
            "floor": item["floor"],
            "semantic_labels": effective_labels,
            "source_semantic_labels": source_labels,
            "canonical_path": f"boundary_extraction.space_boundary_graphs.{item['floor']}.spaces",
            "geometry_copied": False,
        })
    openings = [
        {
            "opening_id": identity,
            "floor": item["floor"],
            "kind": item["record"].get("kind"),
            "status": item["record"].get("status"),
            "side_a": item["record"].get("side_a"),
            "side_b": item["record"].get("side_b"),
            "canonical_path": f"boundary_extraction.opening_host_graphs.{item['floor']}.openings",
        }
        for identity, item in sorted(catalog["openings"].items())
    ]
    relations = [
        {
            "relation_id": identity,
            "from": record.get("from"),
            "to": record.get("to"),
            "kind": record.get("kind"),
            "canonical_path": "boundary_extraction.access_graph.edges",
        }
        for identity, record in sorted(catalog["edges"].items())
    ]

    verified_exterior_boundaries: list[dict[str, Any]] = []
    for identity, item in sorted(catalog["spaces"].items()):
        explicit = item["record"].get("exterior_boundary_ids")
        if isinstance(explicit, (list, tuple)) and explicit:
            verified_exterior_boundaries.append({
                "space_id": identity,
                "boundary_ids": sorted({str(value) for value in explicit}),
                "evidence": _evidence(
                    f"boundary_extraction.space_boundary_graphs.{item['floor']}.spaces",
                    [identity, *[str(value) for value in explicit]],
                ),
            })
    verified_openings = [
        item["opening_id"] for item in openings
        if str(item.get("status", "")).upper() in {"RESOLVED", "VERIFIED", "ACCEPTED"}
    ]
    verified_window_hosts = [
        identity for identity, item in sorted(catalog["openings"].items())
        if str(item["record"].get("kind", "")).upper() == "WINDOW"
        and str(item["record"].get("status", "")).upper() in {"RESOLVED", "VERIFIED", "ACCEPTED"}
        and any(item["record"].get(key) is not None for key in (
            "host_wall_solid_id", "host_wall_pair_id", "host_face_a", "host_face_b"
        ))
    ]

    candidate: dict[str, Any] = {
        "contract": CONTRACT,
        "contract_version": VERSION,
        "candidate_id": f"{accepted_baseline['candidate_id']}::DESIGN-02::{suffix}",
        "candidate_version": f"{accepted_baseline['candidate_version']}+design-02.{suffix}",
        "parent_baseline_id": accepted_baseline["candidate_id"],
        "parent_baseline_version": accepted_baseline["candidate_version"],
        "parent_baseline_hash": parent_hash,
        "derivation_status": DERIVATION_STATUS,
        "refinement_scope": SCOPE,
        "boundary_extraction": deepcopy(dict(extraction)),
        "canonical_graph_references": graph_references,
        "semantic_state": {
            "spaces": spaces,
            "relation_bindings": [
                deepcopy(item) for item in applied
                if item["opportunity_type"] == "PROVEN_RELATION_BINDING"
            ],
            "opening_host_bindings": [
                deepcopy(item) for item in applied
                if item["opportunity_type"] == "OPENING_HOST_REFERENCE_REPAIR"
            ],
        },
        "opening_references": openings,
        "access_references": relations,
        "constraints": {
            "hard_constraints": deepcopy(accepted_baseline.get("hard_constraints", [])),
            "protected_constraints": deepcopy(accepted_baseline.get("protected_constraints", [])),
            "protected_entities": deepcopy(accepted_baseline.get("protected_entities", [])),
            "preservation_requirements": deepcopy(accepted_baseline.get("preservation_requirements", [])),
        },
        "unresolved_evidence": unresolved,
        "applied_refinements": applied,
        "rejected_refinements": rejected,
        "required_rechecks": [
            "VERIFY_PARENT_HASH_BEFORE_FURTHER_DERIVATION",
            "RECHECK_PROTECTED_ENTITIES_BEFORE_GEOMETRIC_CHANGE",
            "RESOLVE_PRIVACY_EVIDENCE_IN_DESIGN_03",
            "RESOLVE_PARCEL_EDGE_SITE_EVIDENCE_IN_DESIGN_03",
        ],
        "refinement_opportunities": opportunities,
        "design_03_readiness": {
            "verified_exterior_boundaries": verified_exterior_boundaries,
            "verified_openings": verified_openings,
            "verified_window_hosts": verified_window_hosts,
            "protected_entities": deepcopy(accepted_baseline.get("protected_entities", [])),
            "privacy_evidence": "UNRESOLVED_NO_INFERENCE",
            "parcel_edge_site_evidence": "UNRESOLVED_NO_INFERENCE",
        },
        "lineage": {
            "parent_baseline_id": accepted_baseline["candidate_id"],
            "parent_baseline_version": accepted_baseline["candidate_version"],
            "parent_baseline_hash": parent_hash,
            "parent_contract": accepted_baseline["contract"],
            "parent_acceptance_status": accepted_baseline["acceptance_status"],
            "derived_from_accepted_parent": True,
            "accepted_parent_mutated": False,
            "refinement_fingerprint": refinement_fingerprint,
        },
        "provenance": {
            "phase": PHASE,
            "refiner": REFINER_VERSION,
            "derivation": deepcopy(dict(derivation_provenance)),
            "evidence_policy": "CANONICAL_ACCEPTED_BASELINE_EVIDENCE_ONLY",
            "frozen_01i_adapter": {
                "schema_version": adapter["schema_version"],
                "baseline_identity": deepcopy(adapter["baseline_identity"]),
                "revision_paths": deepcopy(adapter["revision_paths"]),
                "readiness_gaps": deepcopy(adapter["readiness_gaps"]),
                "usage": "READ_ONLY_COMPATIBILITY_AND_READINESS",
            },
            "geometry_created": False,
            "geometry_modified": False,
            "relationships_inferred": False,
            "site_orientation_inferred": False,
        },
        "immutability": {
            "accepted_parent": "READ_ONLY",
            "canonical_geometry": "PRESERVED_EXACTLY",
            "in_place_revision_allowed": False,
            "future_changes_require_new_derived_candidate": True,
        },
        "architecture_only": True,
        "side_effects": {
            "site": False,
            "structure": False,
            "bim": False,
            "ifc": False,
            "render": False,
            "chat_intelligence": False,
        },
    }
    candidate["candidate_hash"] = derived_candidate_semantic_hash(candidate)

    if canonical_accepted_baseline_document(accepted_baseline) != parent_document:
        raise RuntimeError("accepted baseline mutated during derived refinement")
    if accepted_baseline_semantic_hash(accepted_baseline) != parent_hash:
        raise RuntimeError("accepted baseline semantic hash changed during derived refinement")
    return candidate


__all__ = [
    "PHASE",
    "REFINER_VERSION",
    "SCOPE",
    "derive_architectural_candidate_v1",
]
