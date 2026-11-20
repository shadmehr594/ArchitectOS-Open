"""Constraint-preserving declarative planning for architectural changes.

This 01C planner consumes an already interpreted intent, its read-only impact,
and a semantic plan snapshot.  It describes *what* a later phase may attempt.
It does not interpret dialogue or produce executable spatial modifications.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeIntent,
    DeclarativeChangePlan,
    DesignChangeImpact,
    PLANNING_STATUS_GEOMETRY_DEPENDENT,
    PLANNING_STATUS_INSUFFICIENT_EVIDENCE,
    PLANNING_STATUS_PLANNABLE,
    PLANNING_STATUS_PLANNABLE_WITH_PREREQUISITES,
    PLANNING_STATUS_REJECTED_BY_CONSTRAINT,
    PLANNING_STATUS_SITE_DEPENDENT,
)


def _sorted(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if isinstance(value, str) and value}))


def _semantic_name(entity_id: str) -> str:
    return entity_id.split(":", 1)[-1]


def _classify(intent: ArchitecturalChangeIntent) -> str:
    tokens = {
        intent.change_type.lower(),
        (intent.direction or "").lower(),
        (intent.preference or "").lower(),
        *(objective.lower() for objective in intent.soft_objectives),
    }
    if any("daylight" in token or "window" in token for token in tokens):
        return "daylight"
    if intent.change_type.lower() == "change_relation" or any(
        token in {"closer", "proximity", "adjacency"} for token in tokens
    ):
        return "relation"
    if intent.change_type.lower() == "resize_space" or any(
        token in {"increase", "decrease", "larger_area", "smaller_area"}
        for token in tokens
    ):
        return "resize"
    return "generic"


def _availability(snapshot: Mapping[str, Any], name: str) -> bool:
    direct = snapshot.get(f"{name}_available")
    if isinstance(direct, bool):
        return direct
    status = snapshot.get(f"{name}_status")
    if isinstance(status, Mapping):
        state = status.get("state")
    else:
        state = status
    return isinstance(state, str) and state.lower() in {
        "available", "complete", "resolved", "verified",
    }


def _records(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        values = value.values()
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        return ()
    return tuple(item for item in values if isinstance(item, Mapping))


def _hard_conflicts(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    conflicts = []
    for record in _records(snapshot.get("constraint_conflicts")) + _records(
        snapshot.get("hard_constraint_conflicts")
    ):
        severity = str(record.get("severity", "hard")).lower()
        status = str(record.get("status", "active")).lower()
        protected = record.get("protected") is True
        if (severity in {"hard", "critical"} or protected) and status in {
            "active", "conflict", "violated", "unresolved",
        }:
            conflict_id = record.get("constraint_id") or record.get("id") or record.get("reason")
            if isinstance(conflict_id, str) and conflict_id:
                conflicts.append(conflict_id)
    return _sorted(conflicts)


def plan_architectural_change(
    intent: ArchitecturalChangeIntent,
    impact: DesignChangeImpact,
    snapshot: Mapping[str, Any],
) -> DeclarativeChangePlan:
    """Build a stable semantic plan without modifying any input value."""
    if not isinstance(intent, ArchitecturalChangeIntent):
        raise ValueError("intent must be ArchitecturalChangeIntent")
    if not isinstance(impact, DesignChangeImpact):
        raise ValueError("impact must be DesignChangeImpact")
    if not isinstance(snapshot, Mapping):
        raise ValueError("snapshot must be a mapping")
    if impact.change_intent_id != intent.change_intent_id:
        raise ValueError("impact and intent identifiers must match")

    kind = _classify(intent)
    targets = _sorted(intent.targets)
    names = tuple(_semantic_name(target) for target in intent.targets)
    operations: set[str] = set()
    preserves = set(intent.preserve_constraints)
    prerequisites: set[str] = set()
    rejection_conditions: set[str] = set()
    rechecks = set(impact.required_rechecks)
    deferred: set[str] = set()
    reasons: set[str] = set()

    if kind == "resize":
        direction = "increase" if (intent.direction or "").lower() == "increase" else "adjust"
        operations.add(f"{direction}_space_area({names[0]})")
        operations.update({"preserve_circulation_continuity", "reevaluate_openings"})
        preserves.update({"living_usability", "circulation_continuity", "target_access"})
        prerequisites.update({"geometry_availability", "adjacency_availability"})
        rejection_conditions.update({
            "insufficient_transferable_area", "circulation_break",
            "protected_constraint_violation",
        })
        rechecks.update({"area_tradeoff", "adjacency", "access", "circulation", "openings"})
    elif kind == "relation" and len(names) >= 2:
        operations.update({
            f"strengthen_adjacency({names[0]},{names[1]})",
            "reevaluate_privacy", "reevaluate_access", "preserve_circulation_continuity",
        })
        preserves.update({"circulation_continuity", "privacy", "target_access"})
        prerequisites.update({"topology_availability", "geometry_availability"})
        rejection_conditions.update({
            "circulation_break", "privacy_violation", "protected_constraint_violation",
        })
        rechecks.update({"adjacency", "topology", "privacy", "access", "circulation"})
    elif kind == "daylight":
        operations.update({
            f"improve_daylight({names[0]})",
            f"identify_window_opportunity({names[0]})",
            "reevaluate_privacy",
        })
        preserves.update({"privacy", "circulation_continuity"})
        prerequisites.add("daylight_evidence_availability")
        deferred.update({"facade_evidence", "site_orientation_evidence"})
        rejection_conditions.update({
            "facade_opening_privacy_conflict", "protected_constraint_violation",
        })
        rechecks.update({"windows_daylight", "frontage", "privacy", "site_orientation"})
    else:
        operations.add(f"reevaluate_change_scope({','.join(names)})")
        prerequisites.add("supported_intent_semantics")
        rejection_conditions.add("unresolved_change_scope")
        reasons.add("intent_kind_not_supported_by_declarative_rules")

    blockers = _hard_conflicts(snapshot)
    missing_target_evidence = (
        impact.feasibility_status.upper() in {"UNKNOWN", "NOT_ASSESSED"}
        or "missing_target_evidence" in impact.risk_flags
        or "target_entities_not_found_in_snapshot" in impact.feasibility_reasons
    )
    if blockers:
        status = PLANNING_STATUS_REJECTED_BY_CONSTRAINT
        reasons.update(f"hard_constraint_conflict:{item}" for item in blockers)
    elif missing_target_evidence:
        status = PLANNING_STATUS_INSUFFICIENT_EVIDENCE
        reasons.add("target_evidence_missing")
    elif kind == "daylight" and not (
        snapshot.get("orientation") or snapshot.get("site_orientation")
    ):
        status = PLANNING_STATUS_SITE_DEPENDENT
        reasons.add("site_orientation_evidence_missing")
    else:
        unavailable = {
            requirement
            for requirement in prerequisites
            if requirement.endswith("_availability")
            and not _availability(snapshot, requirement.removesuffix("_availability"))
        }
        if "geometry_availability" in unavailable:
            status = PLANNING_STATUS_GEOMETRY_DEPENDENT
            reasons.add("geometry_evidence_missing")
        elif unavailable or any(
            not requirement.endswith("_availability")
            for requirement in prerequisites
        ):
            status = PLANNING_STATUS_PLANNABLE_WITH_PREREQUISITES
            reasons.update(f"prerequisite_pending:{item}" for item in unavailable)
        else:
            status = PLANNING_STATUS_PLANNABLE
            reasons.add("semantic_plan_ready")

    evidence = set(impact.evidence)
    evidence.update(f"impact_status:{impact.feasibility_status}")
    evidence.update(f"target:{target}" for target in targets)
    return DeclarativeChangePlan(
        plan_id=f"declarative-plan:{intent.change_intent_id}",
        intent_id=intent.change_intent_id,
        proposed_operations=_sorted(operations),
        target_entities=targets,
        preserve_constraints=_sorted(preserves),
        prerequisites=_sorted(prerequisites),
        rejection_conditions=_sorted(rejection_conditions),
        required_rechecks=_sorted(rechecks),
        deferred_dependencies=_sorted(deferred),
        planning_status=status,
        planning_reasons=_sorted(reasons),
        evidence=_sorted(evidence),
        provenance={
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01C",
            "planner": "architectural_change_planner_v1",
            "geometry_changed": False,
            "source_impact_intent_id": impact.change_intent_id,
        },
    )


__all__ = ["plan_architectural_change"]
