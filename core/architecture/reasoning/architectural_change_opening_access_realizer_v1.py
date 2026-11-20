"""Transactional 01F-C opening/access-interface realization.

This module edits only the canonical opening-host and semantic access graphs of
a deep-cloned candidate.  It creates no BIM door, leaf, frame, swing, window,
site, structure, render, or generator object.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from math import hypot
from typing import Any, Mapping

from shapely.geometry import LineString, Polygon

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeStrategy,
    ExecutionReadinessResult,
    OPENING_ACCESS_REALIZATION_STATUS_FAILED,
    OPENING_ACCESS_REALIZATION_STATUS_REALIZED,
    OPENING_ACCESS_REALIZATION_STATUS_REALIZED_WITH_WARNINGS,
    OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS,
    OPENING_ACCESS_REALIZATION_STATUS_REJECTED_CONSTRAINT,
    OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
    OPENING_ACCESS_REALIZATION_STATUS_STALE_PARENT,
    OPENING_ACCESS_REALIZATION_STATUS_UNSUPPORTED_STRATEGY,
    OpeningAccessDelta,
    OpeningAccessRealizationResult,
    READINESS_STATUS_READY,
    READINESS_STATUS_READY_WITH_PREREQUISITES,
)
from core.architecture.reasoning.architectural_change_space_geometry_realizer_v1 import (
    candidate_semantic_hash,
)


REALIZER_VERSION = "architectural_change_opening_access_realizer_v1"
SUPPORTED_EXECUTION_FAMILY = "OPENING_ACCESS_REALIZATION"
SUPPORTED_OPERATIONS = frozenset({
    "CREATE_DIRECT_ACCESS_INTERFACE",
    "REBIND_EXISTING_PORTAL",
    "RELOCATE_ACCESS_INTERFACE",
})
SUPPORTED_STRATEGY_TYPES = frozenset({
    "CREATE_DIRECT_ACCESS_INTERFACE",
    "REBIND_EXISTING_PORTAL",
    "RELOCATE_ACCESS_INTERFACE",
    "PRIVATE_ACCESS_REALIZATION",
    "DIRECT_PRIVATE_RELATIONSHIP",
})
_EPSILON = 1e-7


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _canonical_document(value: Mapping[str, Any]) -> str:
    return json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_tuple(values: Any) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if isinstance(value, str) and value}))


def _identity(candidate: Mapping[str, Any]) -> tuple[str | None, str | None]:
    candidate_id = candidate.get("candidate_id") or candidate.get("id")
    version = candidate.get("candidate_version") or candidate.get("version")
    return (
        str(candidate_id) if candidate_id is not None else None,
        str(version) if version is not None else None,
    )


def _nested_root(candidate: Mapping[str, Any], key: str) -> Any:
    direct = candidate.get(key)
    if direct is not None:
        return direct
    extraction = candidate.get("boundary_extraction")
    return extraction.get(key) if isinstance(extraction, Mapping) else None


def _space_records(candidate: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    root = _nested_root(candidate, "space_boundary_graphs")
    records: list[dict[str, Any]] = []
    if not isinstance(root, Mapping):
        return ()
    for floor in sorted(root, key=str):
        graph = root[floor]
        if isinstance(graph, Mapping) and isinstance(graph.get("spaces"), list):
            records.extend(item for item in graph["spaces"] if isinstance(item, dict))
    return tuple(records)


def _opening_root(candidate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    root = _nested_root(candidate, "opening_host_graphs")
    return root if isinstance(root, Mapping) else None


def _access_graph(candidate: Mapping[str, Any]) -> dict[str, Any] | None:
    graph = _nested_root(candidate, "access_graph")
    return graph if isinstance(graph, dict) else None


def _execution_evidence(
    strategy: ArchitecturalChangeStrategy, candidate: Mapping[str, Any]
) -> Mapping[str, Any] | None:
    sources: list[Any] = []
    if isinstance(strategy.provenance, Mapping):
        sources.extend((
            strategy.provenance.get("opening_access_realization"),
            strategy.provenance.get("execution_evidence"),
        ))
    evidence = candidate.get("realization_evidence")
    if isinstance(evidence, Mapping):
        sources.append(evidence.get(strategy.strategy_id))
    return next((item for item in sources if isinstance(item, Mapping)), None)


def _find_opening(candidate: Mapping[str, Any], interface_id: str) -> tuple[str, dict[str, Any]] | None:
    root = _opening_root(candidate)
    if root is None:
        return None
    matches: list[tuple[str, dict[str, Any]]] = []
    for floor in sorted(root, key=str):
        graph = root[floor]
        if not isinstance(graph, Mapping):
            continue
        for opening in graph.get("openings", ()):
            if isinstance(opening, dict) and opening.get("opening_id") == interface_id:
                matches.append((str(floor), opening))
    return matches[0] if len(matches) == 1 else None


def _find_edge(candidate: Mapping[str, Any], interface_id: str) -> dict[str, Any] | None:
    graph = _access_graph(candidate)
    if graph is None:
        return None
    matches = [
        edge for edge in graph.get("edges", ())
        if isinstance(edge, dict) and (edge.get("edge_id") or edge.get("id")) == interface_id
    ]
    return matches[0] if len(matches) == 1 else None


def _line_from_opening(opening: Mapping[str, Any]) -> LineString | None:
    raw = opening.get("centerline") or opening.get("threshold")
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        return None
    try:
        line = LineString(raw)
    except (TypeError, ValueError):
        return None
    return line if not line.is_empty and line.length > _EPSILON else None


def _access_failures(
    graph: Mapping[str, Any], records: Mapping[str, Mapping[str, Any]]
) -> tuple[str, ...]:
    nodes = {
        str(item.get("id")): item
        for item in graph.get("nodes", ())
        if isinstance(item, Mapping) and item.get("id") is not None
    }
    adjacency = {node_id: set() for node_id in nodes}
    for edge in graph.get("edges", ()):
        if not isinstance(edge, Mapping) or edge.get("kind") != "DOOR_PORTAL":
            continue
        first, second = edge.get("from"), edge.get("to")
        if isinstance(first, str) and isinstance(second, str) and first in adjacency and second in adjacency and first != second:
            adjacency[first].add(second)
            adjacency[second].add(first)
    required = {
        space_id for space_id, record in records.items()
        if record.get("required") is True and space_id in adjacency
    }
    anchors = set()
    for node_id, node in nodes.items():
        token = " ".join((
            node_id,
            str(node.get("semantic_class") or ""),
            str(records.get(node_id, {}).get("circulation_role") or ""),
        )).upper()
        if any(item in token for item in ("EXTERIOR", "HALL", "CORRIDOR", "CIRCULATION", "LOBBY", "STAIR")):
            anchors.add(node_id)

    def reachable(start: str) -> set[str]:
        seen, stack = {start}, [start]
        while stack:
            current = stack.pop()
            for neighbor in adjacency.get(current, set()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        return seen

    failures = []
    for space_id in sorted(required):
        if not adjacency.get(space_id):
            failures.append(f"sealed_required_space:{space_id}")
        elif anchors and not (reachable(space_id) & anchors):
            failures.append(f"required_space_not_connected_to_circulation:{space_id}")
    if not anchors and required:
        seed = min(required)
        if not required <= reachable(seed):
            failures.append("required_access_graph_disconnected")
    return tuple(failures)


def _refresh_access_components(graph: dict[str, Any]) -> None:
    """Refresh derived connectivity metadata after the edge transaction."""
    nodes = {
        str(item.get("id")) for item in graph.get("nodes", ())
        if isinstance(item, Mapping) and item.get("id") is not None
    }
    adjacency = {node_id: set() for node_id in nodes}
    for edge in graph.get("edges", ()):
        if not isinstance(edge, Mapping) or edge.get("kind") != "DOOR_PORTAL":
            continue
        first, second = edge.get("from"), edge.get("to")
        if isinstance(first, str) and isinstance(second, str) and first in nodes and second in nodes and first != second:
            adjacency[first].add(second)
            adjacency[second].add(first)
    unseen = set(nodes)
    components = []
    while unseen:
        seed = min(unseen)
        unseen.remove(seed)
        component, stack = [], [seed]
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in sorted(adjacency[current], reverse=True):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
        components.append(sorted(component))
    graph["connected_components"] = sorted(components, key=lambda item: tuple(item))


def _protected_violation(
    candidate: Mapping[str, Any], pair: tuple[str, str], interface_id: str, boundary_ref: str
) -> tuple[str, ...]:
    failures = []
    protected_entities = candidate.get("protected_entities", ())
    if isinstance(protected_entities, (list, tuple, set, frozenset)):
        protected = {str(item) for item in protected_entities}
        if interface_id in protected or boundary_ref in protected:
            failures.append("protected_interface_or_boundary")
    for key in ("protected_constraints", "hard_constraints"):
        raw = candidate.get(key)
        records = raw.values() if isinstance(raw, Mapping) else raw
        if not isinstance(records, (list, tuple, set, frozenset)):
            continue
        for item in records:
            if not isinstance(item, Mapping) or not (item.get("protected") is True or item.get("severity") == "hard"):
                continue
            target = item.get("entity_id") or item.get("boundary_ref") or item.get("interface_id")
            entities = item.get("entities") or item.get("relation_pair")
            if target in {interface_id, boundary_ref}:
                failures.append("protected_interface_or_boundary")
            if isinstance(entities, (list, tuple)) and len(entities) == 2 and set(map(str, entities)) == set(pair):
                failures.append("protected_space_interface_pair")
    return _stable_tuple(failures)


def _rejection(
    strategy: ArchitecturalChangeStrategy,
    parent_id: str,
    parent_hash: str,
    status: str,
    failures: tuple[str, ...],
    *,
    rejected_operations: tuple[str, ...] = (),
    geometry_checks: tuple[Mapping[str, Any], ...] = (),
    access_checks: tuple[Mapping[str, Any], ...] = (),
    circulation_checks: tuple[Mapping[str, Any], ...] = (),
    constraint_checks: tuple[Mapping[str, Any], ...] = (),
) -> tuple[None, OpeningAccessRealizationResult]:
    token = hashlib.sha256(
        f"{parent_hash}|{strategy.strategy_id}|{status}|{'|'.join(failures)}".encode("utf-8")
    ).hexdigest()[:16]
    return None, OpeningAccessRealizationResult(
        realization_id=f"opening-access-realization:{token}",
        strategy_id=strategy.strategy_id,
        parent_candidate_id=parent_id,
        derived_candidate_id=None,
        status=status,
        opening_access_changes=(),
        affected_entities=(),
        applied_operations=(),
        rejected_operations=rejected_operations,
        geometry_checks=geometry_checks,
        access_checks=access_checks,
        circulation_checks=circulation_checks,
        constraint_checks=constraint_checks,
        required_downstream_rechecks=(),
        warnings=(),
        failures=failures,
        parent_hash=parent_hash,
        derived_hash=None,
        provenance={
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01F-C",
            "realizer": REALIZER_VERSION,
            "commit": False,
            "parent_unchanged": True,
        },
    )


def realize_selected_opening_access_strategy(
    strategy: ArchitecturalChangeStrategy,
    readiness: ExecutionReadinessResult,
    parent_candidate: Mapping[str, Any],
    *,
    expected_parent_id: str,
    expected_parent_version: str,
    expected_parent_hash: str,
) -> tuple[dict[str, Any] | None, OpeningAccessRealizationResult]:
    """Realize one evidence-proved opening/access operation on a cloned child."""
    if not isinstance(strategy, ArchitecturalChangeStrategy):
        raise ValueError("strategy must be ArchitecturalChangeStrategy")
    if not isinstance(readiness, ExecutionReadinessResult):
        raise ValueError("readiness must be ExecutionReadinessResult")
    if not isinstance(parent_candidate, Mapping):
        raise ValueError("parent_candidate must be a mapping")

    parent_document_before = _canonical_document(parent_candidate)
    parent_hash = candidate_semantic_hash(parent_candidate)
    parent_id, parent_version = _identity(parent_candidate)
    result_parent_id = parent_id or str(expected_parent_id)
    stored_hash = parent_candidate.get("candidate_hash") or parent_candidate.get("hash")
    if (
        parent_id != str(expected_parent_id)
        or parent_version != str(expected_parent_version)
        or parent_hash != str(expected_parent_hash)
        or (stored_hash is not None and str(stored_hash) != parent_hash)
    ):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_STALE_PARENT,
            ("parent_identity_version_or_hash_mismatch",),
        )

    if (
        readiness.plan_id != strategy.plan_id
        or readiness.readiness_status not in {READINESS_STATUS_READY, READINESS_STATUS_READY_WITH_PREREQUISITES}
        or readiness.constraint_conflicts
    ):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_CONSTRAINT,
            ("selected_strategy_not_admitted_by_readiness",),
            constraint_checks=({"check": "readiness", "passed": False, "status": readiness.readiness_status},),
        )
    satisfied = parent_candidate.get("satisfied_prerequisites", ())
    satisfied_set = set(satisfied) if isinstance(satisfied, (list, tuple, set, frozenset)) else set()
    missing = tuple(sorted(set(strategy.prerequisites) - satisfied_set))
    if missing:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_CONSTRAINT,
            tuple(f"unresolved_prerequisite:{item}" for item in missing),
        )
    if strategy.strategy_type not in SUPPORTED_STRATEGY_TYPES:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_UNSUPPORTED_STRATEGY,
            (f"unsupported_strategy_type:{strategy.strategy_type}",),
            rejected_operations=(strategy.strategy_type,),
        )

    evidence = _execution_evidence(strategy, parent_candidate)
    if evidence is None:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
            ("insufficient_opening_access_execution_evidence",),
        )
    operation = evidence.get("operation")
    if evidence.get("execution_family") != SUPPORTED_EXECUTION_FAMILY or operation not in SUPPORTED_OPERATIONS:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_UNSUPPORTED_STRATEGY,
            ("unsupported_execution_family_or_operation",),
            rejected_operations=(str(operation or "unknown"),),
        )

    raw_pair = evidence.get("target_space_pair")
    interface_id = evidence.get("interface_id") or evidence.get("opening_id")
    boundary_ref = evidence.get("shared_boundary_ref")
    if (
        not isinstance(raw_pair, (list, tuple)) or len(raw_pair) != 2
        or not all(isinstance(item, str) and item for item in raw_pair)
        or raw_pair[0] == raw_pair[1]
        or not isinstance(interface_id, str) or not interface_id
        or not isinstance(boundary_ref, str) or not boundary_ref
    ):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
            ("incomplete_interface_pair_or_shared_boundary_evidence",),
            rejected_operations=(str(operation),),
        )
    pair = (raw_pair[0], raw_pair[1])
    if not set(pair) <= set(strategy.target_entities):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_CONSTRAINT,
            ("evidence_pair_not_selected_strategy_targets",),
            rejected_operations=(str(operation),),
        )

    records = {str(item.get("space_id")): item for item in _space_records(parent_candidate)}
    if len(records) != len(_space_records(parent_candidate)) or not set(pair) <= set(records):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
            ("target_spaces_not_uniquely_resolved",),
            rejected_operations=(str(operation),),
        )
    if str(records[pair[0]].get("floor")) != str(records[pair[1]].get("floor")):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
            ("cross_floor_access_interface_not_supported",),
            rejected_operations=(str(operation),),
        )
    try:
        polygons = (Polygon(records[pair[0]]["polygon"]), Polygon(records[pair[1]]["polygon"]))
        shared = polygons[0].boundary.intersection(polygons[1].boundary)
    except (KeyError, TypeError, ValueError):
        shared = LineString()
    if shared.is_empty or shared.length <= _EPSILON or polygons[0].intersection(polygons[1]).area > _EPSILON:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
            ("target_spaces_have_no_proved_shared_boundary",),
            rejected_operations=(str(operation),),
            geometry_checks=({"check": "actual_shared_boundary", "passed": False},),
        )

    raw_boundary = evidence.get("boundary_segment")
    if not isinstance(raw_boundary, (list, tuple)) or len(raw_boundary) != 2:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
            ("explicit_boundary_segment_missing",),
            rejected_operations=(str(operation),),
        )
    try:
        boundary = LineString(raw_boundary)
    except (TypeError, ValueError):
        boundary = LineString()
    if (
        boundary.is_empty or boundary.length <= _EPSILON
        or abs(boundary.length - hypot(
            boundary.coords[-1][0] - boundary.coords[0][0],
            boundary.coords[-1][1] - boundary.coords[0][1],
        )) > _EPSILON
        or boundary.difference(shared.buffer(_EPSILON)).length > _EPSILON
    ):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
            ("declared_boundary_segment_not_on_actual_straight_shared_boundary",),
            rejected_operations=(str(operation),),
        )

    existing = _find_opening(parent_candidate, interface_id)
    existing_edge = _find_edge(parent_candidate, interface_id)
    before_interface = deepcopy(existing[1]) if existing else None
    if operation == "CREATE_DIRECT_ACCESS_INTERFACE" and (existing is not None or existing_edge is not None):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS,
            ("interface_id_already_exists",), rejected_operations=(str(operation),),
        )
    if operation in {"REBIND_EXISTING_PORTAL", "RELOCATE_ACCESS_INTERFACE"} and (existing is None or existing_edge is None):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS,
            ("existing_portal_and_access_edge_binding_required",), rejected_operations=(str(operation),),
        )

    width = evidence.get("width_m")
    width_source = evidence.get("width_source")
    position_source = evidence.get("position_source")
    if operation == "REBIND_EXISTING_PORTAL" and existing is not None:
        existing_line = _line_from_opening(existing[1])
        if width is None:
            width = existing[1].get("clear_width_m") or (existing_line.length if existing_line is not None else None)
        if width_source is None:
            width_source = "existing_portal.clear_width_m"
        if position_source is None:
            position_source = "existing_portal.centerline"
    if (
        not isinstance(width, (int, float)) or isinstance(width, bool) or width <= 0
        or not isinstance(width_source, str) or not width_source
        or not isinstance(position_source, str) or not position_source
    ):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
            ("proved_width_or_position_source_missing",),
            rejected_operations=(str(operation),),
        )
    width = float(width)

    if operation == "REBIND_EXISTING_PORTAL" and existing is not None:
        opening_line = _line_from_opening(existing[1])
        if opening_line is None:
            return _rejection(
                strategy, result_parent_id, parent_hash,
                OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
                ("existing_portal_geometry_missing",), rejected_operations=(str(operation),),
            )
        position = {"mode": "EXISTING_PORTAL_GEOMETRY", "center_distance_m": boundary.project(opening_line.centroid)}
    else:
        distance = evidence.get("position_distance_m")
        fraction = evidence.get("position_fraction")
        if isinstance(distance, (int, float)) and not isinstance(distance, bool):
            center_distance = float(distance)
            position = {"mode": "DISTANCE_FROM_BOUNDARY_START", "distance_m": center_distance}
        elif isinstance(fraction, (int, float)) and not isinstance(fraction, bool) and 0 <= float(fraction) <= 1:
            center_distance = boundary.length * float(fraction)
            position = {"mode": "FRACTION_OF_PROVED_BOUNDARY", "fraction": float(fraction), "distance_m": center_distance}
        else:
            return _rejection(
                strategy, result_parent_id, parent_hash,
                OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
                ("explicit_or_geometry_derived_position_missing",),
                rejected_operations=(str(operation),),
            )
        start_distance, end_distance = center_distance - width / 2.0, center_distance + width / 2.0
        if start_distance <= _EPSILON or end_distance >= boundary.length - _EPSILON:
            return _rejection(
                strategy, result_parent_id, parent_hash,
                OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
                ("opening_corner_or_endpoint_collision",),
                rejected_operations=(str(operation),),
                geometry_checks=({"check": "corner_endpoint_clearance", "passed": False},),
            )
        opening_line = LineString((boundary.interpolate(start_distance), boundary.interpolate(end_distance)))

    if (
        opening_line.length <= _EPSILON
        or abs(opening_line.length - width) > _EPSILON
        or opening_line.difference(boundary.buffer(_EPSILON)).length > _EPSILON
        or opening_line.boundary.distance(boundary.boundary) <= _EPSILON
    ):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
            ("opening_not_fully_inside_shared_boundary_or_width_mismatch",),
            rejected_operations=(str(operation),),
            geometry_checks=({"check": "opening_inside_shared_boundary", "passed": False},),
        )

    protected_failures = _protected_violation(parent_candidate, pair, interface_id, boundary_ref)
    if protected_failures:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_CONSTRAINT,
            protected_failures, rejected_operations=(str(operation),),
            constraint_checks=({"check": "protected_wall_interface_and_privacy", "passed": False},),
        )
    opening_root = _opening_root(parent_candidate)
    if opening_root is None or _access_graph(parent_candidate) is None:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS,
            ("canonical_opening_host_and_access_graphs_required",),
            rejected_operations=(str(operation),),
        )
    for floor in sorted(opening_root, key=str):
        graph = opening_root[floor]
        if not isinstance(graph, Mapping):
            continue
        for opening in graph.get("openings", ()):
            if not isinstance(opening, Mapping) or opening.get("opening_id") == interface_id:
                continue
            other = _line_from_opening(opening)
            if other is not None and opening_line.intersection(other).length > _EPSILON:
                return _rejection(
                    strategy, result_parent_id, parent_hash,
                    OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
                    (f"opening_overlap:{opening.get('opening_id')}",),
                    rejected_operations=(str(operation),),
                    geometry_checks=({"check": "no_opening_overlap", "passed": False},),
                )

    derived = deepcopy(dict(parent_candidate))
    derived_opening_root = _opening_root(derived)
    derived_access = _access_graph(derived)
    if derived_opening_root is None or derived_access is None:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_FAILED,
            ("rollback_canonical_graph_clone_resolution_failed",), rejected_operations=(str(operation),),
        )
    floor = str(records[pair[0]].get("floor"))
    floor_graph = derived_opening_root.get(floor)
    if not isinstance(floor_graph, dict) or not isinstance(floor_graph.get("openings"), list):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS,
            ("target_floor_opening_host_graph_missing",), rejected_operations=(str(operation),),
        )
    coordinates = [[float(x), float(y)] for x, y in opening_line.coords]
    after_interface = deepcopy(before_interface) if before_interface is not None else {}
    prior_geometric_evidence = after_interface.get("geometric_evidence")
    geometric_evidence = deepcopy(prior_geometric_evidence) if isinstance(prior_geometric_evidence, Mapping) else {}
    geometric_evidence.update({
        "shared_boundary_ref": boundary_ref,
        "boundary_segment": [[float(x), float(y)] for x, y in boundary.coords],
        "width_source": width_source,
        "position_source": position_source,
        "realization_kind": "ACCESS_INTERFACE_ONLY",
    })
    after_interface.update({
        "opening_id": interface_id,
        "floor": floor,
        "kind": "DOOR",
        "constituent_source_handles": [],
        "host_wall_pair_id": boundary_ref,
        "host_face_a": None,
        "host_face_b": None,
        "threshold": coordinates,
        "centerline": coordinates,
        "clear_width_m": width,
        "side_a": pair[0],
        "side_b": pair[1],
        "traversable": True,
        "exposure": "INTERIOR",
        "confidence": 1.0,
        "geometric_evidence": geometric_evidence,
        "status": "RESOLVED",
    })
    if operation == "CREATE_DIRECT_ACCESS_INTERFACE":
        floor_graph["openings"].append(after_interface)
        derived_access.setdefault("edges", []).append({
            "edge_id": interface_id,
            "from": pair[0],
            "to": pair[1],
            "kind": "DOOR_PORTAL",
            "source_handles": [],
            "opening_binding": interface_id,
        })
    else:
        derived_existing = _find_opening(derived, interface_id)
        derived_edge = _find_edge(derived, interface_id)
        if derived_existing is None or derived_edge is None:
            return _rejection(
                strategy, result_parent_id, parent_hash,
                OPENING_ACCESS_REALIZATION_STATUS_FAILED,
                ("rollback_existing_binding_lost_in_clone",), rejected_operations=(str(operation),),
            )
        derived_existing[1].clear()
        derived_existing[1].update(after_interface)
        derived_edge.update({"from": pair[0], "to": pair[1], "kind": "DOOR_PORTAL", "opening_binding": interface_id})

    _refresh_access_components(derived_access)

    derived_records = {str(item.get("space_id")): item for item in _space_records(derived)}
    access_failures = _access_failures(derived_access, derived_records)
    if access_failures:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS,
            tuple(f"rollback_access_gate:{item}" for item in access_failures),
            rejected_operations=(str(operation),),
            access_checks=({"check": "required_access_graph_connected", "passed": False, "failures": list(access_failures)},),
            circulation_checks=({"check": "required_circulation_preserved", "passed": False},),
        )
    derived_binding = _find_edge(derived, interface_id)
    derived_opening = _find_opening(derived, interface_id)
    if (
        derived_binding is None or derived_opening is None
        or {derived_binding.get("from"), derived_binding.get("to")} != set(pair)
        or {derived_opening[1].get("side_a"), derived_opening[1].get("side_b")} != set(pair)
        or _line_from_opening(derived_opening[1]) is None
    ):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS,
            ("rollback_geometric_opening_access_binding_inconsistent",),
            rejected_operations=(str(operation),),
        )
    if _canonical_document(parent_candidate) != parent_document_before or candidate_semantic_hash(parent_candidate) != parent_hash:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            OPENING_ACCESS_REALIZATION_STATUS_FAILED,
            ("parent_mutation_detected_transaction_rolled_back",), rejected_operations=(str(operation),),
        )

    delta = OpeningAccessDelta(
        interface_id=interface_id,
        target_space_pair=pair,
        shared_boundary_ref=boundary_ref,
        operation=str(operation),
        before_interface=before_interface,
        after_interface=deepcopy(after_interface),
        boundary_segment=tuple((float(x), float(y)) for x, y in boundary.coords),  # type: ignore[arg-type]
        width=width,
        source_of_width=width_source,
        position=position,
        source_of_position=position_source,
        affected_access_edges=(interface_id,),
        affected_circulation=_stable_tuple(
            item for item in pair
            if "CIRCULATION" in str(records[item].get("circulation_role") or "").upper()
        ),
        preserved_constraints=_stable_tuple(strategy.preserved_constraints),
        reason=str(evidence.get("reason") or "selected_strategy_evidence_based_opening_access_realization"),
        strategy_id=strategy.strategy_id,
        provenance={
            "realizer": REALIZER_VERSION,
            "execution_family": SUPPORTED_EXECUTION_FAMILY,
            "operation": operation,
            "geometry_source": "actual_shared_space_boundary",
            "access_source": "canonical_access_graph",
        },
    )
    fingerprint = hashlib.sha256(
        json.dumps(_json_value(delta.__dict__), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    derived_id = f"{parent_id}:derived:{fingerprint[:16]}"
    derived["parent_candidate_id"] = parent_id
    derived["candidate_id"] = derived_id
    derived["candidate_version"] = f"{parent_version}+01f-c.{fingerprint[:12]}"
    derived["derivation"] = {
        "strategy_id": strategy.strategy_id,
        "realizer": REALIZER_VERSION,
        "execution_family": SUPPORTED_EXECUTION_FAMILY,
        "operation": operation,
    }
    derived_hash = candidate_semantic_hash(derived)
    derived["candidate_hash"] = derived_hash
    rechecks = _stable_tuple(
        set(strategy.required_rechecks)
        | set(readiness.required_checks_before_execution)
        | {"opening_geometry", "access", "circulation", "privacy"}
    )
    token = hashlib.sha256(f"{parent_hash}|{strategy.strategy_id}|{fingerprint}".encode("utf-8")).hexdigest()[:16]
    result = OpeningAccessRealizationResult(
        realization_id=f"opening-access-realization:{token}",
        strategy_id=strategy.strategy_id,
        parent_candidate_id=parent_id,
        derived_candidate_id=derived_id,
        status=OPENING_ACCESS_REALIZATION_STATUS_REALIZED,
        opening_access_changes=(delta,),
        affected_entities=_stable_tuple((*pair, interface_id, boundary_ref)),
        applied_operations=(str(operation),),
        rejected_operations=(),
        geometry_checks=(
            {"check": "actual_shared_boundary", "passed": True, "length_m": shared.length},
            {"check": "opening_fully_inside_shared_boundary", "passed": True},
            {"check": "no_corner_endpoint_collision", "passed": True},
            {"check": "no_opening_overlap", "passed": True},
        ),
        access_checks=(
            {"check": "geometric_opening_semantic_edge_binding", "passed": True},
            {"check": "required_access_graph_connected", "passed": True},
            {"check": "no_mandatory_access_deletion", "passed": True},
        ),
        circulation_checks=({"check": "required_circulation_preserved", "passed": True},),
        constraint_checks=(
            {"check": "readiness_parent_identity_version_hash", "passed": True},
            {"check": "protected_wall_interface_and_privacy", "passed": True},
            {"check": "unrelated_openings_unchanged", "passed": True},
            {"check": "no_bim_door_or_window_object_created", "passed": True},
        ),
        required_downstream_rechecks=rechecks,
        warnings=(),
        failures=(),
        parent_hash=parent_hash,
        derived_hash=derived_hash,
        provenance={
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01F-C",
            "realizer": REALIZER_VERSION,
            "commit": True,
            "parent_unchanged": True,
            "execution_family": SUPPORTED_EXECUTION_FAMILY,
            "operation": operation,
            "physical_bim_object_created": False,
        },
    )
    return derived, result


__all__ = [
    "REALIZER_VERSION",
    "SUPPORTED_EXECUTION_FAMILY",
    "SUPPORTED_OPERATIONS",
    "SUPPORTED_STRATEGY_TYPES",
    "realize_selected_opening_access_strategy",
]
