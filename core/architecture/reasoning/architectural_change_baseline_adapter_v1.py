"""Read-only bridge from an accepted architectural baseline to change inputs.

The canonical geometry kernel publishes its graphs inside ``boundary_extraction``
while the frozen change realizers consume the same graph contracts at candidate
root level.  This adapter only lifts those existing records into an immutable
change snapshot.  It does not create geometry, choose a strategy, or derive
execution evidence.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from core.architecture.reasoning.architectural_change_space_geometry_realizer_v1 import (
    candidate_semantic_hash,
)


ADAPTER_VERSION = "architectural_change_baseline_adapter_v1"
_GRAPH_KEYS = (
    "space_boundary_graphs",
    "wall_face_graphs",
    "wall_solid_graphs",
    "opening_host_graphs",
    "access_graph",
)


def _identity(candidate: Mapping[str, Any]) -> tuple[str | None, str | None]:
    identity = candidate.get("candidate_id") or candidate.get("id")
    version = candidate.get("candidate_version") or candidate.get("version")
    return (
        str(identity) if identity is not None else None,
        str(version) if version is not None else None,
    )


def _conflicting_aliases(candidate: Mapping[str, Any], first: str, second: str) -> bool:
    return (
        first in candidate
        and second in candidate
        and candidate[first] is not None
        and candidate[second] is not None
        and str(candidate[first]) != str(candidate[second])
    )


def _records(value: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(value, Mapping):
        return []
    records: list[dict[str, Any]] = []
    for floor in sorted(value, key=str):
        graph = value[floor]
        if not isinstance(graph, Mapping):
            continue
        raw = graph.get(key, ())
        if not isinstance(raw, (list, tuple)):
            continue
        records.extend(deepcopy(dict(item)) for item in raw if isinstance(item, Mapping))
    return records


def _verified_orientation(candidate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("site_orientation_evidence", "orientation_evidence"):
        evidence = candidate.get(key)
        if not isinstance(evidence, Mapping):
            continue
        status = str(evidence.get("status") or evidence.get("evidence_status") or "").upper()
        source = evidence.get("source") or evidence.get("provenance")
        if status in {"VERIFIED", "AUTHORITATIVE", "RESOLVED"} and source:
            return evidence
    return None


def _graph_available(root: Any, record_key: str) -> bool:
    return bool(_records(root, record_key))


def _failure_result(gaps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": ADAPTER_VERSION,
        "baseline_identity": None,
        "parent_candidate": None,
        "semantic_snapshot": None,
        "revision_paths": [],
        "readiness_gaps": gaps,
        "adapter_provenance": {
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01I",
            "baseline_mutated": False,
            "geometry_created": False,
            "strategy_selected": False,
            "execution_evidence_derived": False,
            "site_orientation_inferred": False,
        },
    }


def adapt_accepted_baseline_for_architectural_change(
    accepted_baseline: Mapping[str, Any],
) -> dict[str, Any]:
    """Return deterministic 01A-01H inputs without mutating the baseline.

    The input must already be an accepted candidate envelope with a stable
    identity, version, and stored semantic hash.  Missing or stale envelope
    evidence is returned as a structured blocker instead of being invented.
    """
    if not isinstance(accepted_baseline, Mapping):
        return _failure_result([{
            "classification": "BASELINE_CONTRACT_GAP",
            "code": "ACCEPTED_BASELINE_ENVELOPE_REQUIRED",
            "received_type": type(accepted_baseline).__name__,
        }])

    baseline_id, baseline_version = _identity(accepted_baseline)
    stored_hash = accepted_baseline.get("candidate_hash") or accepted_baseline.get("hash")
    try:
        actual_hash = candidate_semantic_hash(accepted_baseline)
    except (TypeError, ValueError):
        return _failure_result([{
            "classification": "BASELINE_CONTRACT_GAP",
            "code": "accepted_baseline_semantic_content_not_canonical_json",
        }])
    envelope_gaps: list[dict[str, Any]] = []
    for first, second, code in (
        ("candidate_id", "id", "accepted_baseline_identity_alias_conflict"),
        ("candidate_version", "version", "accepted_baseline_version_alias_conflict"),
        ("candidate_hash", "hash", "accepted_baseline_hash_alias_conflict"),
    ):
        if _conflicting_aliases(accepted_baseline, first, second):
            envelope_gaps.append({
                "classification": "BASELINE_CONTRACT_GAP",
                "code": code,
            })
    if baseline_id is None:
        envelope_gaps.append({
            "classification": "BASELINE_CONTRACT_GAP",
            "code": "ACCEPTED_BASELINE_ENVELOPE_REQUIRED",
            "missing_field": "candidate_id|id",
        })
    if baseline_version is None:
        envelope_gaps.append({
            "classification": "BASELINE_CONTRACT_GAP",
            "code": "ACCEPTED_BASELINE_ENVELOPE_REQUIRED",
            "missing_field": "candidate_version|version",
        })
    if stored_hash is None:
        envelope_gaps.append({
            "classification": "BASELINE_CONTRACT_GAP",
            "code": "ACCEPTED_BASELINE_ENVELOPE_REQUIRED",
            "missing_field": "candidate_hash|hash",
        })
    elif str(stored_hash) != actual_hash:
        envelope_gaps.append({
            "classification": "TRUE_BLOCKER",
            "code": "accepted_baseline_hash_mismatch",
            "stored_hash": str(stored_hash),
            "actual_hash": actual_hash,
        })
    if envelope_gaps:
        return _failure_result(envelope_gaps)

    extraction = accepted_baseline.get("boundary_extraction")
    extraction = extraction if isinstance(extraction, Mapping) else {}

    graph_conflicts = [
        key for key in _GRAPH_KEYS
        if isinstance(accepted_baseline.get(key), Mapping)
        and isinstance(extraction.get(key), Mapping)
        and accepted_baseline[key] != extraction[key]
    ]
    if graph_conflicts:
        return _failure_result([{
            "classification": "BASELINE_CONTRACT_GAP",
            "code": "ambiguous_root_and_boundary_extraction_graphs",
            "graph_keys": graph_conflicts,
        }])

    parent = deepcopy(dict(accepted_baseline))
    parent.pop("candidate_hash", None)
    parent.pop("hash", None)
    parent.pop("boundary_extraction", None)

    for key in _GRAPH_KEYS:
        source = accepted_baseline.get(key)
        if not isinstance(source, Mapping):
            source = extraction.get(key)
        if isinstance(source, Mapping):
            parent[key] = deepcopy(dict(source))

    source_metadata = {
        key: deepcopy(value)
        for key, value in extraction.items()
        if key not in _GRAPH_KEYS
    }
    if source_metadata:
        parent["baseline_source_provenance"] = source_metadata
    parent["baseline_lineage"] = {
        "accepted_baseline_candidate_id": baseline_id,
        "accepted_baseline_candidate_version": baseline_version,
        "accepted_baseline_hash": actual_hash,
        "adapter": ADAPTER_VERSION,
        "graph_records_copied_without_geometric_derivation": True,
    }
    parent["candidate_hash"] = candidate_semantic_hash(parent)

    spaces = _records(parent.get("space_boundary_graphs"), "spaces")
    openings = _records(parent.get("opening_host_graphs"), "openings")
    windows = [item for item in openings if str(item.get("kind", "")).upper() == "WINDOW"]
    access = parent.get("access_graph")
    relations = (
        deepcopy(list(access.get("edges", ())))
        if isinstance(access, Mapping) and isinstance(access.get("edges", ()), (list, tuple))
        else []
    )
    geometry_available = bool(spaces)
    access_status = str(access.get("status", "")).upper() if isinstance(access, Mapping) else ""
    access_available = (
        isinstance(access, Mapping)
        and isinstance(access.get("nodes"), (list, tuple))
        and isinstance(access.get("edges"), (list, tuple))
        and access_status in {"RESOLVED", "VERIFIED", "ACCEPTED"}
    )
    opening_available = isinstance(parent.get("opening_host_graphs"), Mapping)
    face_available = _graph_available(parent.get("wall_face_graphs"), "faces")
    solid_available = _graph_available(parent.get("wall_solid_graphs"), "solids")
    daylight_host_available = geometry_available and opening_available and face_available and solid_available
    orientation = _verified_orientation(parent)

    resolved_dependencies: list[str] = []
    if geometry_available:
        resolved_dependencies.append("geometry_availability")
    if geometry_available and access_available:
        resolved_dependencies.extend(("adjacency_availability", "topology_availability"))
    if daylight_host_available:
        resolved_dependencies.extend(("daylight_evidence_availability", "facade_evidence"))
    if orientation is not None:
        resolved_dependencies.append("site_orientation_evidence")

    snapshot: dict[str, Any] = {
        "schema_version": ADAPTER_VERSION,
        "baseline_identity": {
            "candidate_id": baseline_id,
            "candidate_version": baseline_version,
            "accepted_baseline_hash": actual_hash,
            "change_parent_hash": parent["candidate_hash"],
            "stored_hash_verified": True,
        },
        "spaces": spaces,
        "relations": relations,
        "openings": openings,
        "windows": windows,
        "private_circulation": [
            item for item in spaces
            if str(item.get("circulation_role", "")).upper() in {
                "PRIVATE_CIRCULATION", "PRIVATE_HALL_CORRIDOR",
            }
        ],
        "geometry_available": geometry_available,
        "adjacency_available": geometry_available and access_available,
        "topology_available": geometry_available and access_available,
        "daylight_evidence_available": daylight_host_available,
        "facade_evidence_available": daylight_host_available,
        "resolved_dependencies": sorted(set(resolved_dependencies)),
        "unresolved_dependencies": (
            [] if orientation is not None else ["site_orientation_evidence"]
        ),
        "evidence_status": "verified" if geometry_available and access_available else "partial",
        "validation_evidence": ["accepted_baseline_identity_version_hash_verified"] + (
            ["canonical_space_graph_records_preserved"] if geometry_available else []
        ) + (
            ["canonical_access_graph_records_preserved"] if access_available else []
        ),
        "hard_constraints": deepcopy(parent.get("hard_constraints", [])),
        "protected_constraints": deepcopy(parent.get("protected_constraints", [])),
        "protected_entities": deepcopy(parent.get("protected_entities", [])),
        "preservation_requirements": deepcopy(parent.get("preservation_requirements", [])),
    }
    if orientation is not None:
        snapshot["site_orientation"] = deepcopy(dict(orientation))
        snapshot["orientation"] = deepcopy(dict(orientation))

    revision_paths = [
        {
            "path": "SPACE_AREA_01F_A",
            "status": "READY_FOR_EXPLICIT_CALLER_EVIDENCE" if geometry_available else "BLOCKED_BASELINE_CONTRACT",
            "required_contracts": ["space_boundary_graphs", "access_graph", "constraints"],
        },
        {
            "path": "ADJACENCY_TOPOLOGY_01F_B",
            "status": "READY_FOR_EXPLICIT_CALLER_EVIDENCE" if geometry_available and access_available else "BLOCKED_BASELINE_CONTRACT",
            "required_contracts": ["space_boundary_graphs", "access_graph", "opening_host_graphs", "constraints"],
        },
        {
            "path": "OPENING_ACCESS_01F_C",
            "status": "READY_FOR_EXPLICIT_CALLER_EVIDENCE" if geometry_available and access_available and opening_available else "BLOCKED_BASELINE_CONTRACT",
            "required_contracts": ["space_boundary_graphs", "opening_host_graphs", "access_graph", "constraints"],
        },
        {
            "path": "DAYLIGHT_WINDOW_01H",
            "status": "READY_WITH_ORIENTATION_PENDING" if daylight_host_available and orientation is None else ("READY_FOR_EXPLICIT_CALLER_EVIDENCE" if daylight_host_available else "BLOCKED_BASELINE_CONTRACT"),
            "required_contracts": ["space_boundary_graphs", "wall_face_graphs", "wall_solid_graphs", "opening_host_graphs", "privacy_constraints"],
        },
        {
            "path": "MULTI_STEP_01F_D",
            "status": "READY_FOR_EXPLICIT_CALLER_EVIDENCE" if geometry_available and access_available and opening_available else "BLOCKED_BASELINE_CONTRACT",
            "required_contracts": ["01F_A", "01F_B", "01F_C", "explicit_dependency_order"],
        },
    ]

    gaps = [
        {
            "classification": "EXPECTED_CALLER_EVIDENCE",
            "code": "explicit_strategy_selection_required",
        },
        {
            "classification": "EXPECTED_CALLER_EVIDENCE",
            "code": "realizer_specific_execution_binding_required",
        },
    ]
    if orientation is None:
        gaps.append({
            "classification": "EXPECTED_CALLER_EVIDENCE",
            "code": "verified_site_orientation_required_for_orientation_dependent_daylight",
        })
    missing_graphs = [
        key for key in _GRAPH_KEYS
        if not isinstance(parent.get(key), Mapping)
    ]
    for key in missing_graphs:
        gaps.append({
            "classification": "BASELINE_CONTRACT_GAP",
            "code": f"canonical_graph_missing:{key}",
        })
    if isinstance(access, Mapping) and not access_available:
        gaps.append({
            "classification": "BASELINE_CONTRACT_GAP",
            "code": "canonical_access_graph_not_verified_resolved",
        })

    return {
        "schema_version": ADAPTER_VERSION,
        "baseline_identity": deepcopy(snapshot["baseline_identity"]),
        "parent_candidate": parent,
        "semantic_snapshot": snapshot,
        "revision_paths": revision_paths,
        "readiness_gaps": gaps,
        "adapter_provenance": {
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01I",
            "baseline_mutated": False,
            "geometry_created": False,
            "strategy_selected": False,
            "execution_evidence_derived": False,
            "site_orientation_inferred": False,
        },
    }


__all__ = ["ADAPTER_VERSION", "adapt_accepted_baseline_for_architectural_change"]
