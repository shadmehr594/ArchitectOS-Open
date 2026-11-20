"""Deterministic semantic strategy generation for admitted change plans.

This phase compares meaning-level alternatives only.  It consumes a read-only
plan snapshot for constraint evidence and does not invoke any design producer.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeStrategy,
    DeclarativeChangePlan,
    ExecutionReadinessResult,
    READINESS_STATUS_READY,
    READINESS_STATUS_READY_WITH_PREREQUISITES,
    STRATEGY_APPLICABILITY_APPLICABLE,
    STRATEGY_APPLICABILITY_WITH_PREREQUISITES,
    STRATEGY_GENERATION_STATUS_BLOCKED_READINESS,
    STRATEGY_GENERATION_STATUS_GENERATED,
    StrategyGenerationResult,
)


_ADMITTED = {READINESS_STATUS_READY, READINESS_STATUS_READY_WITH_PREREQUISITES}


def _sorted(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if isinstance(value, str) and value}))


def _snapshot_constraints(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    values: set[str] = set()
    for key in ("hard_constraints", "protected_constraints"):
        raw = snapshot.get(key)
        records: Iterable[Any]
        if isinstance(raw, Mapping):
            records = raw.values()
        elif isinstance(raw, (list, tuple, set, frozenset)):
            records = raw
        else:
            records = ()
        for record in records:
            if isinstance(record, str) and record:
                values.add(record)
            elif isinstance(record, Mapping):
                identity = record.get("constraint_id") or record.get("id") or record.get("name")
                if isinstance(identity, str) and identity:
                    values.add(identity)
    return _sorted(values)


def _strategy_kind(plan: DeclarativeChangePlan) -> str:
    operations = " ".join(plan.proposed_operations).lower()
    if "daylight" in operations or "window_opportunity" in operations:
        return "living_daylight"
    if "strengthen_adjacency" in operations or "reevaluate_privacy" in operations:
        return "master_bath_adjacency"
    if "space_area" in operations or "living_usability" in plan.preserve_constraints:
        return "kitchen_resize"
    return "generic_change"


def _templates(kind: str) -> tuple[dict[str, tuple[str, ...] | str], ...]:
    if kind == "kitchen_resize":
        return (
            {
                "type": "ADJACENT_AREA_TRANSFER",
                "actions": ("transfer_adjacent_available_area", "reevaluate_affected_opening_relationships"),
                "tradeoffs": ("adjacent_space_area_and_usability",),
                "impacts": ("increased_kitchen_capacity", "changed_adjacent_space_balance"),
                "risks": ("insufficient_transferable_area", "adjacent_space_usability_reduction"),
                "rechecks": ("living_minimum_usability", "circulation", "access", "openings"),
            },
            {
                "type": "SERVICE_BAND_REALLOCATION",
                "actions": ("reallocate_available_service_band_area", "preserve_public_space_continuity"),
                "tradeoffs": ("service_band_capacity", "service_relationships"),
                "impacts": ("increased_kitchen_service_capacity", "rebalanced_service_band"),
                "risks": ("service_function_conflict", "circulation_pressure"),
                "rechecks": ("living_minimum_usability", "circulation", "access", "service_adjacency"),
            },
            {
                "type": "RELATIONSHIP_RECONFIGURATION",
                "actions": ("reconfigure_kitchen_living_relationship_semantics", "improve_perceived_kitchen_openness"),
                "tradeoffs": ("visual_openness_and_privacy",),
                "impacts": ("perceived_kitchen_enlargement", "changed_public_space_relationship"),
                "risks": ("privacy_reduction", "opening_relationship_conflict"),
                "rechecks": ("living_minimum_usability", "circulation", "access", "privacy"),
            },
        )
    if kind == "master_bath_adjacency":
        return (
            {
                "type": "DIRECT_PRIVATE_RELATIONSHIP",
                "actions": ("strengthen_master_bath_adjacency", "prioritize_private_access_relationship"),
                "tradeoffs": ("private_zone_relationships",),
                "impacts": ("stronger_master_bath_adjacency", "clearer_private_access"),
                "risks": ("privacy_transition_conflict", "circulation_overlap"),
                "rechecks": ("privacy", "circulation", "access", "adjacency"),
            },
            {
                "type": "PRIVATE_ZONE_MEDIATED_RELATIONSHIP",
                "actions": ("strengthen_adjacency_through_private_zone", "preserve_separated_access_semantics"),
                "tradeoffs": ("adjacency_strength_and_access_separation",),
                "impacts": ("improved_private_proximity", "retained_access_separation"),
                "risks": ("private_zone_congestion", "weakened_directness"),
                "rechecks": ("privacy", "circulation", "access", "topology"),
            },
        )
    if kind == "living_daylight":
        return (
            {
                "type": "DAYLIGHT_EXPOSURE_RELATIONSHIP",
                "actions": ("improve_living_daylight_exposure_relationship",),
                "tradeoffs": ("daylight_exposure_and_privacy",),
                "impacts": ("improved_living_daylight_opportunity",),
                "risks": ("privacy_exposure_conflict",),
                "rechecks": ("daylight", "privacy", "site_orientation"),
            },
            {
                "type": "FACADE_OPPORTUNITY_RELATIONSHIP",
                "actions": ("prioritize_living_facade_opportunity", "identify_opening_opportunity_semantics"),
                "tradeoffs": ("facade_opportunity_and_program_relationships",),
                "impacts": ("stronger_living_facade_relationship",),
                "risks": ("facade_constraint_conflict",),
                "rechecks": ("daylight", "facade", "privacy", "site_orientation"),
            },
        )
    return ({
        "type": "SEMANTIC_SCOPE_REEVALUATION",
        "actions": ("reevaluate_supported_change_relationships",),
        "tradeoffs": ("change_scope_and_preservation_requirements",),
        "impacts": ("clarified_semantic_change_path",),
        "risks": ("unsupported_semantic_scope",),
        "rechecks": ("change_scope", "protected_constraints"),
    },)


def generate_architectural_change_strategies(
    plan: DeclarativeChangePlan,
    readiness: ExecutionReadinessResult,
    snapshot: Mapping[str, Any],
) -> StrategyGenerationResult:
    """Return stable semantic alternatives without changing any input."""
    if not isinstance(plan, DeclarativeChangePlan):
        raise ValueError("plan must be DeclarativeChangePlan")
    if not isinstance(readiness, ExecutionReadinessResult):
        raise ValueError("readiness must be ExecutionReadinessResult")
    if not isinstance(snapshot, Mapping):
        raise ValueError("snapshot must be a mapping")
    if readiness.plan_id != plan.plan_id:
        raise ValueError("readiness and plan identifiers must match")

    evidence = _sorted((*plan.evidence, *readiness.evidence))
    provenance = {
        "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01E",
        "strategy_generator": "architectural_change_strategy_generator_v1",
        "source_plan_id": plan.plan_id,
        "source_validation_version": readiness.validation_version,
        "spatial_state_changed": False,
        "producer_invoked": False,
    }
    if readiness.readiness_status not in _ADMITTED:
        reasons = _sorted((
            f"readiness_status:{readiness.readiness_status}",
            *readiness.rejection_reasons,
            *(f"unresolved_dependency:{item}" for item in readiness.unresolved_dependencies),
            *(f"constraint_conflict:{item}" for item in readiness.constraint_conflicts),
        ))
        return StrategyGenerationResult(
            plan_id=plan.plan_id,
            generation_status=STRATEGY_GENERATION_STATUS_BLOCKED_READINESS,
            strategies=(),
            blocker_reasons=reasons,
            evidence=evidence,
            provenance=provenance,
        )

    kind = _strategy_kind(plan)
    constraints = _sorted((
        *plan.preserve_constraints,
        *readiness.preservation_requirements,
        *_snapshot_constraints(snapshot),
    ))
    prerequisites = _sorted((*plan.prerequisites, *readiness.unresolved_dependencies))
    rechecks = _sorted((*plan.required_rechecks, *readiness.required_checks_before_execution))
    applicability = (
        STRATEGY_APPLICABILITY_WITH_PREREQUISITES
        if readiness.readiness_status == READINESS_STATUS_READY_WITH_PREREQUISITES
        else STRATEGY_APPLICABILITY_APPLICABLE
    )
    strategies = []
    for template in _templates(kind):
        strategy_type = str(template["type"])
        strategies.append(ArchitecturalChangeStrategy(
            strategy_id=f"{plan.plan_id}:strategy:{strategy_type.lower()}",
            plan_id=plan.plan_id,
            strategy_type=strategy_type,
            target_entities=_sorted(plan.target_entities),
            proposed_semantic_actions=_sorted((
                *plan.proposed_operations,
                *template["actions"],
            )),
            required_tradeoffs=_sorted(template["tradeoffs"]),
            preserved_constraints=constraints,
            prerequisites=prerequisites,
            expected_impacts=_sorted(template["impacts"]),
            risks=_sorted(template["risks"]),
            required_rechecks=_sorted((*rechecks, *template["rechecks"])),
            applicability_status=applicability,
            evidence=evidence,
            provenance={**provenance, "strategy_type": strategy_type},
            strategy_rank_hint=None,
        ))

    return StrategyGenerationResult(
        plan_id=plan.plan_id,
        generation_status=STRATEGY_GENERATION_STATUS_GENERATED,
        strategies=tuple(strategies),
        blocker_reasons=(),
        evidence=evidence,
        provenance=provenance,
    )


__all__ = ["generate_architectural_change_strategies"]
