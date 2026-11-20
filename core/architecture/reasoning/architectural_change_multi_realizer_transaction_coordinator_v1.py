"""01F-D atomic coordinator for the existing 01F-A/B/C realizers only."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
import hashlib
import json
from typing import Any, Mapping, Sequence

from shapely.geometry import LineString, Polygon

from core.architecture.contracts.architectural_change_contracts_v1 import (
    AdjacencyRealizationResult,
    ArchitecturalChangeStrategy,
    ExecutionReadinessResult,
    GeometryRealizationResult,
    MultiRealizerTransactionPlan,
    MultiRealizerTransactionResult,
    OpeningAccessRealizationResult,
    TransactionStepResult,
    TRANSACTION_STATUS_COMMITTED,
    TRANSACTION_STATUS_COMMITTED_WITH_WARNINGS,
    TRANSACTION_STATUS_FAILED,
    TRANSACTION_STATUS_REJECTED_CONSTRAINT,
    TRANSACTION_STATUS_REJECTED_DEPENDENCY_ORDER,
    TRANSACTION_STATUS_REJECTED_STEP_FAILURE,
    TRANSACTION_STATUS_STALE_PARENT,
    TRANSACTION_STATUS_UNSUPPORTED_STRATEGY_SEQUENCE,
)
from core.architecture.reasoning.architectural_change_adjacency_topology_realizer_v1 import (
    SUPPORTED_STRATEGY_TYPES as TOPOLOGY_STRATEGY_TYPES,
    realize_selected_adjacency_topology_strategy,
)
from core.architecture.reasoning.architectural_change_opening_access_realizer_v1 import (
    SUPPORTED_OPERATIONS as OPENING_OPERATIONS,
    SUPPORTED_STRATEGY_TYPES as OPENING_STRATEGY_TYPES,
    realize_selected_opening_access_strategy,
)
from core.architecture.reasoning.architectural_change_space_geometry_realizer_v1 import (
    candidate_semantic_hash,
    realize_selected_space_geometry_strategy,
)


COORDINATOR_VERSION = "architectural_change_multi_realizer_transaction_coordinator_v1"
SUPPORTED_REALIZER_STEPS = (
    "SPACE_BOUNDARY_REALIZATION",
    "ADJACENCY_TOPOLOGY_REALIZATION",
    "OPENING_ACCESS_REALIZATION",
)
_SUCCESS_STATUSES = frozenset({"REALIZED", "REALIZED_WITH_WARNINGS"})
_EPSILON = 1e-7


def _json_value(value: Any) -> Any:
    if is_dataclass(value):
        return {item.name: _json_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return deepcopy(value)


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _identity(candidate: Mapping[str, Any]) -> tuple[str | None, str | None]:
    candidate_id = candidate.get("candidate_id") or candidate.get("id")
    candidate_version = candidate.get("candidate_version") or candidate.get("version")
    return (
        str(candidate_id) if candidate_id is not None else None,
        str(candidate_version) if candidate_version is not None else None,
    )


def _route_supported(strategy: ArchitecturalChangeStrategy, step: str) -> bool:
    if step == "SPACE_BOUNDARY_REALIZATION":
        return strategy.strategy_type == "ADJACENT_AREA_TRANSFER"
    if step == "ADJACENCY_TOPOLOGY_REALIZATION":
        return strategy.strategy_type in TOPOLOGY_STRATEGY_TYPES
    if step == "OPENING_ACCESS_REALIZATION":
        if strategy.strategy_type not in OPENING_STRATEGY_TYPES:
            return False
        sources = []
        if isinstance(strategy.provenance, Mapping):
            sources.extend((
                strategy.provenance.get("opening_access_realization"),
                strategy.provenance.get("execution_evidence"),
            ))
        operation = next(
            (item.get("operation") for item in sources if isinstance(item, Mapping)),
            strategy.strategy_type,
        )
        return operation in OPENING_OPERATIONS
    return False


def _deltas(result: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(result, GeometryRealizationResult):
        values = result.geometry_changes
    elif isinstance(result, AdjacencyRealizationResult):
        values = result.topology_changes
    elif isinstance(result, OpeningAccessRealizationResult):
        values = result.opening_access_changes
    else:
        return ()
    return tuple(_json_value(value) for value in values)


def _checks(result: Any) -> tuple[Mapping[str, Any], ...]:
    collected = []
    for name in (
        "constraint_checks", "geometry_checks", "topology_checks",
        "access_checks", "circulation_checks",
    ):
        collected.extend(getattr(result, name, ()))
    return tuple(deepcopy(item) for item in collected)


def _result(
    plan: MultiRealizerTransactionPlan,
    status: str,
    *,
    step_results: tuple[TransactionStepResult, ...] = (),
    aggregate_deltas: tuple[Mapping[str, Any], ...] = (),
    final_candidate: Mapping[str, Any] | None = None,
    rollback_reason: str | None = None,
    failed_step_index: int | None = None,
    failed_step_id: str | None = None,
    invariant_checks: tuple[Mapping[str, Any], ...] = (),
    warnings: tuple[str, ...] = (),
    failures: tuple[str, ...] = (),
) -> MultiRealizerTransactionResult:
    committed = status in {TRANSACTION_STATUS_COMMITTED, TRANSACTION_STATUS_COMMITTED_WITH_WARNINGS}
    final_id, final_version = _identity(final_candidate or {})
    return MultiRealizerTransactionResult(
        transaction_id=plan.transaction_id,
        parent_candidate_id=plan.parent_candidate_id,
        parent_candidate_hash=plan.parent_candidate_hash,
        parent_candidate_version=plan.parent_candidate_version,
        ordered_strategy_ids=plan.ordered_strategy_ids,
        ordered_realizer_steps=plan.ordered_realizer_steps,
        dependency_edges=plan.dependency_edges,
        step_results=step_results,
        aggregate_deltas=aggregate_deltas,
        final_candidate_id=final_id if committed else None,
        final_candidate_hash=(str(final_candidate.get("candidate_hash")) if committed and final_candidate else None),
        final_candidate_version=final_version if committed else None,
        commit_status=status,
        rollback_reason=rollback_reason,
        failed_step_index=failed_step_index,
        failed_step_id=failed_step_id,
        invariant_checks=invariant_checks,
        warnings=warnings,
        failures=failures,
        provenance={
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01F-D",
            "coordinator": COORDINATOR_VERSION,
            "commit": committed,
            "single_final_commit": committed,
            "intermediate_candidates_committed": False,
            "parent_unchanged": True,
        },
    )


def _preflight_failure(
    plan: MultiRealizerTransactionPlan, status: str, reason: str,
    *, failed_step_index: int | None = None, failed_step_id: str | None = None,
) -> tuple[None, MultiRealizerTransactionResult]:
    return None, _result(
        plan, status, rollback_reason=reason,
        failed_step_index=failed_step_index, failed_step_id=failed_step_id,
        failures=(reason,),
    )


def _aggregate_invariants(
    parent: Mapping[str, Any], candidate: Mapping[str, Any],
    required_constraints: set[str], parent_document: str, parent_hash: str,
) -> tuple[Mapping[str, Any], ...]:
    checks: list[Mapping[str, Any]] = []
    parent_unchanged = _canonical(parent) == parent_document and candidate_semantic_hash(parent) == parent_hash
    checks.append({"check": "original_parent_byte_semantic_equivalence", "passed": parent_unchanged})

    parent_hard = _json_value(parent.get("hard_constraints", ()))
    parent_protected = _json_value(parent.get("protected_constraints", ()))
    constraints_preserved = (
        _json_value(candidate.get("hard_constraints", ())) == parent_hard
        and _json_value(candidate.get("protected_constraints", ())) == parent_protected
    )
    checks.append({
        "check": "protected_and_hard_constraints_preserved",
        "passed": constraints_preserved,
        "required_constraints": sorted(required_constraints),
    })

    polygons: dict[str, Polygon] = {}
    polygon_floors: dict[str, str] = {}
    geometry_failures: list[str] = []
    roots = candidate.get("space_boundary_graphs")
    if not isinstance(roots, Mapping):
        geometry_failures.append("space_boundary_graphs_missing")
    else:
        for floor, graph in roots.items():
            if not isinstance(graph, Mapping):
                geometry_failures.append(f"invalid_space_graph:{floor}")
                continue
            for record in graph.get("spaces", ()):
                try:
                    space_id = str(record["space_id"])
                    polygon = Polygon(record["polygon"])
                    if space_id in polygons or polygon.is_empty or not polygon.is_valid or not polygon.is_simple or polygon.area <= _EPSILON:
                        geometry_failures.append(f"invalid_or_duplicate_space:{space_id}")
                    polygons[space_id] = polygon
                    polygon_floors[space_id] = str(floor)
                except (KeyError, TypeError, ValueError):
                    geometry_failures.append(f"invalid_space_record:{floor}")
    ids = sorted(polygons)
    for index, first in enumerate(ids):
        for second in ids[index + 1:]:
            if polygon_floors[first] == polygon_floors[second] and polygons[first].intersection(polygons[second]).area > _EPSILON:
                geometry_failures.append(f"space_overlap:{first}:{second}")
    checks.append({"check": "aggregate_geometry_valid_non_overlapping", "passed": not geometry_failures, "failures": geometry_failures})

    access = candidate.get("access_graph")
    access_failures: list[str] = []
    adjacency: dict[str, set[str]] = {space_id: set() for space_id in polygons}
    edges = access.get("edges", ()) if isinstance(access, Mapping) else ()
    if not isinstance(access, Mapping) or not isinstance(edges, (list, tuple)):
        access_failures.append("canonical_access_graph_missing")
        edges = ()
    opening_by_id: dict[str, Mapping[str, Any]] = {}
    opening_roots = candidate.get("opening_host_graphs", {})
    if isinstance(opening_roots, Mapping):
        for graph in opening_roots.values():
            if isinstance(graph, Mapping):
                for opening in graph.get("openings", ()):
                    if isinstance(opening, Mapping) and opening.get("opening_id"):
                        opening_by_id[str(opening["opening_id"])] = opening
    for edge in edges:
        if not isinstance(edge, Mapping):
            access_failures.append("invalid_access_edge")
            continue
        first, second = str(edge.get("from")), str(edge.get("to"))
        if first not in polygons or second not in polygons:
            access_failures.append(f"access_endpoint_missing:{edge.get('edge_id')}")
            continue
        adjacency[first].add(second)
        adjacency[second].add(first)
        binding = edge.get("opening_binding")
        if binding is not None:
            opening = opening_by_id.get(str(binding))
            if opening is None or {opening.get("side_a"), opening.get("side_b")} != {first, second}:
                access_failures.append(f"opening_binding_inconsistent:{edge.get('edge_id')}")
            else:
                raw_line = opening.get("centerline") or opening.get("threshold")
                try:
                    opening_line = LineString(raw_line)
                    shared = polygons[first].boundary.intersection(polygons[second].boundary)
                    if (
                        opening_line.is_empty or opening_line.length <= _EPSILON
                        or shared.is_empty
                        or opening_line.difference(shared.buffer(_EPSILON)).length > _EPSILON
                    ):
                        access_failures.append(f"opening_geometry_not_on_current_shared_boundary:{edge.get('edge_id')}")
                except (TypeError, ValueError):
                    access_failures.append(f"opening_geometry_invalid:{edge.get('edge_id')}")
    required_ids = sorted(
        space_id for space_id in polygons
        if any(
            isinstance(record, Mapping) and str(record.get("space_id")) == space_id and record.get("required", True)
            for graph in (roots.values() if isinstance(roots, Mapping) else ())
            for record in (graph.get("spaces", ()) if isinstance(graph, Mapping) else ())
        )
    )
    if required_ids:
        reached, frontier = set(), [required_ids[0]]
        while frontier:
            current = frontier.pop()
            if current in reached:
                continue
            reached.add(current)
            frontier.extend(sorted(adjacency.get(current, set()) - reached))
        missing = sorted(set(required_ids) - reached)
        if missing:
            access_failures.append("required_access_disconnected:" + ",".join(missing))
    checks.append({"check": "aggregate_access_circulation_and_opening_binding", "passed": not access_failures, "failures": access_failures})
    return tuple(checks)


def execute_multi_realizer_transaction(
    plan: MultiRealizerTransactionPlan,
    strategies: Sequence[ArchitecturalChangeStrategy],
    readiness_by_strategy: Mapping[str, ExecutionReadinessResult],
    parent_candidate: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, MultiRealizerTransactionResult]:
    """Execute a selected ordered bundle atomically and publish one final child."""
    if not isinstance(plan, MultiRealizerTransactionPlan):
        raise ValueError("plan must be MultiRealizerTransactionPlan")
    if not isinstance(parent_candidate, Mapping):
        raise ValueError("parent_candidate must be a mapping")
    if not isinstance(readiness_by_strategy, Mapping):
        raise ValueError("readiness_by_strategy must be a mapping")
    if any(not isinstance(item, ArchitecturalChangeStrategy) for item in strategies):
        raise ValueError("strategies must contain ArchitecturalChangeStrategy values")

    parent_document = _canonical(parent_candidate)
    actual_parent_hash = candidate_semantic_hash(parent_candidate)
    parent_id, parent_version = _identity(parent_candidate)
    stored_hash = parent_candidate.get("candidate_hash") or parent_candidate.get("hash")
    if (
        parent_id != plan.parent_candidate_id
        or parent_version != plan.parent_candidate_version
        or actual_parent_hash != plan.parent_candidate_hash
        or (stored_hash is not None and str(stored_hash) != actual_parent_hash)
    ):
        return _preflight_failure(plan, TRANSACTION_STATUS_STALE_PARENT, "parent_identity_version_or_hash_mismatch")

    supplied_ids = tuple(item.strategy_id for item in strategies)
    if supplied_ids != plan.ordered_strategy_ids:
        return _preflight_failure(plan, TRANSACTION_STATUS_UNSUPPORTED_STRATEGY_SEQUENCE, "strategy_bundle_does_not_match_declared_order")
    if len(set(zip(plan.ordered_strategy_ids, plan.ordered_realizer_steps))) != len(plan.ordered_strategy_ids):
        return _preflight_failure(plan, TRANSACTION_STATUS_UNSUPPORTED_STRATEGY_SEQUENCE, "duplicate_strategy_realizer_application")
    positions = {strategy_id: index for index, strategy_id in enumerate(plan.ordered_strategy_ids)}
    for prerequisite, dependent in plan.dependency_edges:
        if prerequisite not in positions or dependent not in positions or positions[prerequisite] >= positions[dependent]:
            return _preflight_failure(plan, TRANSACTION_STATUS_REJECTED_DEPENDENCY_ORDER, f"invalid_dependency_order:{prerequisite}->{dependent}")
    for index, (strategy, step) in enumerate(zip(strategies, plan.ordered_realizer_steps)):
        if step not in SUPPORTED_REALIZER_STEPS or not _route_supported(strategy, step):
            return _preflight_failure(
                plan, TRANSACTION_STATUS_UNSUPPORTED_STRATEGY_SEQUENCE,
                f"unsupported_strategy_realizer_step:{strategy.strategy_id}:{step}",
                failed_step_index=index, failed_step_id=strategy.strategy_id,
            )
        readiness = readiness_by_strategy.get(strategy.strategy_id)
        if not isinstance(readiness, ExecutionReadinessResult) or readiness.plan_id != strategy.plan_id:
            return _preflight_failure(
                plan, TRANSACTION_STATUS_REJECTED_CONSTRAINT,
                f"missing_or_mismatched_readiness:{strategy.strategy_id}",
                failed_step_index=index, failed_step_id=strategy.strategy_id,
            )

    working = deepcopy(dict(parent_candidate))
    step_results: list[TransactionStepResult] = []
    aggregate_deltas: list[Mapping[str, Any]] = []
    all_warnings: set[str] = set()
    carried_constraints: set[str] = set()

    for index, (strategy, step) in enumerate(zip(strategies, plan.ordered_realizer_steps)):
        current_id, current_version = _identity(working)
        current_hash = candidate_semantic_hash(working)
        effective_strategy = replace(
            strategy,
            preserved_constraints=tuple(sorted(set(strategy.preserved_constraints) | carried_constraints)),
        )
        readiness = readiness_by_strategy[strategy.strategy_id]
        effective_readiness = replace(
            readiness,
            preservation_requirements=tuple(sorted(set(readiness.preservation_requirements) | carried_constraints)),
        )
        kwargs = {
            "expected_parent_id": str(current_id),
            "expected_parent_version": str(current_version),
            "expected_parent_hash": current_hash,
        }
        try:
            if step == "SPACE_BOUNDARY_REALIZATION":
                derived, realization = realize_selected_space_geometry_strategy(effective_strategy, effective_readiness, working, **kwargs)
            elif step == "ADJACENCY_TOPOLOGY_REALIZATION":
                derived, realization = realize_selected_adjacency_topology_strategy(effective_strategy, effective_readiness, working, **kwargs)
            else:
                derived, realization = realize_selected_opening_access_strategy(effective_strategy, effective_readiness, working, **kwargs)
        except Exception as exc:  # defensive transaction boundary; never publish local state
            return None, _result(
                plan, TRANSACTION_STATUS_FAILED,
                step_results=tuple(step_results), aggregate_deltas=tuple(aggregate_deltas),
                rollback_reason=f"realizer_exception:{type(exc).__name__}",
                failed_step_index=index, failed_step_id=strategy.strategy_id,
                failures=(f"realizer_exception:{type(exc).__name__}",),
            )

        deltas = _deltas(realization)
        step_result = TransactionStepResult(
            step_index=index,
            strategy_id=strategy.strategy_id,
            realizer_step=step,
            realization_result_type=type(realization).__name__,
            realization_status=realization.status,
            parent_candidate_id=str(current_id),
            parent_candidate_hash=current_hash,
            parent_candidate_version=str(current_version),
            derived_candidate_id=realization.derived_candidate_id,
            derived_candidate_hash=realization.derived_hash,
            derived_candidate_version=(_identity(derived)[1] if derived is not None else None),
            deltas=deltas,
            invariant_checks=_checks(realization),
            warnings=tuple(realization.warnings),
            failures=tuple(realization.failures),
            provenance={
                "transaction_id": plan.transaction_id,
                "transaction_local": True,
                "published": False,
                "realizer_provenance": _json_value(realization.provenance),
                "inherited_preserved_constraints": sorted(carried_constraints),
            },
        )
        step_results.append(step_result)
        if derived is None or realization.status not in _SUCCESS_STATUSES:
            if realization.status == "STALE_PARENT":
                status = TRANSACTION_STATUS_STALE_PARENT
            elif realization.status == "REJECTED_CONSTRAINT":
                status = TRANSACTION_STATUS_REJECTED_CONSTRAINT
            elif realization.status == "UNSUPPORTED_STRATEGY":
                status = TRANSACTION_STATUS_UNSUPPORTED_STRATEGY_SEQUENCE
            else:
                status = TRANSACTION_STATUS_REJECTED_STEP_FAILURE
            reason = f"step_failed:{strategy.strategy_id}:{realization.status}"
            return None, _result(
                plan, status, step_results=tuple(step_results),
                aggregate_deltas=tuple(aggregate_deltas), rollback_reason=reason,
                failed_step_index=index, failed_step_id=strategy.strategy_id,
                warnings=tuple(sorted(all_warnings | set(realization.warnings))),
                failures=tuple(realization.failures) or (reason,),
            )
        aggregate_deltas.extend(deltas)
        all_warnings.update(realization.warnings)
        carried_constraints.update(effective_strategy.preserved_constraints)
        carried_constraints.update(effective_readiness.preservation_requirements)
        working = derived

    invariant_checks = _aggregate_invariants(
        parent_candidate, working, carried_constraints, parent_document, actual_parent_hash,
    )
    failed_checks = tuple(str(item.get("check")) for item in invariant_checks if not item.get("passed"))
    if failed_checks:
        return None, _result(
            plan, TRANSACTION_STATUS_REJECTED_CONSTRAINT,
            step_results=tuple(step_results), aggregate_deltas=tuple(aggregate_deltas),
            rollback_reason="aggregate_invariant_failure",
            invariant_checks=invariant_checks, warnings=tuple(sorted(all_warnings)),
            failures=failed_checks,
        )

    fingerprint_payload = {
        "transaction_id": plan.transaction_id,
        "parent_hash": actual_parent_hash,
        "ordered_strategy_ids": plan.ordered_strategy_ids,
        "ordered_realizer_steps": plan.ordered_realizer_steps,
        "dependency_edges": plan.dependency_edges,
        "step_result_hashes": tuple(item.derived_candidate_hash for item in step_results),
        "aggregate_deltas": aggregate_deltas,
    }
    fingerprint = hashlib.sha256(
        json.dumps(_json_value(fingerprint_payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    final_candidate = deepcopy(working)
    final_candidate["parent_candidate_id"] = plan.parent_candidate_id
    final_candidate["candidate_id"] = f"{plan.parent_candidate_id}:transaction:{fingerprint[:16]}"
    final_candidate["candidate_version"] = f"{plan.parent_candidate_version}+01f-d.{fingerprint[:12]}"
    final_candidate["derivation"] = {
        "transaction_id": plan.transaction_id,
        "coordinator": COORDINATOR_VERSION,
        "lineage_root_parent_candidate_id": plan.parent_candidate_id,
        "lineage_root_parent_hash": plan.parent_candidate_hash,
        "lineage_root_parent_version": plan.parent_candidate_version,
        "ordered_strategy_ids": list(plan.ordered_strategy_ids),
        "ordered_realizer_steps": list(plan.ordered_realizer_steps),
        "dependency_edges": [list(edge) for edge in plan.dependency_edges],
        "realizer_results": [
            {
                "step_index": item.step_index,
                "strategy_id": item.strategy_id,
                "realizer_step": item.realizer_step,
                "result_type": item.realization_result_type,
                "result_status": item.realization_status,
                "transaction_local_derived_hash": item.derived_candidate_hash,
            }
            for item in step_results
        ],
        "single_final_commit": True,
        "intermediate_candidates_committed": False,
    }
    final_candidate.pop("candidate_hash", None)
    final_candidate["candidate_hash"] = candidate_semantic_hash(final_candidate)
    status = TRANSACTION_STATUS_COMMITTED_WITH_WARNINGS if all_warnings else TRANSACTION_STATUS_COMMITTED
    return final_candidate, _result(
        plan, status, step_results=tuple(step_results),
        aggregate_deltas=tuple(aggregate_deltas), final_candidate=final_candidate,
        invariant_checks=invariant_checks, warnings=tuple(sorted(all_warnings)),
    )


__all__ = [
    "COORDINATOR_VERSION",
    "SUPPORTED_REALIZER_STEPS",
    "execute_multi_realizer_transaction",
]
