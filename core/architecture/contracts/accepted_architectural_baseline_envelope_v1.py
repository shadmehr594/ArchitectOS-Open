"""Canonical acceptance contract for an architecture-only baseline.

The accepted envelope binds the existing space-boundary pipeline result to an
explicit candidate identity and version.  It does not derive geometry or fill
missing evidence.  ``candidate_hash`` is the stored SHA-256 of the complete
deterministic envelope document, excluding only the hash aliases themselves.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any


CONTRACT = "AcceptedArchitecturalBaselineEnvelopeV1"
VERSION = "1.0"
ACCEPTANCE_BOUNDARY = "ArchitecturalSpaceBoundaryPipelineV1.accept_resolved_baseline"
GRAPH_KEYS = (
    "wall_face_graphs",
    "wall_solid_graphs",
    "opening_host_graphs",
    "space_boundary_graphs",
    "access_graph",
)


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def canonical_accepted_baseline_document(value: Mapping[str, Any]) -> str:
    """Serialize accepted semantic content with one stable JSON policy.

    Keys are sorted, separators are compact, Unicode is retained, tuples are
    normalized to arrays, and ``candidate_hash``/``hash`` are excluded so the
    digest never recursively covers itself.  No timestamp or runtime/cache
    field is introduced by this contract.
    """
    if not isinstance(value, Mapping):
        raise ValueError("accepted baseline envelope must be a mapping")
    payload = deepcopy(dict(value))
    payload.pop("candidate_hash", None)
    payload.pop("hash", None)
    return json.dumps(
        _json_value(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def accepted_baseline_semantic_hash(value: Mapping[str, Any]) -> str:
    """Return the canonical accepted-baseline semantic SHA-256."""
    document = canonical_accepted_baseline_document(value)
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def verify_accepted_baseline_envelope(value: Mapping[str, Any]) -> bool:
    """Verify contract identity, acceptance state, and stored semantic hash."""
    if not isinstance(value, Mapping):
        return False
    if value.get("contract") != CONTRACT or str(value.get("contract_version")) != VERSION:
        return False
    if value.get("acceptance_status") != "ACCEPTED_FROZEN":
        return False
    stored = value.get("candidate_hash")
    return isinstance(stored, str) and stored == accepted_baseline_semantic_hash(value)


def _floor_records(root: Any, record_key: str) -> list[Mapping[str, Any]]:
    if not isinstance(root, Mapping):
        return []
    records: list[Mapping[str, Any]] = []
    for floor in sorted(root, key=str):
        graph = root[floor]
        if not isinstance(graph, Mapping):
            continue
        values = graph.get(record_key)
        if isinstance(values, (list, tuple)):
            records.extend(item for item in values if isinstance(item, Mapping))
    return records


def _record_ids(records: list[Mapping[str, Any]], keys: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for record in records:
        identity = next((record.get(key) for key in keys if record.get(key) is not None), None)
        if identity is not None:
            values.append(str(identity))
    return sorted(set(values))


def _semantic_reference_snapshot(
    extraction: Mapping[str, Any],
    resolved_baseline: Mapping[str, Any],
) -> dict[str, Any]:
    spaces = _floor_records(extraction.get("space_boundary_graphs"), "spaces")
    openings = _floor_records(extraction.get("opening_host_graphs"), "openings")
    access = extraction.get("access_graph")
    edges = access.get("edges", []) if isinstance(access, Mapping) else []
    edges = [item for item in edges if isinstance(item, Mapping)] if isinstance(edges, (list, tuple)) else []

    graph_availability: dict[str, Any] = {}
    unresolved: list[dict[str, Any]] = []
    for key in GRAPH_KEYS:
        present = isinstance(extraction.get(key), Mapping)
        graph_availability[key] = {
            "status": "PRESENT" if present else "MISSING",
            "canonical_path": f"boundary_extraction.{key}",
        }
        if not present:
            unresolved.append({
                "classification": "MISSING_CANONICAL_EVIDENCE",
                "code": f"canonical_graph_missing:{key}",
            })

    source_unresolved = extraction.get("unresolved")
    if isinstance(source_unresolved, (list, tuple)):
        unresolved.extend(deepcopy(item) for item in source_unresolved if isinstance(item, Mapping))

    opening_ids = _record_ids(openings, ("opening_id", "id"))
    door_ids = _record_ids(
        [item for item in openings if str(item.get("kind", "")).upper() == "DOOR"],
        ("opening_id", "id"),
    )
    window_ids = _record_ids(
        [item for item in openings if str(item.get("kind", "")).upper() == "WINDOW"],
        ("opening_id", "id"),
    )
    relation_ids = _record_ids(edges, ("edge_id", "id"))

    return {
        "contract": "AcceptedArchitecturalBaselineSemanticSnapshotV1",
        "evidence_policy": "CANONICAL_EXISTING_EVIDENCE_ONLY",
        "canonical_record_references": {
            "spaces": {
                "canonical_path": "boundary_extraction.space_boundary_graphs[*].spaces",
                "record_ids": _record_ids(spaces, ("space_id", "id")),
            },
            "relations": {
                "canonical_path": "boundary_extraction.access_graph.edges",
                "record_ids": relation_ids,
            },
            "openings": {
                "canonical_path": "boundary_extraction.opening_host_graphs[*].openings",
                "record_ids": opening_ids,
            },
            "doors": {
                "canonical_path": "boundary_extraction.opening_host_graphs[*].openings",
                "record_ids": door_ids,
            },
            "windows": {
                "canonical_path": "boundary_extraction.opening_host_graphs[*].openings",
                "record_ids": window_ids,
            },
            "circulation": {
                "canonical_path": "boundary_extraction.access_graph",
                "record_ids": relation_ids,
            },
        },
        "constraint_references": {
            "constraints": "hard_constraints",
            "protected_constraints": "protected_constraints",
            "protected_entities": "protected_entities",
        },
        "graph_availability": graph_availability,
        "access_evidence_status": (
            str(access.get("status")) if isinstance(access, Mapping) and access.get("status") is not None else "MISSING"
        ),
        "unresolved_evidence": unresolved,
        "geometry_derived": False,
        "relationships_inferred": False,
        "site_orientation_inferred": False,
        "execution_bindings_added": False,
    }


def build_accepted_architectural_baseline_envelope(
    resolved_baseline: Mapping[str, Any],
    *,
    candidate_id: str,
    candidate_version: str,
    acceptance_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Freeze a resolved architecture-only pipeline result as an envelope.

    Identity/version and acceptance provenance must be supplied at the
    acceptance boundary.  Missing graph families remain explicit gaps.
    """
    if not isinstance(resolved_baseline, Mapping):
        raise ValueError("resolved_baseline must be a mapping")
    if resolved_baseline.get("architecture_only") is not True:
        raise ValueError("architecture-only resolved baseline is required")
    if not isinstance(resolved_baseline.get("boundary_extraction"), Mapping):
        raise ValueError("canonical boundary_extraction is required")
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ValueError("explicit candidate_id is required at acceptance")
    if not isinstance(candidate_version, str) or not candidate_version.strip():
        raise ValueError("explicit candidate_version is required at acceptance")
    if not isinstance(acceptance_provenance, Mapping) or not acceptance_provenance:
        raise ValueError("evidence-bearing acceptance_provenance is required")
    decision = acceptance_provenance.get("status") or acceptance_provenance.get("decision")
    if str(decision).upper() not in {"ACCEPTED", "FROZEN", "ACCEPTED_FROZEN"}:
        raise ValueError("acceptance_provenance must contain an explicit accepted/frozen decision")
    source_candidate_id = resolved_baseline.get("candidate_id")
    source_candidate_version = resolved_baseline.get("candidate_version")
    if source_candidate_id is not None and str(source_candidate_id) != candidate_id.strip():
        raise ValueError("candidate_id must preserve the existing source candidate identity")
    if source_candidate_version is not None and str(source_candidate_version) != candidate_version.strip():
        raise ValueError("candidate_version must preserve the existing source candidate version")

    extraction = deepcopy(dict(resolved_baseline["boundary_extraction"]))
    source_id = source_candidate_id or candidate_id
    source_version = source_candidate_version or candidate_version
    semantic_snapshot = _semantic_reference_snapshot(extraction, resolved_baseline)
    envelope: dict[str, Any] = {
        "contract": CONTRACT,
        # ``version`` is intentionally not used here: frozen 01I treats that
        # key as the candidate-version alias.  The contract version is kept
        # distinct so both version domains remain unambiguous.
        "contract_version": VERSION,
        "candidate_id": candidate_id.strip(),
        "candidate_version": candidate_version.strip(),
        "source_candidate_id": str(source_id),
        "source_candidate_version": str(source_version),
        "acceptance_status": "ACCEPTED_FROZEN",
        "acceptance_provenance": deepcopy(dict(acceptance_provenance)),
        "acceptance_boundary": ACCEPTANCE_BOUNDARY,
        "source_pipeline": {
            "name": "ArchitecturalSpaceBoundaryPipelineV1",
            "version": deepcopy(resolved_baseline.get("version")),
            "pipeline": deepcopy(resolved_baseline.get("pipeline")),
        },
        "boundary_extraction": extraction,
        "semantic_regions": deepcopy(resolved_baseline.get("semantic_regions", [])),
        "semantic_snapshot": semantic_snapshot,
        "hard_constraints": deepcopy(resolved_baseline.get("constraints", [])),
        "protected_constraints": deepcopy(resolved_baseline.get("protected_constraints", [])),
        "protected_entities": deepcopy(resolved_baseline.get("protected_entities", [])),
        "preservation_requirements": deepcopy(resolved_baseline.get("preservation_requirements", [])),
        "lineage": {
            "source_candidate_id": str(source_id),
            "source_candidate_version": str(source_version),
            "accepted_candidate_id": candidate_id.strip(),
            "accepted_candidate_version": candidate_version.strip(),
            "derived_from_accepted_parent": False,
        },
        "immutability": {
            "accepted_content": "FROZEN",
            "in_place_revision_allowed": False,
            "later_changes_require_derived_candidate": True,
            "downstream_access": "READ_ONLY",
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
    envelope["candidate_hash"] = accepted_baseline_semantic_hash(envelope)
    return envelope


__all__ = [
    "ACCEPTANCE_BOUNDARY",
    "CONTRACT",
    "GRAPH_KEYS",
    "VERSION",
    "accepted_baseline_semantic_hash",
    "build_accepted_architectural_baseline_envelope",
    "canonical_accepted_baseline_document",
    "verify_accepted_baseline_envelope",
]
