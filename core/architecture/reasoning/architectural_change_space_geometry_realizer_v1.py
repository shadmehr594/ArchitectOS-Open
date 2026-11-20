"""Transactional 01F-A realization of an evidence-defined space area transfer.

This module consumes the canonical ``space_boundary_graphs`` payload produced by
the architecture space-boundary kernel.  It neither reconstructs walls nor
creates openings.  A successful call returns a new deep-cloned candidate; every
rejection returns ``None`` and leaves the parent byte/semantically unchanged.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from math import hypot
from typing import Any, Mapping

from shapely.geometry import Polygon

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeStrategy,
    ExecutionReadinessResult,
    GeometryDelta,
    GeometryRealizationResult,
    GEOMETRY_REALIZATION_STATUS_FAILED,
    GEOMETRY_REALIZATION_STATUS_REALIZED,
    GEOMETRY_REALIZATION_STATUS_REALIZED_WITH_WARNINGS,
    GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT,
    GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
    GEOMETRY_REALIZATION_STATUS_STALE_PARENT,
    GEOMETRY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY,
    READINESS_STATUS_READY,
    READINESS_STATUS_READY_WITH_PREREQUISITES,
)


REALIZER_VERSION = "architectural_change_space_geometry_realizer_v1"
SUPPORTED_STRATEGY_TYPE = "ADJACENT_AREA_TRANSFER"
SUPPORTED_EXECUTION_FAMILY = "SPACE_BOUNDARY_REALIZATION"
SUPPORTED_OPERATION = "AREA_TRANSFER"
_EPSILON = 1e-7


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _canonical_document(value: Mapping[str, Any], *, omit_hash: bool = False) -> str:
    payload = deepcopy(dict(value))
    if omit_hash:
        payload.pop("candidate_hash", None)
        payload.pop("hash", None)
    return json.dumps(_json_value(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def candidate_semantic_hash(candidate: Mapping[str, Any]) -> str:
    """Stable hash that does not recursively include a stored hash field."""
    if not isinstance(candidate, Mapping):
        raise ValueError("candidate must be a mapping")
    return hashlib.sha256(_canonical_document(candidate, omit_hash=True).encode("utf-8")).hexdigest()


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
    if root is None:
        return ()
    records: list[dict[str, Any]] = []
    for floor in sorted(root, key=str):
        graph = root[floor]
        if not isinstance(graph, Mapping) or not isinstance(graph.get("spaces"), list):
            continue
        for space in graph["spaces"]:
            if isinstance(space, dict):
                records.append(space)
    return tuple(records)


def _polygon(record: Mapping[str, Any]) -> Polygon:
    raw = record.get("polygon")
    if not isinstance(raw, (list, tuple)):
        raise ValueError("space polygon is missing")
    return Polygon(raw)


def _coordinates(polygon: Polygon) -> list[list[float]]:
    return [[float(x), float(y)] for x, y in polygon.exterior.coords]


def _geometry_reference(record: Mapping[str, Any], polygon: Polygon) -> dict[str, Any]:
    return {
        "contract": "SpacePolygon",
        "space_id": str(record.get("space_id")),
        "floor": str(record.get("floor", "")),
        "polygon": _coordinates(polygon),
    }


def _minimum_width(polygon: Polygon) -> float:
    rectangle = polygon.minimum_rotated_rectangle
    points = list(rectangle.exterior.coords)
    lengths = [hypot(points[index + 1][0] - points[index][0], points[index + 1][1] - points[index][1]) for index in range(4)]
    return min(lengths) if lengths else 0.0


def _area_limit(candidate: Mapping[str, Any], record: Mapping[str, Any]) -> float | None:
    for key in ("minimum_area_m2", "min_area_m2", "minimum_area"):
        value = record.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    constraints = candidate.get("space_constraints")
    scoped = constraints.get(str(record.get("space_id"))) if isinstance(constraints, Mapping) else None
    if isinstance(scoped, Mapping):
        for key in ("minimum_area_m2", "min_area_m2", "minimum_area"):
            value = scoped.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


def _width_limit(candidate: Mapping[str, Any], record: Mapping[str, Any]) -> float | None:
    for key in ("minimum_width_m", "min_width_m", "minimum_dimension_m"):
        value = record.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    constraints = candidate.get("space_constraints")
    scoped = constraints.get(str(record.get("space_id"))) if isinstance(constraints, Mapping) else None
    if isinstance(scoped, Mapping):
        for key in ("minimum_width_m", "min_width_m", "minimum_dimension_m"):
            value = scoped.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


def _protected_entities(candidate: Mapping[str, Any]) -> set[str]:
    protected: set[str] = set()
    raw = candidate.get("protected_entities")
    if isinstance(raw, (list, tuple, set, frozenset)):
        protected.update(str(item) for item in raw if isinstance(item, str))
    for key in ("protected_constraints", "hard_constraints"):
        constraints = candidate.get(key)
        records = constraints.values() if isinstance(constraints, Mapping) else constraints
        if isinstance(records, (list, tuple, set, frozenset)) or hasattr(records, "__iter__") and not isinstance(records, (str, bytes, type(None))):
            for item in records:
                if isinstance(item, Mapping) and (item.get("protected") is True or item.get("severity") == "hard"):
                    entity = item.get("entity_id") or item.get("space_id") or item.get("target_entity")
                    if isinstance(entity, str):
                        protected.add(entity)
    for record in _space_records(candidate):
        if record.get("protected") is True or record.get("hard_constraint") is True:
            protected.add(str(record.get("space_id")))
    return protected


def _execution_evidence(strategy: ArchitecturalChangeStrategy, candidate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    sources: list[Any] = []
    if isinstance(strategy.provenance, Mapping):
        sources.append(strategy.provenance.get("area_transfer"))
        sources.append(strategy.provenance.get("execution_evidence"))
    evidence = candidate.get("realization_evidence")
    if isinstance(evidence, Mapping):
        sources.append(evidence.get(strategy.strategy_id))
    return next((item for item in sources if isinstance(item, Mapping)), None)


def _access_graph(candidate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    graph = candidate.get("access_graph")
    if isinstance(graph, Mapping):
        return graph
    extraction = candidate.get("boundary_extraction")
    if isinstance(extraction, Mapping) and isinstance(extraction.get("access_graph"), Mapping):
        return extraction["access_graph"]
    return None


def _rejection(
    strategy: ArchitecturalChangeStrategy,
    parent_id: str,
    parent_hash: str,
    status: str,
    failures: tuple[str, ...],
    *,
    rejected_operations: tuple[str, ...] = (),
    constraint_checks: tuple[Mapping[str, Any], ...] = (),
    geometry_checks: tuple[Mapping[str, Any], ...] = (),
    rechecks: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> tuple[None, GeometryRealizationResult]:
    token = hashlib.sha256(f"{parent_hash}|{strategy.strategy_id}|{status}".encode("utf-8")).hexdigest()[:16]
    return None, GeometryRealizationResult(
        realization_id=f"realization:{token}",
        strategy_id=strategy.strategy_id,
        parent_candidate_id=parent_id,
        derived_candidate_id=None,
        status=status,
        affected_entities=(),
        geometry_changes=(),
        preserved_entities=(),
        applied_operations=(),
        rejected_operations=rejected_operations,
        constraint_checks=constraint_checks,
        geometry_checks=geometry_checks,
        required_downstream_rechecks=rechecks,
        warnings=warnings,
        failures=failures,
        parent_hash=parent_hash,
        derived_hash=None,
        provenance={
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01F-A",
            "realizer": REALIZER_VERSION,
            "commit": False,
            "parent_unchanged": True,
        },
    )


def realize_selected_space_geometry_strategy(
    strategy: ArchitecturalChangeStrategy,
    readiness: ExecutionReadinessResult,
    parent_candidate: Mapping[str, Any],
    *,
    expected_parent_id: str,
    expected_parent_version: str,
    expected_parent_hash: str,
) -> tuple[dict[str, Any] | None, GeometryRealizationResult]:
    """Apply one proved adjacent area transfer to a derived candidate only."""
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
    stored_parent_hash = parent_candidate.get("candidate_hash") or parent_candidate.get("hash")

    if (
        parent_id != str(expected_parent_id)
        or parent_version != str(expected_parent_version)
        or parent_hash != str(expected_parent_hash)
        or (stored_parent_hash is not None and str(stored_parent_hash) != parent_hash)
    ):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            GEOMETRY_REALIZATION_STATUS_STALE_PARENT,
            ("parent_identity_version_or_hash_mismatch",),
        )

    if readiness.plan_id != strategy.plan_id or readiness.readiness_status not in {
        READINESS_STATUS_READY, READINESS_STATUS_READY_WITH_PREREQUISITES,
    } or readiness.constraint_conflicts:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT,
            ("selected_strategy_not_admitted_by_readiness",),
            constraint_checks=({"check": "readiness", "passed": False, "status": readiness.readiness_status},),
        )

    satisfied = parent_candidate.get("satisfied_prerequisites", ())
    satisfied_set = set(satisfied) if isinstance(satisfied, (list, tuple, set, frozenset)) else set()
    missing_prerequisites = tuple(sorted(set(strategy.prerequisites) - satisfied_set))
    if missing_prerequisites:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT,
            tuple(f"unresolved_prerequisite:{item}" for item in missing_prerequisites),
            constraint_checks=({"check": "strategy_prerequisites", "passed": False, "missing": list(missing_prerequisites)},),
        )

    actions = set(strategy.proposed_semantic_actions)
    if strategy.strategy_type != SUPPORTED_STRATEGY_TYPE or "transfer_adjacent_available_area" not in actions:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            GEOMETRY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY,
            (f"unsupported_strategy_type:{strategy.strategy_type}",),
            rejected_operations=(strategy.strategy_type,),
        )

    evidence = _execution_evidence(strategy, parent_candidate)
    if evidence is None:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
            ("insufficient_area_transfer_execution_evidence",),
            rejected_operations=(SUPPORTED_OPERATION,),
        )
    if evidence.get("execution_family", SUPPORTED_EXECUTION_FAMILY) != SUPPORTED_EXECUTION_FAMILY or evidence.get("operation", SUPPORTED_OPERATION) != SUPPORTED_OPERATION:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            GEOMETRY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY,
            ("unsupported_execution_family_or_operation",),
            rejected_operations=(str(evidence.get("operation", "unknown")),),
        )

    target_id = evidence.get("target_space_id")
    donor_id = evidence.get("source_space_id") or evidence.get("donor_space_id")
    raw_transfer = evidence.get("transfer_polygon")
    requested_increase = evidence.get("increase_area_m2")
    target_after_area = evidence.get("target_after_area_m2")
    if not isinstance(target_id, str) or not isinstance(donor_id, str) or not isinstance(raw_transfer, (list, tuple)):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
            ("incomplete_target_donor_or_transfer_polygon_evidence",),
            rejected_operations=(SUPPORTED_OPERATION,),
        )
    if target_id not in strategy.target_entities:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT,
            ("evidence_target_not_selected_strategy_target",),
            rejected_operations=(SUPPORTED_OPERATION,),
        )
    if not isinstance(requested_increase, (int, float)) and not isinstance(target_after_area, (int, float)):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
            ("explicit_area_target_missing",),
            rejected_operations=(SUPPORTED_OPERATION,),
        )

    parent_spaces = _space_records(parent_candidate)
    by_id = {str(record.get("space_id")): record for record in parent_spaces}
    if len(by_id) != len(parent_spaces) or target_id not in by_id or donor_id not in by_id or target_id == donor_id:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
            ("target_or_adjacent_transfer_source_not_uniquely_resolved",),
            rejected_operations=(SUPPORTED_OPERATION,),
        )

    protected = _protected_entities(parent_candidate)
    if target_id in protected or donor_id in protected:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT,
            ("protected_or_hard_constrained_space_boundary",),
            rejected_operations=(SUPPORTED_OPERATION,),
            constraint_checks=({"check": "protected_hard_constraints", "passed": False, "entities": sorted({target_id, donor_id} & protected)},),
        )

    geometry_checks: list[Mapping[str, Any]] = []
    constraint_checks: list[Mapping[str, Any]] = [
        {"check": "readiness", "passed": True, "status": readiness.readiness_status},
        {"check": "parent_identity_version_hash", "passed": True},
        {"check": "protected_hard_constraints", "passed": True},
    ]
    try:
        target_before = _polygon(by_id[target_id])
        donor_before = _polygon(by_id[donor_id])
        transfer = Polygon(raw_transfer)
    except (TypeError, ValueError) as exc:
        return _rejection(
            strategy, result_parent_id, parent_hash,
            GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
            (f"invalid_polygon_evidence:{type(exc).__name__}",),
            rejected_operations=(SUPPORTED_OPERATION,),
        )

    initial = (target_before, donor_before, transfer)
    if any(item.is_empty or not item.is_valid or not item.is_simple or item.area <= _EPSILON for item in initial):
        return _rejection(
            strategy, result_parent_id, parent_hash,
            GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
            ("invalid_non_simple_or_zero_area_input_geometry",),
            rejected_operations=(SUPPORTED_OPERATION,),
        )
    if target_before.intersection(donor_before).area > _EPSILON:
        return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
                          ("parent_target_donor_overlap",), rejected_operations=(SUPPORTED_OPERATION,))
    if target_before.boundary.intersection(donor_before.boundary).length <= _EPSILON:
        return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
                          ("transfer_source_not_immediately_adjacent",), rejected_operations=(SUPPORTED_OPERATION,))
    if transfer.difference(donor_before).area > _EPSILON or transfer.boundary.intersection(target_before.boundary).length <= _EPSILON:
        return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
                          ("transfer_polygon_not_proved_inside_adjacent_source",), rejected_operations=(SUPPORTED_OPERATION,))

    expected_increase = float(requested_increase) if isinstance(requested_increase, (int, float)) else float(target_after_area) - target_before.area
    if expected_increase <= _EPSILON or abs(transfer.area - expected_increase) > _EPSILON:
        return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
                          ("transfer_polygon_area_does_not_match_explicit_area_target",), rejected_operations=(SUPPORTED_OPERATION,))

    target_after = target_before.union(transfer)
    donor_after = donor_before.difference(transfer)
    if (
        not isinstance(target_after, Polygon)
        or not isinstance(donor_after, Polygon)
        or target_after.is_empty
        or donor_after.is_empty
    ):
        return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
                          ("area_transfer_would_fragment_or_delete_space",), rejected_operations=(SUPPORTED_OPERATION,))
    changed = (target_after, donor_after)
    if any(item.is_empty or not item.is_valid or not item.is_simple or item.area <= _EPSILON for item in changed):
        return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
                          ("proposed_geometry_failed_validity_gate",), rejected_operations=(SUPPORTED_OPERATION,))

    for record, polygon in ((by_id[target_id], target_after), (by_id[donor_id], donor_after)):
        area_limit = _area_limit(parent_candidate, record)
        width_limit = _width_limit(parent_candidate, record)
        if area_limit is not None and polygon.area + _EPSILON < area_limit:
            return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT,
                              (f"minimum_area_violated:{record.get('space_id')}",), rejected_operations=(SUPPORTED_OPERATION,))
        if width_limit is not None and _minimum_width(polygon) + _EPSILON < width_limit:
            return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT,
                              (f"minimum_dimension_violated:{record.get('space_id')}",), rejected_operations=(SUPPORTED_OPERATION,))
    constraint_checks.append({"check": "minimum_area_and_dimensions", "passed": True})

    derived = deepcopy(dict(parent_candidate))
    derived_by_id = {str(record.get("space_id")): record for record in _space_records(derived)}
    deltas: list[GeometryDelta] = []
    for space_id, before, after, operation in (
        (target_id, target_before, target_after, "EXPAND_SPACE_BOUNDARY"),
        (donor_id, donor_before, donor_after, "REDUCE_TRANSFERABLE_SPACE_BOUNDARY"),
    ):
        record = derived_by_id[space_id]
        before_record = by_id[space_id]
        record["polygon"] = _coordinates(after)
        record["area_m2"] = float(after.area)
        if "perimeter_m" in record:
            record["perimeter_m"] = float(after.length)
        if "centroid" in record:
            record["centroid"] = [float(after.centroid.x), float(after.centroid.y)]
        if "interior_point" in record:
            point = after.representative_point()
            record["interior_point"] = [float(point.x), float(point.y)]
        deltas.append(GeometryDelta(
            entity_id=space_id,
            space_id=space_id,
            operation=operation,
            before_geometry=_geometry_reference(before_record, before),
            after_geometry=_geometry_reference(record, after),
            before_area=float(before.area),
            after_area=float(after.area),
            affected_neighbors=(donor_id if space_id == target_id else target_id,),
            reason="selected_strategy_evidence_based_adjacent_area_transfer",
            strategy_id=strategy.strategy_id,
            provenance={
                "realizer": REALIZER_VERSION,
                "execution_family": SUPPORTED_EXECUTION_FAMILY,
                "operation": SUPPORTED_OPERATION,
                "geometry_source": "existing_space_boundary_graph",
            },
        ))

    final_polygons: dict[str, Polygon] = {}
    try:
        for record in _space_records(derived):
            polygon = _polygon(record)
            if polygon.is_empty or not polygon.is_valid or not polygon.is_simple or polygon.area <= _EPSILON:
                raise ValueError(f"invalid_space:{record.get('space_id')}")
            final_polygons[str(record.get("space_id"))] = polygon
    except ValueError as exc:
        return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
                          (f"rollback_geometry_gate:{exc}",), rejected_operations=(SUPPORTED_OPERATION,))

    ids = sorted(final_polygons)
    for index, first_id in enumerate(ids):
        for second_id in ids[index + 1:]:
            if final_polygons[first_id].intersection(final_polygons[second_id]).area > _EPSILON:
                return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
                                  (f"rollback_polygon_overlap:{first_id}:{second_id}",), rejected_operations=(SUPPORTED_OPERATION,))
    geometry_checks.extend((
        {"check": "changed_polygons_valid_simple_nonzero", "passed": True},
        {"check": "no_polygon_overlap", "passed": True},
        {"check": "no_space_deletion", "passed": set(final_polygons) == set(by_id)},
        {"check": "area_conservation", "passed": abs((target_before.area + donor_before.area) - (target_after.area + donor_after.area)) <= _EPSILON},
    ))
    if not all(bool(item["passed"]) for item in geometry_checks):
        return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
                          ("rollback_post_apply_geometry_gate",), rejected_operations=(SUPPORTED_OPERATION,),
                          geometry_checks=tuple(geometry_checks))

    for space_id in set(by_id) - {target_id, donor_id}:
        if derived_by_id[space_id] != by_id[space_id]:
            return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_FAILED,
                              (f"rollback_unrelated_space_mutation:{space_id}",), rejected_operations=(SUPPORTED_OPERATION,))
    constraint_checks.append({"check": "unrelated_spaces_unchanged", "passed": True})

    warnings: list[str] = []
    rechecks = set(strategy.required_rechecks) | set(readiness.required_checks_before_execution)
    graph = _access_graph(parent_candidate)
    access_required = bool({"access", "circulation", "target_access", "circulation_continuity"} & set(strategy.preserved_constraints))
    if graph is not None:
        nodes = {str(item.get("id")) for item in graph.get("nodes", ()) if isinstance(item, Mapping)}
        edges = [item for item in graph.get("edges", ()) if isinstance(item, Mapping)]
        required_ids = {str(record.get("space_id")) for record in parent_spaces if record.get("required") is True}
        required_ids.add(target_id)
        sealed = sorted(space_id for space_id in required_ids if space_id in nodes and not any(space_id in (edge.get("from"), edge.get("to")) for edge in edges))
        if access_required and (target_id not in nodes or sealed):
            return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT,
                              ("access_or_circulation_continuity_not_preserved",), rejected_operations=(SUPPORTED_OPERATION,))
        constraint_checks.append({"check": "access_graph_and_required_space_continuity", "passed": True})
    elif access_required:
        warnings.append("access_representation_unavailable_preservation_requires_downstream_recheck")
        rechecks.update(("access", "circulation"))
        constraint_checks.append({"check": "access_graph_and_required_space_continuity", "passed": None, "deferred": True})

    if _canonical_document(parent_candidate) != parent_document_before or candidate_semantic_hash(parent_candidate) != parent_hash:
        return _rejection(strategy, result_parent_id, parent_hash, GEOMETRY_REALIZATION_STATUS_FAILED,
                          ("parent_mutation_detected_transaction_rolled_back",), rejected_operations=(SUPPORTED_OPERATION,))

    delta_fingerprint = hashlib.sha256(json.dumps([_json_value(delta) for delta in [delta.__dict__ for delta in deltas]], sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    derived_id = f"{parent_id}:derived:{delta_fingerprint[:16]}"
    derived["parent_candidate_id"] = parent_id
    derived["candidate_id"] = derived_id
    derived["candidate_version"] = f"{parent_version}+01f-a.{delta_fingerprint[:12]}"
    derived["derivation"] = {
        "strategy_id": strategy.strategy_id,
        "realizer": REALIZER_VERSION,
        "execution_family": SUPPORTED_EXECUTION_FAMILY,
        "operation": SUPPORTED_OPERATION,
    }
    derived_hash = candidate_semantic_hash(derived)
    derived["candidate_hash"] = derived_hash
    status = GEOMETRY_REALIZATION_STATUS_REALIZED_WITH_WARNINGS if warnings else GEOMETRY_REALIZATION_STATUS_REALIZED
    token = hashlib.sha256(f"{parent_hash}|{strategy.strategy_id}|{delta_fingerprint}".encode("utf-8")).hexdigest()[:16]
    preserved = tuple(sorted(set(by_id) - {target_id, donor_id}))
    result = GeometryRealizationResult(
        realization_id=f"realization:{token}",
        strategy_id=strategy.strategy_id,
        parent_candidate_id=parent_id,
        derived_candidate_id=derived_id,
        status=status,
        affected_entities=tuple(sorted((target_id, donor_id))),
        geometry_changes=tuple(deltas),
        preserved_entities=preserved,
        applied_operations=(SUPPORTED_OPERATION,),
        rejected_operations=(),
        constraint_checks=tuple(constraint_checks),
        geometry_checks=tuple(geometry_checks),
        required_downstream_rechecks=_stable_tuple(rechecks),
        warnings=_stable_tuple(warnings),
        failures=(),
        parent_hash=parent_hash,
        derived_hash=derived_hash,
        provenance={
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01F-A",
            "realizer": REALIZER_VERSION,
            "commit": True,
            "parent_unchanged": True,
            "execution_family": SUPPORTED_EXECUTION_FAMILY,
            "operation": SUPPORTED_OPERATION,
        },
    )
    return derived, result


__all__ = [
    "REALIZER_VERSION",
    "SUPPORTED_STRATEGY_TYPE",
    "SUPPORTED_EXECUTION_FAMILY",
    "SUPPORTED_OPERATION",
    "candidate_semantic_hash",
    "realize_selected_space_geometry_strategy",
]
