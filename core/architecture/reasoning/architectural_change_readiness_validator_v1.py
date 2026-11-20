"""Read-only validation and execution-readiness gate for declarative plans.

The validator classifies evidence already present in a plan and constraint
snapshot.  It never interprets proposed operations or changes spatial state.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from core.architecture.contracts.architectural_change_contracts_v1 import (
    DeclarativeChangePlan,
    ExecutionReadinessResult,
    PLANNING_STATUS_GEOMETRY_DEPENDENT,
    PLANNING_STATUS_INSUFFICIENT_EVIDENCE,
    PLANNING_STATUS_REJECTED_BY_CONSTRAINT,
    PLANNING_STATUS_SITE_DEPENDENT,
    READINESS_STATUS_BLOCKED_CONSTRAINT,
    READINESS_STATUS_BLOCKED_GEOMETRY,
    READINESS_STATUS_BLOCKED_SITE,
    READINESS_STATUS_INSUFFICIENT_EVIDENCE,
    READINESS_STATUS_READY,
    READINESS_STATUS_READY_WITH_PREREQUISITES,
)


_RESOLVED_STATES = {"available", "complete", "resolved", "satisfied", "verified"}
_UNRESOLVED_STATES = {"blocked", "missing", "pending", "unavailable", "unresolved"}


def _sorted(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if isinstance(value, str) and value}))


def _text_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(item for item in value if isinstance(item, str) and item)
    return ()


def _records(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        values = value.values()
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        return ()
    return tuple(item for item in values if isinstance(item, Mapping))


def _state_is_resolved(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, Mapping):
        value = value.get("state", value.get("status"))
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _RESOLVED_STATES:
            return True
        if normalized in _UNRESOLVED_STATES:
            return False
    return None


def _dependency_resolved(snapshot: Mapping[str, Any], dependency: str) -> bool:
    resolved = set(_text_values(snapshot.get("resolved_dependencies")))
    unresolved = set(_text_values(snapshot.get("unresolved_dependencies")))
    if dependency in resolved:
        return True
    if dependency in unresolved:
        return False

    statuses = snapshot.get("dependency_status")
    if isinstance(statuses, Mapping) and dependency in statuses:
        state = _state_is_resolved(statuses[dependency])
        if state is not None:
            return state

    candidates = [dependency, f"{dependency}_status"]
    if dependency.endswith("_availability"):
        base = dependency.removesuffix("_availability")
        candidates.extend((f"{base}_available", f"{base}_status", base))
    for key in candidates:
        if key in snapshot:
            state = _state_is_resolved(snapshot[key])
            if state is not None:
                return state
    return False


def _hard_conflicts(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    conflicts: set[str] = set(_text_values(snapshot.get("hard_constraint_conflicts")))
    conflicts.update(_text_values(snapshot.get("protected_constraint_conflicts")))
    for record in _records(snapshot.get("constraint_conflicts")) + _records(
        snapshot.get("hard_constraint_conflicts")
    ) + _records(snapshot.get("protected_constraint_conflicts")):
        severity = str(record.get("severity", "hard")).lower()
        status = str(record.get("status", "active")).lower()
        protected = record.get("protected") is True
        if (severity in {"hard", "critical"} or protected) and status in {
            "active", "conflict", "unresolved", "violated",
        }:
            identity = record.get("constraint_id") or record.get("id") or record.get("reason")
            if isinstance(identity, str) and identity:
                conflicts.add(identity)
    for record in _records(snapshot.get("protected_constraints")):
        status = str(record.get("status", "active")).lower()
        if status not in {"conflict", "unresolved", "violated"}:
            continue
        identity = record.get("constraint_id") or record.get("id") or record.get("reason")
        if isinstance(identity, str) and identity:
            conflicts.add(identity)
    return _sorted(conflicts)


def _target_ids(snapshot: Mapping[str, Any]) -> tuple[set[str], bool]:
    identifiers: set[str] = set()
    has_collection = False
    for key in ("nodes", "spaces", "rooms", "entities"):
        if key not in snapshot:
            continue
        has_collection = True
        for record in _records(snapshot.get(key)):
            for name in ("node_id", "space_id", "room_id", "entity_id", "id", "name"):
                value = record.get(name)
                if isinstance(value, str) and value:
                    identifiers.add(value.lower())
                    identifiers.add(value.split(":", 1)[-1].lower())
    return identifiers, has_collection


def _unresolved_targets(
    plan: DeclarativeChangePlan,
    snapshot: Mapping[str, Any],
) -> tuple[str, ...]:
    unresolved = set(_text_values(snapshot.get("unresolved_targets")))
    target_evidence = snapshot.get("target_evidence")
    known_ids, has_collection = _target_ids(snapshot)
    for target in plan.target_entities:
        if isinstance(target_evidence, Mapping) and target in target_evidence:
            if _state_is_resolved(target_evidence[target]) is not True:
                unresolved.add(target)
        elif has_collection:
            normalized = target.lower()
            if normalized not in known_ids and normalized.split(":", 1)[-1] not in known_ids:
                unresolved.add(target)
    return _sorted(unresolved)


def _is_site_dependency(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in ("site", "orientation", "facade"))


def _is_geometry_dependency(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in ("geometry", "topology", "adjacency"))


def validate_declarative_plan_readiness(
    plan: DeclarativeChangePlan,
    snapshot: Mapping[str, Any],
) -> ExecutionReadinessResult:
    """Classify whether ``plan`` may enter strategy work without mutating inputs."""
    if not isinstance(plan, DeclarativeChangePlan):
        raise ValueError("plan must be DeclarativeChangePlan")
    if not isinstance(snapshot, Mapping):
        raise ValueError("snapshot must be a mapping")

    dependencies = set(plan.prerequisites) | set(plan.deferred_dependencies)
    unresolved = {item for item in dependencies if not _dependency_resolved(snapshot, item)}
    if plan.planning_status == PLANNING_STATUS_SITE_DEPENDENT and not any(
        _is_site_dependency(item) for item in unresolved
    ):
        unresolved.add("site_orientation_evidence")
    if plan.planning_status == PLANNING_STATUS_GEOMETRY_DEPENDENT and not any(
        _is_geometry_dependency(item) for item in unresolved
    ):
        unresolved.add("geometry_availability")

    conflicts = set(_hard_conflicts(snapshot))
    preservation = set(plan.preserve_constraints)
    preservation.update(_text_values(snapshot.get("preservation_requirements")))
    for record in _records(snapshot.get("protected_constraints")):
        identity = record.get("constraint_id") or record.get("id") or record.get("name")
        if isinstance(identity, str) and identity:
            preservation.add(identity)

    checks = set(plan.required_rechecks)
    checks.update(_text_values(snapshot.get("required_checks_before_execution")))
    evidence = set(plan.evidence)
    evidence.update(_text_values(snapshot.get("validation_evidence")))
    missing_targets = _unresolved_targets(plan, snapshot)
    evidence_state = _state_is_resolved(snapshot.get("evidence_status"))
    insufficient = (
        plan.planning_status == PLANNING_STATUS_INSUFFICIENT_EVIDENCE
        or bool(missing_targets)
        or not plan.evidence
        or evidence_state is False
    )

    site_dependencies = {item for item in unresolved if _is_site_dependency(item)}
    geometry_dependencies = {item for item in unresolved if _is_geometry_dependency(item)}
    other_dependencies = unresolved - site_dependencies - geometry_dependencies
    reasons: set[str] = set()

    if plan.planning_status == PLANNING_STATUS_REJECTED_BY_CONSTRAINT or conflicts:
        status = READINESS_STATUS_BLOCKED_CONSTRAINT
        reasons.update(f"constraint_conflict:{item}" for item in conflicts)
        if plan.planning_status == PLANNING_STATUS_REJECTED_BY_CONSTRAINT:
            reasons.add("plan_rejected_by_constraint")
    elif site_dependencies:
        status = READINESS_STATUS_BLOCKED_SITE
        reasons.update(f"unresolved_site_dependency:{item}" for item in site_dependencies)
    elif geometry_dependencies:
        status = READINESS_STATUS_BLOCKED_GEOMETRY
        reasons.update(f"unresolved_geometry_dependency:{item}" for item in geometry_dependencies)
    elif insufficient:
        status = READINESS_STATUS_INSUFFICIENT_EVIDENCE
        reasons.update(f"unresolved_target:{item}" for item in missing_targets)
        if not plan.evidence or evidence_state is False:
            reasons.add("plan_evidence_insufficient")
        if plan.planning_status == PLANNING_STATUS_INSUFFICIENT_EVIDENCE:
            reasons.add("plan_marked_insufficient_evidence")
    elif other_dependencies:
        status = READINESS_STATUS_READY_WITH_PREREQUISITES
        reasons.update(f"nonblocking_prerequisite:{item}" for item in other_dependencies)
    else:
        status = READINESS_STATUS_READY

    return ExecutionReadinessResult(
        plan_id=plan.plan_id,
        readiness_status=status,
        unresolved_dependencies=_sorted(unresolved),
        constraint_conflicts=_sorted(conflicts),
        preservation_requirements=_sorted(preservation),
        required_checks_before_execution=_sorted(checks),
        rejection_reasons=_sorted(reasons),
        evidence=_sorted(evidence),
        provenance={
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01D",
            "validator": "architectural_change_readiness_validator_v1",
            "source_plan_id": plan.plan_id,
            "spatial_state_changed": False,
        },
    )


__all__ = ["validate_declarative_plan_readiness"]
