"""Transactional 01F-B realization of evidence-proved adjacency topology.

The only executable transformation is a declared permutation of two existing
space polygons.  It reuses exact authoritative geometry and existing access
edges; it never invents coordinates, relations, doors, windows, or openings.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from math import hypot
from typing import Any, Mapping

from shapely.geometry import Polygon

from core.architecture.contracts.architectural_change_contracts_v1 import (
    AdjacencyRealizationResult,
    ArchitecturalChangeStrategy,
    ExecutionReadinessResult,
    READINESS_STATUS_READY,
    READINESS_STATUS_READY_WITH_PREREQUISITES,
    TOPOLOGY_REALIZATION_STATUS_FAILED,
    TOPOLOGY_REALIZATION_STATUS_REALIZED,
    TOPOLOGY_REALIZATION_STATUS_REALIZED_WITH_WARNINGS,
    TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT,
    TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY,
    TOPOLOGY_REALIZATION_STATUS_STALE_PARENT,
    TOPOLOGY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY,
    TopologyDelta,
)
from core.architecture.reasoning.architectural_change_space_geometry_realizer_v1 import (
    candidate_semantic_hash,
)


REALIZER_VERSION = "architectural_change_adjacency_topology_realizer_v1"
SUPPORTED_EXECUTION_FAMILY = "ADJACENCY_TOPOLOGY_REALIZATION"
SUPPORTED_OPERATION = "PERMUTE_EXISTING_SPACE_GEOMETRY"
SUPPORTED_STRATEGY_TYPES = frozenset({
    "STRENGTHEN_ADJACENCY",
    "RELOCATE_RELATIONSHIP",
    "PRIVATE_ADJACENCY_REALIZATION",
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


def _boundary_root(candidate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    direct = candidate.get("space_boundary_graphs")
    if isinstance(direct, Mapping):
        return direct
    extraction = candidate.get("boundary_extraction")
    if isinstance(extraction, Mapping) and isinstance(extraction.get("space_boundary_graphs"), Mapping):
        return extraction["space_boundary_graphs"]
    return None


def _space_records(candidate: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    root = _boundary_root(candidate)
    records: list[dict[str, Any]] = []
    if root is None:
        return ()
    for floor in sorted(root, key=str):
        graph = root[floor]
        if isinstance(graph, Mapping) and isinstance(graph.get("spaces"), list):
            records.extend(item for item in graph["spaces"] if isinstance(item, dict))
    return tuple(records)


def _access_graph(candidate: Mapping[str, Any]) -> dict[str, Any] | None:
    direct = candidate.get("access_graph")
    if isinstance(direct, dict):
        return direct
    extraction = candidate.get("boundary_extraction")
    if isinstance(extraction, Mapping) and isinstance(extraction.get("access_graph"), dict):
        return extraction["access_graph"]
    return None


def _opening_graph_root(candidate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    direct = candidate.get("opening_host_graphs")
    if isinstance(direct, Mapping):
        return direct
    extraction = candidate.get("boundary_extraction")
    if isinstance(extraction, Mapping) and isinstance(extraction.get("opening_host_graphs"), Mapping):
        return extraction["opening_host_graphs"]
    return None


def _polygon(record: Mapping[str, Any]) -> Polygon:
    raw = record.get("polygon")
    if not isinstance(raw, (list, tuple)):
        raise ValueError("space polygon is missing")
    return Polygon(raw)


def _coordinates(polygon: Polygon) -> list[list[float]]:
    return [[float(x), float(y)] for x, y in polygon.exterior.coords]


def _minimum_width(polygon: Polygon) -> float:
    points = list(polygon.minimum_rotated_rectangle.exterior.coords)
    lengths = [hypot(points[index + 1][0] - points[index][0], points[index + 1][1] - points[index][1]) for index in range(4)]
    return min(lengths) if lengths else 0.0


def _limit(candidate: Mapping[str, Any], record: Mapping[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    constraints = candidate.get("space_constraints")
    scoped = constraints.get(str(record.get("space_id"))) if isinstance(constraints, Mapping) else None
    if isinstance(scoped, Mapping):
        for key in keys:
            value = scoped.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


def _shared_boundary(first: Polygon, second: Polygon) -> float:
    if first.intersection(second).area > _EPSILON:
        return -1.0
    return float(first.boundary.intersection(second.boundary).length)


def _adjacency(polygons: Mapping[str, Polygon]) -> dict[tuple[str, str], float]:
    result: dict[tuple[str, str], float] = {}
    ids = sorted(polygons)
    for index, first_id in enumerate(ids):
        for second_id in ids[index + 1:]:
            length = _shared_boundary(polygons[first_id], polygons[second_id])
            if length > _EPSILON:
                result[(first_id, second_id)] = length
    return result


def _pair(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((first, second)))  # type: ignore[return-value]


def _execution_evidence(strategy: ArchitecturalChangeStrategy, candidate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    sources: list[Any] = []
    if isinstance(strategy.provenance, Mapping):
        sources.extend((strategy.provenance.get("topology_realization"), strategy.provenance.get("execution_evidence")))
    evidence = candidate.get("realization_evidence")
    if isinstance(evidence, Mapping):
        sources.append(evidence.get(strategy.strategy_id))
    return next((item for item in sources if isinstance(item, Mapping)), None)


def _protected_entities(candidate: Mapping[str, Any]) -> set[str]:
    protected = {str(item) for item in candidate.get("protected_entities", ()) if isinstance(item, str)} if isinstance(candidate.get("protected_entities", ()), (list, tuple, set, frozenset)) else set()
    for key in ("protected_constraints", "hard_constraints"):
        raw = candidate.get(key)
        records = raw.values() if isinstance(raw, Mapping) else raw
        if not isinstance(records, (list, tuple, set, frozenset)):
            continue
        for item in records:
            if isinstance(item, Mapping) and (item.get("protected") is True or item.get("severity") == "hard"):
                entity = item.get("entity_id") or item.get("space_id") or item.get("target_entity")
                if isinstance(entity, str):
                    protected.add(entity)
    for record in _space_records(candidate):
        if record.get("protected") is True or record.get("hard_constraint") is True:
            protected.add(str(record.get("space_id")))
    return protected


def _protected_pairs(candidate: Mapping[str, Any]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for key in ("protected_constraints", "hard_constraints"):
        raw = candidate.get(key)
        records = raw.values() if isinstance(raw, Mapping) else raw
        if not isinstance(records, (list, tuple, set, frozenset)):
            continue
        for item in records:
            if not isinstance(item, Mapping) or not (item.get("protected") is True or item.get("severity") == "hard"):
                continue
            raw_pair = item.get("relation_pair") or item.get("entities")
            if isinstance(raw_pair, (list, tuple)) and len(raw_pair) == 2 and all(isinstance(value, str) for value in raw_pair):
                pairs.add(_pair(raw_pair[0], raw_pair[1]))
                continue
            first = item.get("from") or item.get("from_space_id") or item.get("source_space_id")
            second = item.get("to") or item.get("to_space_id") or item.get("target_space_id")
            if isinstance(first, str) and isinstance(second, str):
                pairs.add(_pair(first, second))
    return pairs


def _graph_state(graph: Mapping[str, Any], records: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, set[str]], set[str], set[str]]:
    nodes = {str(item.get("id")): item for item in graph.get("nodes", ()) if isinstance(item, Mapping) and item.get("id") is not None}
    adjacency = {node_id: set() for node_id in nodes}
    for edge in graph.get("edges", ()):
        if not isinstance(edge, Mapping):
            continue
        first, second = edge.get("from"), edge.get("to")
        if isinstance(first, str) and isinstance(second, str) and first in adjacency and second in adjacency and first != second:
            adjacency[first].add(second)
            adjacency[second].add(first)
    required = {space_id for space_id, record in records.items() if record.get("required") is True and space_id in adjacency}
    anchors = set()
    for node_id, node in nodes.items():
        semantic = str(node.get("semantic_class") or "").upper()
        record = records.get(node_id, {})
        role = str(record.get("circulation_role") or "").upper()
        token = f"{node_id} {semantic} {role}".upper()
        if any(name in token for name in ("EXTERIOR", "HALL", "CORRIDOR", "CIRCULATION", "LOBBY", "STAIR")):
            anchors.add(node_id)
    return adjacency, required, anchors


def _reachable(adjacency: Mapping[str, set[str]], start: str) -> set[str]:
    seen = {start}
    stack = [start]
    while stack:
        current = stack.pop()
        for neighbor in adjacency.get(current, set()):
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return seen


def _access_failures(graph: Mapping[str, Any], records: Mapping[str, Mapping[str, Any]]) -> tuple[str, ...]:
    adjacency, required, anchors = _graph_state(graph, records)
    failures = []
    for space_id in sorted(required):
        if not adjacency.get(space_id):
            failures.append(f"sealed_required_space:{space_id}")
        elif anchors and not (_reachable(adjacency, space_id) & anchors):
            failures.append(f"required_space_not_connected_to_circulation:{space_id}")
    if not anchors and required:
        seed = min(required)
        if not required <= _reachable(adjacency, seed):
            failures.append("required_access_graph_disconnected")
    return tuple(failures)


def _remap_endpoint(value: Any, first: str, second: str) -> Any:
    if value == first:
        return second
    if value == second:
        return first
    return value


def _remap_existing_access(candidate: Mapping[str, Any], first: str, second: str) -> tuple[str, ...]:
    graph = _access_graph(candidate)
    if graph is None:
        return ()
    affected = []
    for edge in graph.get("edges", ()):
        if not isinstance(edge, dict):
            continue
        before = (edge.get("from"), edge.get("to"))
        edge["from"] = _remap_endpoint(edge.get("from"), first, second)
        edge["to"] = _remap_endpoint(edge.get("to"), first, second)
        if before != (edge.get("from"), edge.get("to")):
            affected.append(str(edge.get("edge_id") or edge.get("id") or f"edge:{len(affected) + 1}"))
    opening_root = _opening_graph_root(candidate)
    if opening_root is not None:
        for floor in sorted(opening_root, key=str):
            floor_graph = opening_root[floor]
            if not isinstance(floor_graph, Mapping):
                continue
            for opening in floor_graph.get("openings", ()):
                if isinstance(opening, dict):
                    opening["side_a"] = _remap_endpoint(opening.get("side_a"), first, second)
                    opening["side_b"] = _remap_endpoint(opening.get("side_b"), first, second)
    return _stable_tuple(affected)


def _rejection(
    strategy: ArchitecturalChangeStrategy,
    parent_id: str,
    parent_hash: str,
    status: str,
    failures: tuple[str, ...],
    *,
    rejected_operations: tuple[str, ...] = (),
    constraint_checks: tuple[Mapping[str, Any], ...] = (),
    topology_checks: tuple[Mapping[str, Any], ...] = (),
    access_checks: tuple[Mapping[str, Any], ...] = (),
) -> tuple[None, AdjacencyRealizationResult]:
    token = hashlib.sha256(f"{parent_hash}|{strategy.strategy_id}|{status}|{'|'.join(failures)}".encode()).hexdigest()[:16]
    return None, AdjacencyRealizationResult(
        realization_id=f"topology-realization:{token}",
        strategy_id=strategy.strategy_id,
        parent_candidate_id=parent_id,
        derived_candidate_id=None,
        status=status,
        topology_changes=(),
        affected_entities=(),
        preserved_entities=(),
        applied_operations=(),
        rejected_operations=rejected_operations,
        constraint_checks=constraint_checks,
        topology_checks=topology_checks,
        access_checks=access_checks,
        required_downstream_rechecks=(),
        warnings=(),
        failures=failures,
        parent_hash=parent_hash,
        derived_hash=None,
        provenance={"phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01F-B", "realizer": REALIZER_VERSION, "commit": False, "parent_unchanged": True},
    )


def realize_selected_adjacency_topology_strategy(
    strategy: ArchitecturalChangeStrategy,
    readiness: ExecutionReadinessResult,
    parent_candidate: Mapping[str, Any],
    *,
    expected_parent_id: str,
    expected_parent_version: str,
    expected_parent_hash: str,
) -> tuple[dict[str, Any] | None, AdjacencyRealizationResult]:
    """Realize one direct adjacency using an explicitly evidenced polygon swap."""
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
    if parent_id != str(expected_parent_id) or parent_version != str(expected_parent_version) or parent_hash != str(expected_parent_hash) or (stored_hash is not None and str(stored_hash) != parent_hash):
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_STALE_PARENT, ("parent_identity_version_or_hash_mismatch",))

    if readiness.plan_id != strategy.plan_id or readiness.readiness_status not in {READINESS_STATUS_READY, READINESS_STATUS_READY_WITH_PREREQUISITES} or readiness.constraint_conflicts:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT, ("selected_strategy_not_admitted_by_readiness",), constraint_checks=({"check": "readiness", "passed": False, "status": readiness.readiness_status},))
    satisfied = parent_candidate.get("satisfied_prerequisites", ())
    satisfied_set = set(satisfied) if isinstance(satisfied, (list, tuple, set, frozenset)) else set()
    missing = tuple(sorted(set(strategy.prerequisites) - satisfied_set))
    if missing:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT, tuple(f"unresolved_prerequisite:{item}" for item in missing))

    if strategy.strategy_type not in SUPPORTED_STRATEGY_TYPES:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY, (f"unsupported_strategy_type:{strategy.strategy_type}",), rejected_operations=(strategy.strategy_type,))
    evidence = _execution_evidence(strategy, parent_candidate)
    if evidence is None:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, ("insufficient_topology_execution_evidence",), rejected_operations=(SUPPORTED_OPERATION,))
    if evidence.get("execution_family") != SUPPORTED_EXECUTION_FAMILY or evidence.get("operation") != SUPPORTED_OPERATION:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY, ("unsupported_execution_family_or_operation",), rejected_operations=(str(evidence.get("operation", "unknown")),))

    target_id = evidence.get("target_space_id")
    partner_id = evidence.get("desired_adjacent_space_id") or evidence.get("partner_space_id")
    relocation_id = evidence.get("relocation_space_id")
    allowed = evidence.get("allowed_affected_spaces")
    if not all(isinstance(item, str) and item for item in (target_id, partner_id, relocation_id)) or len({target_id, partner_id, relocation_id}) != 3:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, ("incomplete_or_non_distinct_topology_endpoints",), rejected_operations=(SUPPORTED_OPERATION,))
    if target_id not in strategy.target_entities and partner_id not in strategy.target_entities:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT, ("evidence_pair_not_selected_strategy_target",), rejected_operations=(SUPPORTED_OPERATION,))
    if not isinstance(allowed, (list, tuple)) or not all(isinstance(item, str) for item in allowed):
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, ("allowed_affected_spaces_evidence_missing",), rejected_operations=(SUPPORTED_OPERATION,))

    records = _space_records(parent_candidate)
    by_id = {str(record.get("space_id")): record for record in records}
    if len(by_id) != len(records) or any(space_id not in by_id for space_id in (target_id, partner_id, relocation_id)):
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, ("topology_endpoints_not_uniquely_resolved",), rejected_operations=(SUPPORTED_OPERATION,))
    floors = {str(by_id[space_id].get("floor")) for space_id in (target_id, partner_id, relocation_id)}
    if len(floors) != 1:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, ("cross_floor_polygon_permutation_not_supported",), rejected_operations=(SUPPORTED_OPERATION,))
    protected = _protected_entities(parent_candidate)
    if {target_id, partner_id, relocation_id} & protected:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT, ("protected_or_hard_constrained_topology_entity",), rejected_operations=(SUPPORTED_OPERATION,), constraint_checks=({"check": "protected_hard_constraints", "passed": False, "entities": sorted({target_id, partner_id, relocation_id} & protected)},))

    try:
        before_polygons = {space_id: _polygon(record) for space_id, record in by_id.items()}
    except (TypeError, ValueError) as exc:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, (f"invalid_parent_polygon:{type(exc).__name__}",), rejected_operations=(SUPPORTED_OPERATION,))
    if any(polygon.is_empty or not polygon.is_valid or not polygon.is_simple or polygon.area <= _EPSILON for polygon in before_polygons.values()):
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, ("invalid_non_simple_or_zero_area_parent_geometry",), rejected_operations=(SUPPORTED_OPERATION,))
    before_adjacency = _adjacency(before_polygons)
    desired_pair = _pair(target_id, partner_id)
    source_pair = _pair(target_id, relocation_id)
    if desired_pair in before_adjacency:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, ("requested_adjacency_already_realized",), rejected_operations=(SUPPORTED_OPERATION,))
    if source_pair not in before_adjacency:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, ("relocation_space_not_proved_adjacent_to_target",), rejected_operations=(SUPPORTED_OPERATION,))

    after_polygons = dict(before_polygons)
    after_polygons[partner_id], after_polygons[relocation_id] = before_polygons[relocation_id], before_polygons[partner_id]
    after_adjacency = _adjacency(after_polygons)
    minimum_shared = evidence.get("minimum_shared_boundary_m", 0.0)
    if not isinstance(minimum_shared, (int, float)) or isinstance(minimum_shared, bool) or after_adjacency.get(desired_pair, 0.0) + _EPSILON < max(float(minimum_shared), _EPSILON):
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, ("proposed_permutation_does_not_prove_requested_adjacency",), rejected_operations=(SUPPORTED_OPERATION,))

    changed_pairs = set(before_adjacency) ^ set(after_adjacency)
    changed_spaces = {item for pair in changed_pairs for item in pair}
    if not changed_pairs or not changed_spaces <= set(allowed) or any(not ({partner_id, relocation_id} & set(pair)) for pair in changed_pairs):
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, ("unrelated_or_undeclared_adjacency_mutation",), rejected_operations=(SUPPORTED_OPERATION,))
    protected_pairs = _protected_pairs(parent_candidate)
    lost_protected = tuple(sorted(pair for pair in protected_pairs if pair in before_adjacency and pair not in after_adjacency))
    if lost_protected:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT, ("protected_mandatory_adjacency_would_be_lost",), rejected_operations=(SUPPORTED_OPERATION,), constraint_checks=({"check": "protected_mandatory_adjacency", "passed": False, "lost_pairs": [list(pair) for pair in lost_protected]},))

    for space_id in (partner_id, relocation_id):
        record = by_id[space_id]
        polygon = after_polygons[space_id]
        area_limit = _limit(parent_candidate, record, ("minimum_area_m2", "min_area_m2", "minimum_area"))
        width_limit = _limit(parent_candidate, record, ("minimum_width_m", "min_width_m", "minimum_dimension_m"))
        if area_limit is not None and polygon.area + _EPSILON < area_limit:
            return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT, (f"minimum_area_violated:{space_id}",), rejected_operations=(SUPPORTED_OPERATION,))
        if width_limit is not None and _minimum_width(polygon) + _EPSILON < width_limit:
            return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT, (f"minimum_dimension_violated:{space_id}",), rejected_operations=(SUPPORTED_OPERATION,))

    parent_graph = _access_graph(parent_candidate)
    if parent_graph is None:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT, ("access_graph_required_for_topology_realization",), rejected_operations=(SUPPORTED_OPERATION,))
    parent_access_failures = _access_failures(parent_graph, by_id)
    if parent_access_failures:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT, tuple(f"parent_access_invalid:{item}" for item in parent_access_failures), rejected_operations=(SUPPORTED_OPERATION,))

    derived = deepcopy(dict(parent_candidate))
    derived_by_id = {str(record.get("space_id")): record for record in _space_records(derived)}
    for space_id in (partner_id, relocation_id):
        polygon = after_polygons[space_id]
        record = derived_by_id[space_id]
        record["polygon"] = _coordinates(polygon)
        record["area_m2"] = float(polygon.area)
        if "perimeter_m" in record:
            record["perimeter_m"] = float(polygon.length)
        if "centroid" in record:
            record["centroid"] = [float(polygon.centroid.x), float(polygon.centroid.y)]
        if "interior_point" in record:
            point = polygon.representative_point()
            record["interior_point"] = [float(point.x), float(point.y)]
        if "boundary_ids" in record:
            source_record = by_id[relocation_id if space_id == partner_id else partner_id]
            record["boundary_ids"] = deepcopy(source_record.get("boundary_ids", []))
    affected_connections = _remap_existing_access(derived, partner_id, relocation_id)

    final_polygons = {space_id: _polygon(record) for space_id, record in derived_by_id.items()}
    if any(polygon.is_empty or not polygon.is_valid or not polygon.is_simple or polygon.area <= _EPSILON for polygon in final_polygons.values()):
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, ("rollback_invalid_derived_polygon",), rejected_operations=(SUPPORTED_OPERATION,))
    ids = sorted(final_polygons)
    if any(final_polygons[first].intersection(final_polygons[second]).area > _EPSILON for index, first in enumerate(ids) for second in ids[index + 1:]):
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, ("rollback_derived_polygon_overlap",), rejected_operations=(SUPPORTED_OPERATION,))
    if set(final_polygons) != set(before_polygons):
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY, ("rollback_space_deletion_or_creation",), rejected_operations=(SUPPORTED_OPERATION,))
    derived_access = _access_graph(derived)
    assert derived_access is not None
    access_failures = _access_failures(derived_access, derived_by_id)
    if access_failures:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT, tuple(f"rollback_access_gate:{item}" for item in access_failures), rejected_operations=(SUPPORTED_OPERATION,), access_checks=({"check": "required_access_and_circulation_continuity", "passed": False, "failures": list(access_failures)},))

    for space_id in set(by_id) - {partner_id, relocation_id}:
        if derived_by_id[space_id] != by_id[space_id]:
            return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_FAILED, (f"rollback_unrelated_space_mutation:{space_id}",), rejected_operations=(SUPPORTED_OPERATION,))
    if _canonical_document(parent_candidate) != parent_document_before or candidate_semantic_hash(parent_candidate) != parent_hash:
        return _rejection(strategy, result_parent_id, parent_hash, TOPOLOGY_REALIZATION_STATUS_FAILED, ("parent_mutation_detected_transaction_rolled_back",), rejected_operations=(SUPPORTED_OPERATION,))

    before_relation = {"relation": "DIRECT_ADJACENCY", "satisfied": False, "shared_boundary_m": 0.0, "evidence": "space_boundary_graphs"}
    after_relation = {"relation": "DIRECT_ADJACENCY", "satisfied": True, "shared_boundary_m": float(after_adjacency[desired_pair]), "evidence": "space_boundary_graphs"}
    circulation = tuple(sorted(space_id for space_id, record in by_id.items() if record.get("circulation_role") or any(token in space_id.lower() for token in ("hall", "corridor", "lobby", "stair"))))
    topology_checks = (
        {"check": "requested_adjacency_physically_proved", "passed": True, "pair": list(desired_pair), "shared_boundary_m": after_adjacency[desired_pair]},
        {"check": "changed_polygons_valid_simple_nonzero", "passed": True},
        {"check": "no_polygon_overlap", "passed": True},
        {"check": "no_space_deletion_or_creation", "passed": True},
        {"check": "no_unrelated_relation_mutation", "passed": True, "changed_pairs": [list(pair) for pair in sorted(changed_pairs)]},
    )
    constraint_checks = (
        {"check": "readiness", "passed": True, "status": readiness.readiness_status},
        {"check": "parent_identity_version_hash", "passed": True},
        {"check": "protected_hard_constraints", "passed": True},
        {"check": "minimum_area_and_dimensions", "passed": True},
        {"check": "protected_mandatory_adjacency", "passed": True},
    )
    access_checks = (
        {"check": "required_access_and_circulation_continuity", "passed": True},
        {"check": "no_newly_sealed_required_room", "passed": True},
        {"check": "existing_access_edges_rebound_without_creation", "passed": True, "affected_edges": list(affected_connections)},
    )
    delta = TopologyDelta(
        relation_id=str(evidence.get("relation_id") or f"adjacency:{desired_pair[0]}:{desired_pair[1]}"),
        relation_pair=desired_pair,
        before_relation=before_relation,
        after_relation=after_relation,
        affected_spaces=tuple(sorted(changed_spaces)),
        affected_connections=affected_connections,
        affected_circulation=circulation,
        topology_operations=(SUPPORTED_OPERATION,),
        preserved_constraints=_stable_tuple(set(strategy.preserved_constraints) | set(readiness.preservation_requirements)),
        reason=str(evidence.get("reason") or "selected_strategy_existing_geometry_permutation"),
        strategy_id=strategy.strategy_id,
        provenance={"phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01F-B", "realizer": REALIZER_VERSION, "geometry_source": "existing_space_boundary_graphs", "access_source": "existing_access_graph"},
    )
    fingerprint = hashlib.sha256(json.dumps(_json_value(delta.__dict__), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    derived_id = f"{parent_id}:derived:{fingerprint[:16]}"
    derived["parent_candidate_id"] = parent_id
    derived["candidate_id"] = derived_id
    derived["candidate_version"] = f"{parent_version}+01f-b.{fingerprint[:12]}"
    derived["derivation"] = {"strategy_id": strategy.strategy_id, "realizer": REALIZER_VERSION, "execution_family": SUPPORTED_EXECUTION_FAMILY, "operation": SUPPORTED_OPERATION}
    derived_hash = candidate_semantic_hash(derived)
    derived["candidate_hash"] = derived_hash
    rechecks = _stable_tuple(set(strategy.required_rechecks) | set(readiness.required_checks_before_execution) | {"openings", "privacy"})
    token = hashlib.sha256(f"{parent_hash}|{strategy.strategy_id}|{fingerprint}".encode()).hexdigest()[:16]
    result = AdjacencyRealizationResult(
        realization_id=f"topology-realization:{token}",
        strategy_id=strategy.strategy_id,
        parent_candidate_id=str(parent_id),
        derived_candidate_id=derived_id,
        status=TOPOLOGY_REALIZATION_STATUS_REALIZED,
        topology_changes=(delta,),
        affected_entities=tuple(sorted(changed_spaces)),
        preserved_entities=tuple(sorted(set(by_id) - changed_spaces)),
        applied_operations=(SUPPORTED_OPERATION,),
        rejected_operations=(),
        constraint_checks=constraint_checks,
        topology_checks=topology_checks,
        access_checks=access_checks,
        required_downstream_rechecks=rechecks,
        warnings=(),
        failures=(),
        parent_hash=parent_hash,
        derived_hash=derived_hash,
        provenance={"phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01F-B", "realizer": REALIZER_VERSION, "commit": True, "parent_unchanged": True, "execution_family": SUPPORTED_EXECUTION_FAMILY, "operation": SUPPORTED_OPERATION},
    )
    return derived, result


__all__ = [
    "REALIZER_VERSION",
    "SUPPORTED_EXECUTION_FAMILY",
    "SUPPORTED_OPERATION",
    "SUPPORTED_STRATEGY_TYPES",
    "realize_selected_adjacency_topology_strategy",
]
