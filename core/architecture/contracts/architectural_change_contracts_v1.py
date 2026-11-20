"""Generator-independent contracts for architectural design changes.

The versioned contracts describe change intent, analysis, planning, readiness,
semantic strategies, variant identity, and revision history.  They do not
parse user dialogue, execute producers, or create/mutate spatial state.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass
import json
from typing import Any, Mapping, TypeVar


SCHEMA_VERSION = "architectural_change_contracts_v1"

PLANNING_STATUS_PLANNABLE = "PLANNABLE"
PLANNING_STATUS_PLANNABLE_WITH_PREREQUISITES = "PLANNABLE_WITH_PREREQUISITES"
PLANNING_STATUS_SITE_DEPENDENT = "SITE_DEPENDENT"
PLANNING_STATUS_GEOMETRY_DEPENDENT = "GEOMETRY_DEPENDENT"
PLANNING_STATUS_REJECTED_BY_CONSTRAINT = "REJECTED_BY_CONSTRAINT"
PLANNING_STATUS_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
DECLARATIVE_CHANGE_PLANNING_STATUSES = (
    PLANNING_STATUS_PLANNABLE,
    PLANNING_STATUS_PLANNABLE_WITH_PREREQUISITES,
    PLANNING_STATUS_SITE_DEPENDENT,
    PLANNING_STATUS_GEOMETRY_DEPENDENT,
    PLANNING_STATUS_REJECTED_BY_CONSTRAINT,
    PLANNING_STATUS_INSUFFICIENT_EVIDENCE,
)

READINESS_STATUS_READY = "READY"
READINESS_STATUS_READY_WITH_PREREQUISITES = "READY_WITH_PREREQUISITES"
READINESS_STATUS_BLOCKED_SITE = "BLOCKED_SITE"
READINESS_STATUS_BLOCKED_GEOMETRY = "BLOCKED_GEOMETRY"
READINESS_STATUS_BLOCKED_CONSTRAINT = "BLOCKED_CONSTRAINT"
READINESS_STATUS_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
EXECUTION_READINESS_STATUSES = (
    READINESS_STATUS_READY,
    READINESS_STATUS_READY_WITH_PREREQUISITES,
    READINESS_STATUS_BLOCKED_SITE,
    READINESS_STATUS_BLOCKED_GEOMETRY,
    READINESS_STATUS_BLOCKED_CONSTRAINT,
    READINESS_STATUS_INSUFFICIENT_EVIDENCE,
)

STRATEGY_GENERATION_STATUS_GENERATED = "GENERATED"
STRATEGY_GENERATION_STATUS_BLOCKED_READINESS = "BLOCKED_READINESS"
STRATEGY_GENERATION_STATUSES = (
    STRATEGY_GENERATION_STATUS_GENERATED,
    STRATEGY_GENERATION_STATUS_BLOCKED_READINESS,
)

STRATEGY_APPLICABILITY_APPLICABLE = "APPLICABLE"
STRATEGY_APPLICABILITY_WITH_PREREQUISITES = "APPLICABLE_WITH_PREREQUISITES"
STRATEGY_APPLICABILITY_STATUSES = (
    STRATEGY_APPLICABILITY_APPLICABLE,
    STRATEGY_APPLICABILITY_WITH_PREREQUISITES,
)

GEOMETRY_REALIZATION_STATUS_REALIZED = "REALIZED"
GEOMETRY_REALIZATION_STATUS_REALIZED_WITH_WARNINGS = "REALIZED_WITH_WARNINGS"
GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT = "REJECTED_CONSTRAINT"
GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY = "REJECTED_GEOMETRY"
GEOMETRY_REALIZATION_STATUS_STALE_PARENT = "STALE_PARENT"
GEOMETRY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY = "UNSUPPORTED_STRATEGY"
GEOMETRY_REALIZATION_STATUS_FAILED = "FAILED"
GEOMETRY_REALIZATION_STATUSES = (
    GEOMETRY_REALIZATION_STATUS_REALIZED,
    GEOMETRY_REALIZATION_STATUS_REALIZED_WITH_WARNINGS,
    GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT,
    GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY,
    GEOMETRY_REALIZATION_STATUS_STALE_PARENT,
    GEOMETRY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY,
    GEOMETRY_REALIZATION_STATUS_FAILED,
)

TOPOLOGY_REALIZATION_STATUS_REALIZED = "REALIZED"
TOPOLOGY_REALIZATION_STATUS_REALIZED_WITH_WARNINGS = "REALIZED_WITH_WARNINGS"
TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT = "REJECTED_CONSTRAINT"
TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY = "REJECTED_TOPOLOGY"
TOPOLOGY_REALIZATION_STATUS_STALE_PARENT = "STALE_PARENT"
TOPOLOGY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY = "UNSUPPORTED_STRATEGY"
TOPOLOGY_REALIZATION_STATUS_FAILED = "FAILED"
TOPOLOGY_REALIZATION_STATUSES = (
    TOPOLOGY_REALIZATION_STATUS_REALIZED,
    TOPOLOGY_REALIZATION_STATUS_REALIZED_WITH_WARNINGS,
    TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT,
    TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY,
    TOPOLOGY_REALIZATION_STATUS_STALE_PARENT,
    TOPOLOGY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY,
    TOPOLOGY_REALIZATION_STATUS_FAILED,
)

OPENING_ACCESS_REALIZATION_STATUS_REALIZED = "REALIZED"
OPENING_ACCESS_REALIZATION_STATUS_REALIZED_WITH_WARNINGS = "REALIZED_WITH_WARNINGS"
OPENING_ACCESS_REALIZATION_STATUS_REJECTED_CONSTRAINT = "REJECTED_CONSTRAINT"
OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY = "REJECTED_OPENING_GEOMETRY"
OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS = "REJECTED_ACCESS"
OPENING_ACCESS_REALIZATION_STATUS_STALE_PARENT = "STALE_PARENT"
OPENING_ACCESS_REALIZATION_STATUS_UNSUPPORTED_STRATEGY = "UNSUPPORTED_STRATEGY"
OPENING_ACCESS_REALIZATION_STATUS_FAILED = "FAILED"
OPENING_ACCESS_REALIZATION_STATUSES = (
    OPENING_ACCESS_REALIZATION_STATUS_REALIZED,
    OPENING_ACCESS_REALIZATION_STATUS_REALIZED_WITH_WARNINGS,
    OPENING_ACCESS_REALIZATION_STATUS_REJECTED_CONSTRAINT,
    OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY,
    OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS,
    OPENING_ACCESS_REALIZATION_STATUS_STALE_PARENT,
    OPENING_ACCESS_REALIZATION_STATUS_UNSUPPORTED_STRATEGY,
    OPENING_ACCESS_REALIZATION_STATUS_FAILED,
)

TRANSACTION_STATUS_COMMITTED = "COMMITTED"
TRANSACTION_STATUS_COMMITTED_WITH_WARNINGS = "COMMITTED_WITH_WARNINGS"
TRANSACTION_STATUS_REJECTED_DEPENDENCY_ORDER = "REJECTED_DEPENDENCY_ORDER"
TRANSACTION_STATUS_REJECTED_CONSTRAINT = "REJECTED_CONSTRAINT"
TRANSACTION_STATUS_REJECTED_STEP_FAILURE = "REJECTED_STEP_FAILURE"
TRANSACTION_STATUS_STALE_PARENT = "STALE_PARENT"
TRANSACTION_STATUS_UNSUPPORTED_STRATEGY_SEQUENCE = "UNSUPPORTED_STRATEGY_SEQUENCE"
TRANSACTION_STATUS_FAILED = "FAILED"
MULTI_REALIZER_TRANSACTION_STATUSES = (
    TRANSACTION_STATUS_COMMITTED,
    TRANSACTION_STATUS_COMMITTED_WITH_WARNINGS,
    TRANSACTION_STATUS_REJECTED_DEPENDENCY_ORDER,
    TRANSACTION_STATUS_REJECTED_CONSTRAINT,
    TRANSACTION_STATUS_REJECTED_STEP_FAILURE,
    TRANSACTION_STATUS_STALE_PARENT,
    TRANSACTION_STATUS_UNSUPPORTED_STRATEGY_SEQUENCE,
    TRANSACTION_STATUS_FAILED,
)


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_text_tuple(value: tuple[str, ...], field_name: str) -> None:
    if not isinstance(value, tuple) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{field_name} must be a tuple of non-empty strings")


def _payload(value: Any) -> Any:
    """Return JSON-safe data without exposing caller-owned mutable values."""
    if is_dataclass(value):
        return {item.name: _payload(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _payload(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_payload(item) for item in value]
    return deepcopy(value)


@dataclass(frozen=True)
class ArchitecturalChangeIntent:
    change_intent_id: str
    change_type: str
    targets: tuple[str, ...]
    direction: str | None = None
    preference: str | None = None
    priority: str = "normal"
    hard_constraints: tuple[str, ...] = ()
    soft_objectives: tuple[str, ...] = ()
    preserve_constraints: tuple[str, ...] = ()
    user_text: str = ""
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_text(self.change_intent_id, "change_intent_id")
        _require_text(self.change_type, "change_type")
        _require_text_tuple(self.targets, "targets")
        if not self.targets:
            raise ValueError("targets must contain at least one target")
        _require_text(self.priority, "priority")
        _require_text_tuple(self.hard_constraints, "hard_constraints")
        _require_text_tuple(self.soft_objectives, "soft_objectives")
        _require_text_tuple(self.preserve_constraints, "preserve_constraints")
        if not isinstance(self.user_text, str):
            raise ValueError("user_text must be a string")
        if self.provenance is not None and not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping or None")


@dataclass(frozen=True)
class DesignChangeImpact:
    change_intent_id: str
    affected_spaces: tuple[str, ...] = ()
    affected_relations: tuple[str, ...] = ()
    affected_openings: tuple[str, ...] = ()
    affected_windows_or_daylight: tuple[str, ...] = ()
    affected_circulation: tuple[str, ...] = ()
    possible_conflicts: tuple[str, ...] = ()
    required_rechecks: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()
    feasibility_status: str = "not_assessed"
    feasibility_reasons: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    confidence: str = "unknown"

    def __post_init__(self) -> None:
        _require_text(self.change_intent_id, "change_intent_id")
        for field_name in (
            "affected_spaces",
            "affected_relations",
            "affected_openings",
            "affected_windows_or_daylight",
            "affected_circulation",
            "possible_conflicts",
            "required_rechecks",
            "risk_flags",
            "feasibility_reasons",
            "evidence",
        ):
            _require_text_tuple(getattr(self, field_name), field_name)
        _require_text(self.feasibility_status, "feasibility_status")
        _require_text(self.confidence, "confidence")


@dataclass(frozen=True)
class DeclarativeChangePlan:
    """A semantic statement of what should change, never a geometric patch."""

    plan_id: str
    intent_id: str
    proposed_operations: tuple[str, ...]
    target_entities: tuple[str, ...]
    preserve_constraints: tuple[str, ...]
    prerequisites: tuple[str, ...]
    rejection_conditions: tuple[str, ...]
    required_rechecks: tuple[str, ...]
    deferred_dependencies: tuple[str, ...]
    planning_status: str
    planning_reasons: tuple[str, ...]
    evidence: tuple[str, ...] = ()
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_text(self.plan_id, "plan_id")
        _require_text(self.intent_id, "intent_id")
        for field_name in (
            "proposed_operations",
            "target_entities",
            "preserve_constraints",
            "prerequisites",
            "rejection_conditions",
            "required_rechecks",
            "deferred_dependencies",
            "planning_reasons",
            "evidence",
        ):
            _require_text_tuple(getattr(self, field_name), field_name)
        _require_text(self.planning_status, "planning_status")
        if self.planning_status not in DECLARATIVE_CHANGE_PLANNING_STATUSES:
            raise ValueError(f"unsupported planning_status: {self.planning_status}")
        if self.provenance is not None and not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping or None")


@dataclass(frozen=True)
class ExecutionReadinessResult:
    """A read-only decision about admission to the strategy stage."""

    plan_id: str
    readiness_status: str
    unresolved_dependencies: tuple[str, ...]
    constraint_conflicts: tuple[str, ...]
    preservation_requirements: tuple[str, ...]
    required_checks_before_execution: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    evidence: tuple[str, ...]
    provenance: Mapping[str, Any] | None = None
    validation_version: str = "architectural_change_readiness_v1"

    def __post_init__(self) -> None:
        _require_text(self.plan_id, "plan_id")
        _require_text(self.readiness_status, "readiness_status")
        if self.readiness_status not in EXECUTION_READINESS_STATUSES:
            raise ValueError(f"unsupported readiness_status: {self.readiness_status}")
        for field_name in (
            "unresolved_dependencies",
            "constraint_conflicts",
            "preservation_requirements",
            "required_checks_before_execution",
            "rejection_reasons",
            "evidence",
        ):
            _require_text_tuple(getattr(self, field_name), field_name)
        if self.provenance is not None and not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping or None")
        _require_text(self.validation_version, "validation_version")


@dataclass(frozen=True)
class ArchitecturalChangeStrategy:
    """A comparable semantic option; it is not an executable spatial edit."""

    strategy_id: str
    plan_id: str
    strategy_type: str
    target_entities: tuple[str, ...]
    proposed_semantic_actions: tuple[str, ...]
    required_tradeoffs: tuple[str, ...]
    preserved_constraints: tuple[str, ...]
    prerequisites: tuple[str, ...]
    expected_impacts: tuple[str, ...]
    risks: tuple[str, ...]
    required_rechecks: tuple[str, ...]
    applicability_status: str
    evidence: tuple[str, ...]
    provenance: Mapping[str, Any] | None = None
    strategy_rank_hint: int | None = None
    strategy_version: str = "architectural_change_strategy_v1"

    def __post_init__(self) -> None:
        for field_name in ("strategy_id", "plan_id", "strategy_type"):
            _require_text(getattr(self, field_name), field_name)
        for field_name in (
            "target_entities",
            "proposed_semantic_actions",
            "required_tradeoffs",
            "preserved_constraints",
            "prerequisites",
            "expected_impacts",
            "risks",
            "required_rechecks",
            "evidence",
        ):
            _require_text_tuple(getattr(self, field_name), field_name)
        if not self.target_entities:
            raise ValueError("target_entities must contain at least one target")
        if not self.proposed_semantic_actions:
            raise ValueError("proposed_semantic_actions must not be empty")
        if self.applicability_status not in STRATEGY_APPLICABILITY_STATUSES:
            raise ValueError(
                f"unsupported applicability_status: {self.applicability_status}"
            )
        if self.provenance is not None and not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping or None")
        if self.strategy_rank_hint is not None and (
            not isinstance(self.strategy_rank_hint, int) or self.strategy_rank_hint < 1
        ):
            raise ValueError("strategy_rank_hint must be a positive integer or None")
        _require_text(self.strategy_version, "strategy_version")


@dataclass(frozen=True)
class StrategyGenerationResult:
    """The admitted semantic strategies or a structured readiness rejection."""

    plan_id: str
    generation_status: str
    strategies: tuple[ArchitecturalChangeStrategy, ...]
    blocker_reasons: tuple[str, ...]
    evidence: tuple[str, ...]
    provenance: Mapping[str, Any] | None = None
    generation_version: str = "architectural_change_strategy_generation_v1"

    def __post_init__(self) -> None:
        _require_text(self.plan_id, "plan_id")
        if self.generation_status not in STRATEGY_GENERATION_STATUSES:
            raise ValueError(f"unsupported generation_status: {self.generation_status}")
        if not isinstance(self.strategies, tuple) or any(
            not isinstance(item, ArchitecturalChangeStrategy) for item in self.strategies
        ):
            raise ValueError("strategies must be a tuple of ArchitecturalChangeStrategy")
        _require_text_tuple(self.blocker_reasons, "blocker_reasons")
        _require_text_tuple(self.evidence, "evidence")
        if self.generation_status == STRATEGY_GENERATION_STATUS_BLOCKED_READINESS:
            if self.strategies:
                raise ValueError("blocked strategy generation cannot contain strategies")
            if not self.blocker_reasons:
                raise ValueError("blocked strategy generation requires blocker_reasons")
        if self.generation_status == STRATEGY_GENERATION_STATUS_GENERATED:
            if not self.strategies:
                raise ValueError("generated result must contain at least one strategy")
            if self.blocker_reasons:
                raise ValueError("generated result cannot contain blocker_reasons")
        if self.provenance is not None and not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping or None")
        _require_text(self.generation_version, "generation_version")


@dataclass(frozen=True)
class GeometryDelta:
    """An auditable space-boundary change proposed by one selected strategy."""

    entity_id: str
    space_id: str
    operation: str
    before_geometry: Mapping[str, Any]
    after_geometry: Mapping[str, Any]
    before_area: float
    after_area: float
    affected_neighbors: tuple[str, ...]
    reason: str
    strategy_id: str
    provenance: Mapping[str, Any]
    delta_version: str = "architectural_change_geometry_delta_v1"

    def __post_init__(self) -> None:
        for field_name in ("entity_id", "space_id", "operation", "reason", "strategy_id"):
            _require_text(getattr(self, field_name), field_name)
        for field_name in ("before_geometry", "after_geometry", "provenance"):
            if not isinstance(getattr(self, field_name), Mapping):
                raise ValueError(f"{field_name} must be a mapping")
        for field_name in ("before_area", "after_area"):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{field_name} must be a positive number")
        _require_text_tuple(self.affected_neighbors, "affected_neighbors")
        _require_text(self.delta_version, "delta_version")


@dataclass(frozen=True)
class GeometryRealizationResult:
    """Transaction outcome; a rejected result never represents a committed child."""

    realization_id: str
    strategy_id: str
    parent_candidate_id: str
    derived_candidate_id: str | None
    status: str
    affected_entities: tuple[str, ...]
    geometry_changes: tuple[GeometryDelta, ...]
    preserved_entities: tuple[str, ...]
    applied_operations: tuple[str, ...]
    rejected_operations: tuple[str, ...]
    constraint_checks: tuple[Mapping[str, Any], ...]
    geometry_checks: tuple[Mapping[str, Any], ...]
    required_downstream_rechecks: tuple[str, ...]
    warnings: tuple[str, ...]
    failures: tuple[str, ...]
    parent_hash: str
    derived_hash: str | None
    provenance: Mapping[str, Any]
    realization_version: str = "architectural_change_space_geometry_realization_v1"

    def __post_init__(self) -> None:
        for field_name in ("realization_id", "strategy_id", "parent_candidate_id", "parent_hash"):
            _require_text(getattr(self, field_name), field_name)
        if self.derived_candidate_id is not None:
            _require_text(self.derived_candidate_id, "derived_candidate_id")
        if self.derived_hash is not None:
            _require_text(self.derived_hash, "derived_hash")
        if self.status not in GEOMETRY_REALIZATION_STATUSES:
            raise ValueError(f"unsupported geometry realization status: {self.status}")
        for field_name in (
            "affected_entities", "preserved_entities", "applied_operations",
            "rejected_operations", "required_downstream_rechecks", "warnings", "failures",
        ):
            _require_text_tuple(getattr(self, field_name), field_name)
        if not isinstance(self.geometry_changes, tuple) or any(
            not isinstance(item, GeometryDelta) for item in self.geometry_changes
        ):
            raise ValueError("geometry_changes must be a tuple of GeometryDelta")
        for field_name in ("constraint_checks", "geometry_checks"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple) or any(not isinstance(item, Mapping) for item in value):
                raise ValueError(f"{field_name} must be a tuple of mappings")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        committed = self.status in {
            GEOMETRY_REALIZATION_STATUS_REALIZED,
            GEOMETRY_REALIZATION_STATUS_REALIZED_WITH_WARNINGS,
        }
        if committed and (not self.geometry_changes or self.derived_candidate_id is None or self.derived_hash is None):
            raise ValueError("realized result requires changes and derived candidate identity")
        if not committed and (self.geometry_changes or self.derived_candidate_id is not None or self.derived_hash is not None):
            raise ValueError("rejected result cannot contain committed geometry")
        _require_text(self.realization_version, "realization_version")


@dataclass(frozen=True)
class TopologyDelta:
    """Auditable before/after proof for one physical adjacency change."""

    relation_id: str
    relation_pair: tuple[str, str]
    before_relation: Mapping[str, Any]
    after_relation: Mapping[str, Any]
    affected_spaces: tuple[str, ...]
    affected_connections: tuple[str, ...]
    affected_circulation: tuple[str, ...]
    topology_operations: tuple[str, ...]
    preserved_constraints: tuple[str, ...]
    reason: str
    strategy_id: str
    provenance: Mapping[str, Any]
    delta_version: str = "architectural_change_topology_delta_v1"

    def __post_init__(self) -> None:
        for field_name in ("relation_id", "reason", "strategy_id", "delta_version"):
            _require_text(getattr(self, field_name), field_name)
        _require_text_tuple(self.relation_pair, "relation_pair")
        if len(self.relation_pair) != 2 or self.relation_pair[0] == self.relation_pair[1]:
            raise ValueError("relation_pair must contain two distinct entity ids")
        for field_name in ("before_relation", "after_relation", "provenance"):
            if not isinstance(getattr(self, field_name), Mapping):
                raise ValueError(f"{field_name} must be a mapping")
        for field_name in (
            "affected_spaces", "affected_connections", "affected_circulation",
            "topology_operations", "preserved_constraints",
        ):
            _require_text_tuple(getattr(self, field_name), field_name)
        if not self.topology_operations:
            raise ValueError("topology_operations must not be empty")


@dataclass(frozen=True)
class AdjacencyRealizationResult:
    """Transactional 01F-B outcome; rejected outcomes never contain a child."""

    realization_id: str
    strategy_id: str
    parent_candidate_id: str
    derived_candidate_id: str | None
    status: str
    topology_changes: tuple[TopologyDelta, ...]
    affected_entities: tuple[str, ...]
    preserved_entities: tuple[str, ...]
    applied_operations: tuple[str, ...]
    rejected_operations: tuple[str, ...]
    constraint_checks: tuple[Mapping[str, Any], ...]
    topology_checks: tuple[Mapping[str, Any], ...]
    access_checks: tuple[Mapping[str, Any], ...]
    required_downstream_rechecks: tuple[str, ...]
    warnings: tuple[str, ...]
    failures: tuple[str, ...]
    parent_hash: str
    derived_hash: str | None
    provenance: Mapping[str, Any]
    realization_version: str = "architectural_change_adjacency_topology_realization_v1"

    def __post_init__(self) -> None:
        for field_name in ("realization_id", "strategy_id", "parent_candidate_id", "parent_hash", "realization_version"):
            _require_text(getattr(self, field_name), field_name)
        if self.derived_candidate_id is not None:
            _require_text(self.derived_candidate_id, "derived_candidate_id")
        if self.derived_hash is not None:
            _require_text(self.derived_hash, "derived_hash")
        if self.status not in TOPOLOGY_REALIZATION_STATUSES:
            raise ValueError(f"unsupported topology realization status: {self.status}")
        if not isinstance(self.topology_changes, tuple) or any(
            not isinstance(item, TopologyDelta) for item in self.topology_changes
        ):
            raise ValueError("topology_changes must be a tuple of TopologyDelta")
        for field_name in (
            "affected_entities", "preserved_entities", "applied_operations",
            "rejected_operations", "required_downstream_rechecks", "warnings", "failures",
        ):
            _require_text_tuple(getattr(self, field_name), field_name)
        for field_name in ("constraint_checks", "topology_checks", "access_checks"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple) or any(not isinstance(item, Mapping) for item in value):
                raise ValueError(f"{field_name} must be a tuple of mappings")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        committed = self.status in {
            TOPOLOGY_REALIZATION_STATUS_REALIZED,
            TOPOLOGY_REALIZATION_STATUS_REALIZED_WITH_WARNINGS,
        }
        if committed and (not self.topology_changes or self.derived_candidate_id is None or self.derived_hash is None):
            raise ValueError("realized result requires topology changes and derived candidate identity")
        if not committed and (self.topology_changes or self.derived_candidate_id is not None or self.derived_hash is not None):
            raise ValueError("rejected result cannot contain committed topology")


@dataclass(frozen=True)
class OpeningAccessDelta:
    """Auditable geometric opening and semantic access-binding transaction."""

    interface_id: str
    target_space_pair: tuple[str, str]
    shared_boundary_ref: str
    operation: str
    before_interface: Mapping[str, Any] | None
    after_interface: Mapping[str, Any]
    boundary_segment: tuple[tuple[float, float], tuple[float, float]]
    width: float
    source_of_width: str
    position: Mapping[str, Any]
    source_of_position: str
    affected_access_edges: tuple[str, ...]
    affected_circulation: tuple[str, ...]
    preserved_constraints: tuple[str, ...]
    reason: str
    strategy_id: str
    provenance: Mapping[str, Any]
    delta_version: str = "architectural_change_opening_access_delta_v1"

    def __post_init__(self) -> None:
        for field_name in (
            "interface_id", "shared_boundary_ref", "operation", "source_of_width",
            "source_of_position", "reason", "strategy_id", "delta_version",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_text_tuple(self.target_space_pair, "target_space_pair")
        if len(self.target_space_pair) != 2 or self.target_space_pair[0] == self.target_space_pair[1]:
            raise ValueError("target_space_pair must contain two distinct entity ids")
        if self.before_interface is not None and not isinstance(self.before_interface, Mapping):
            raise ValueError("before_interface must be a mapping or None")
        for field_name in ("after_interface", "position", "provenance"):
            if not isinstance(getattr(self, field_name), Mapping):
                raise ValueError(f"{field_name} must be a mapping")
        if not isinstance(self.width, (int, float)) or isinstance(self.width, bool) or self.width <= 0:
            raise ValueError("width must be a positive number")
        if (
            not isinstance(self.boundary_segment, tuple)
            or len(self.boundary_segment) != 2
            or any(not isinstance(point, tuple) or len(point) != 2 for point in self.boundary_segment)
        ):
            raise ValueError("boundary_segment must contain two coordinate pairs")
        for field_name in (
            "affected_access_edges", "affected_circulation", "preserved_constraints",
        ):
            _require_text_tuple(getattr(self, field_name), field_name)


@dataclass(frozen=True)
class OpeningAccessRealizationResult:
    """Transactional 01F-C outcome; rejected outcomes never contain a child."""

    realization_id: str
    strategy_id: str
    parent_candidate_id: str
    derived_candidate_id: str | None
    status: str
    opening_access_changes: tuple[OpeningAccessDelta, ...]
    affected_entities: tuple[str, ...]
    applied_operations: tuple[str, ...]
    rejected_operations: tuple[str, ...]
    geometry_checks: tuple[Mapping[str, Any], ...]
    access_checks: tuple[Mapping[str, Any], ...]
    circulation_checks: tuple[Mapping[str, Any], ...]
    constraint_checks: tuple[Mapping[str, Any], ...]
    required_downstream_rechecks: tuple[str, ...]
    warnings: tuple[str, ...]
    failures: tuple[str, ...]
    parent_hash: str
    derived_hash: str | None
    provenance: Mapping[str, Any]
    realization_version: str = "architectural_change_opening_access_realization_v1"

    def __post_init__(self) -> None:
        for field_name in (
            "realization_id", "strategy_id", "parent_candidate_id", "parent_hash",
            "realization_version",
        ):
            _require_text(getattr(self, field_name), field_name)
        if self.derived_candidate_id is not None:
            _require_text(self.derived_candidate_id, "derived_candidate_id")
        if self.derived_hash is not None:
            _require_text(self.derived_hash, "derived_hash")
        if self.status not in OPENING_ACCESS_REALIZATION_STATUSES:
            raise ValueError(f"unsupported opening/access realization status: {self.status}")
        if not isinstance(self.opening_access_changes, tuple) or any(
            not isinstance(item, OpeningAccessDelta) for item in self.opening_access_changes
        ):
            raise ValueError("opening_access_changes must be a tuple of OpeningAccessDelta")
        for field_name in (
            "affected_entities", "applied_operations", "rejected_operations",
            "required_downstream_rechecks", "warnings", "failures",
        ):
            _require_text_tuple(getattr(self, field_name), field_name)
        for field_name in (
            "geometry_checks", "access_checks", "circulation_checks", "constraint_checks",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, tuple) or any(not isinstance(item, Mapping) for item in value):
                raise ValueError(f"{field_name} must be a tuple of mappings")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        committed = self.status in {
            OPENING_ACCESS_REALIZATION_STATUS_REALIZED,
            OPENING_ACCESS_REALIZATION_STATUS_REALIZED_WITH_WARNINGS,
        }
        if committed and (
            not self.opening_access_changes
            or self.derived_candidate_id is None
            or self.derived_hash is None
        ):
            raise ValueError("realized result requires changes and derived candidate identity")
        if not committed and (
            self.opening_access_changes
            or self.derived_candidate_id is not None
            or self.derived_hash is not None
        ):
            raise ValueError("rejected result cannot contain committed opening/access changes")


@dataclass(frozen=True)
class MultiRealizerTransactionPlan:
    """Deterministic execution order for existing architectural-change realizers."""

    transaction_id: str
    parent_candidate_id: str
    parent_candidate_hash: str
    parent_candidate_version: str
    ordered_strategy_ids: tuple[str, ...]
    ordered_realizer_steps: tuple[str, ...]
    dependency_edges: tuple[tuple[str, str], ...] = ()
    provenance: Mapping[str, Any] | None = None
    transaction_plan_version: str = "architectural_change_multi_realizer_transaction_plan_v1"

    def __post_init__(self) -> None:
        for field_name in (
            "transaction_id", "parent_candidate_id", "parent_candidate_hash",
            "parent_candidate_version", "transaction_plan_version",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_text_tuple(self.ordered_strategy_ids, "ordered_strategy_ids")
        _require_text_tuple(self.ordered_realizer_steps, "ordered_realizer_steps")
        if not self.ordered_strategy_ids:
            raise ValueError("ordered_strategy_ids must not be empty")
        if len(self.ordered_strategy_ids) != len(self.ordered_realizer_steps):
            raise ValueError("ordered strategy and realizer step counts must match")
        if len(set(self.ordered_strategy_ids)) != len(self.ordered_strategy_ids):
            raise ValueError("ordered_strategy_ids cannot contain duplicates")
        if not isinstance(self.dependency_edges, tuple) or any(
            not isinstance(edge, tuple) or len(edge) != 2
            or any(not isinstance(item, str) or not item.strip() for item in edge)
            for edge in self.dependency_edges
        ):
            raise ValueError("dependency_edges must be a tuple of two-item text tuples")
        if self.provenance is not None and not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping or None")


@dataclass(frozen=True)
class TransactionStepResult:
    step_index: int
    strategy_id: str
    realizer_step: str
    realization_result_type: str
    realization_status: str
    parent_candidate_id: str
    parent_candidate_hash: str
    parent_candidate_version: str
    derived_candidate_id: str | None
    derived_candidate_hash: str | None
    derived_candidate_version: str | None
    deltas: tuple[Mapping[str, Any], ...]
    invariant_checks: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]
    failures: tuple[str, ...]
    provenance: Mapping[str, Any]
    step_result_version: str = "architectural_change_transaction_step_result_v1"

    def __post_init__(self) -> None:
        if not isinstance(self.step_index, int) or self.step_index < 0:
            raise ValueError("step_index must be a non-negative integer")
        for field_name in (
            "strategy_id", "realizer_step", "realization_result_type",
            "realization_status", "parent_candidate_id", "parent_candidate_hash",
            "parent_candidate_version", "step_result_version",
        ):
            _require_text(getattr(self, field_name), field_name)
        for field_name in (
            "derived_candidate_id", "derived_candidate_hash", "derived_candidate_version",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _require_text(value, field_name)
        for field_name in ("deltas", "invariant_checks"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple) or any(not isinstance(item, Mapping) for item in value):
                raise ValueError(f"{field_name} must be a tuple of mappings")
        _require_text_tuple(self.warnings, "warnings")
        _require_text_tuple(self.failures, "failures")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")


@dataclass(frozen=True)
class MultiRealizerTransactionResult:
    transaction_id: str
    parent_candidate_id: str
    parent_candidate_hash: str
    parent_candidate_version: str
    ordered_strategy_ids: tuple[str, ...]
    ordered_realizer_steps: tuple[str, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    step_results: tuple[TransactionStepResult, ...]
    aggregate_deltas: tuple[Mapping[str, Any], ...]
    final_candidate_id: str | None
    final_candidate_hash: str | None
    final_candidate_version: str | None
    commit_status: str
    rollback_reason: str | None
    failed_step_index: int | None
    failed_step_id: str | None
    invariant_checks: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]
    failures: tuple[str, ...]
    provenance: Mapping[str, Any]
    transaction_result_version: str = "architectural_change_multi_realizer_transaction_result_v1"

    def __post_init__(self) -> None:
        for field_name in (
            "transaction_id", "parent_candidate_id", "parent_candidate_hash",
            "parent_candidate_version", "transaction_result_version",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_text_tuple(self.ordered_strategy_ids, "ordered_strategy_ids")
        _require_text_tuple(self.ordered_realizer_steps, "ordered_realizer_steps")
        if self.commit_status not in MULTI_REALIZER_TRANSACTION_STATUSES:
            raise ValueError(f"unsupported transaction status: {self.commit_status}")
        if not isinstance(self.dependency_edges, tuple) or any(
            not isinstance(edge, tuple) or len(edge) != 2 for edge in self.dependency_edges
        ):
            raise ValueError("dependency_edges must be a tuple of pairs")
        if not isinstance(self.step_results, tuple) or any(
            not isinstance(item, TransactionStepResult) for item in self.step_results
        ):
            raise ValueError("step_results must be a tuple of TransactionStepResult")
        for field_name in ("aggregate_deltas", "invariant_checks"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple) or any(not isinstance(item, Mapping) for item in value):
                raise ValueError(f"{field_name} must be a tuple of mappings")
        for field_name in (
            "final_candidate_id", "final_candidate_hash", "final_candidate_version",
            "rollback_reason", "failed_step_id",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _require_text(value, field_name)
        if self.failed_step_index is not None and (
            not isinstance(self.failed_step_index, int) or self.failed_step_index < 0
        ):
            raise ValueError("failed_step_index must be a non-negative integer or None")
        _require_text_tuple(self.warnings, "warnings")
        _require_text_tuple(self.failures, "failures")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        committed = self.commit_status in {
            TRANSACTION_STATUS_COMMITTED, TRANSACTION_STATUS_COMMITTED_WITH_WARNINGS,
        }
        final_values = (self.final_candidate_id, self.final_candidate_hash, self.final_candidate_version)
        if committed and (any(value is None for value in final_values) or self.rollback_reason is not None):
            raise ValueError("committed transaction requires final identity and no rollback reason")
        if not committed and any(value is not None for value in final_values):
            raise ValueError("rejected transaction cannot publish final candidate identity")


@dataclass(frozen=True)
class DesignVariant:
    parent_candidate_id: str
    change_intent_id: str
    variant_id: str
    status: str = "proposed"
    preserved_constraints: tuple[str, ...] = ()
    quality_gate_status: str = "not_evaluated"
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_text(self.parent_candidate_id, "parent_candidate_id")
        _require_text(self.change_intent_id, "change_intent_id")
        _require_text(self.variant_id, "variant_id")
        _require_text(self.status, "status")
        _require_text_tuple(self.preserved_constraints, "preserved_constraints")
        _require_text(self.quality_gate_status, "quality_gate_status")
        if self.provenance is not None and not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping or None")


@dataclass(frozen=True)
class DesignRevisionRecord:
    revision_id: str
    parent_revision_id: str | None
    child_revision_ids: tuple[str, ...]
    user_request: str
    interpreted_intent: ArchitecturalChangeIntent
    affected_entities: tuple[str, ...] = ()
    quality_result: Mapping[str, Any] | None = None
    user_approval_status: str = "pending"

    def __post_init__(self) -> None:
        _require_text(self.revision_id, "revision_id")
        if self.parent_revision_id is not None:
            _require_text(self.parent_revision_id, "parent_revision_id")
            if self.parent_revision_id == self.revision_id:
                raise ValueError("a revision cannot be its own parent")
        _require_text_tuple(self.child_revision_ids, "child_revision_ids")
        if self.revision_id in self.child_revision_ids:
            raise ValueError("a revision cannot be its own child")
        _require_text(self.user_request, "user_request")
        if not isinstance(self.interpreted_intent, ArchitecturalChangeIntent):
            raise ValueError("interpreted_intent must be ArchitecturalChangeIntent")
        _require_text_tuple(self.affected_entities, "affected_entities")
        if self.quality_result is not None and not isinstance(
            self.quality_result, Mapping
        ):
            raise ValueError("quality_result must be a mapping or None")
        _require_text(self.user_approval_status, "user_approval_status")


ContractT = TypeVar(
    "ContractT",
    ArchitecturalChangeIntent,
    DesignChangeImpact,
    DeclarativeChangePlan,
    ExecutionReadinessResult,
    ArchitecturalChangeStrategy,
    StrategyGenerationResult,
    GeometryDelta,
    GeometryRealizationResult,
    TopologyDelta,
    AdjacencyRealizationResult,
    OpeningAccessDelta,
    OpeningAccessRealizationResult,
    MultiRealizerTransactionPlan,
    TransactionStepResult,
    MultiRealizerTransactionResult,
    DesignVariant,
    DesignRevisionRecord,
)


class ArchitecturalChangeContractRegistry:
    """Minimal explicit registry for stable contract persistence."""

    def __init__(self) -> None:
        self._types: dict[str, type[Any]] = {}

    def register(self, contract_type: type[ContractT]) -> None:
        name = contract_type.__name__
        if name in self._types and self._types[name] is not contract_type:
            raise ValueError(f"contract type already registered: {name}")
        self._types[name] = contract_type

    @property
    def contract_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._types))

    def serialize(self, contract: ContractT) -> dict[str, Any]:
        contract_type = type(contract)
        name = contract_type.__name__
        if self._types.get(name) is not contract_type:
            raise ValueError(f"unregistered contract type: {name}")
        return {
            "schema_version": SCHEMA_VERSION,
            "contract_type": name,
            "data": _payload(contract),
        }

    def deserialize(self, envelope: Mapping[str, Any]) -> ContractT:
        if not isinstance(envelope, Mapping):
            raise ValueError("contract envelope must be a mapping")
        if envelope.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported architectural change contract schema")
        name = envelope.get("contract_type")
        contract_type = self._types.get(str(name))
        if contract_type is None:
            raise ValueError(f"unknown contract type: {name}")
        data = envelope.get("data")
        if not isinstance(data, Mapping):
            raise ValueError("contract data must be a mapping")
        values = deepcopy(dict(data))
        self._restore_tuples(contract_type, values)
        if contract_type is DesignRevisionRecord:
            intent = values.get("interpreted_intent")
            if not isinstance(intent, Mapping):
                raise ValueError("interpreted_intent must be a mapping")
            intent_values = deepcopy(dict(intent))
            self._restore_tuples(ArchitecturalChangeIntent, intent_values)
            values["interpreted_intent"] = ArchitecturalChangeIntent(**intent_values)
        if contract_type is StrategyGenerationResult:
            raw_strategies = values.get("strategies")
            if not isinstance(raw_strategies, (list, tuple)):
                raise ValueError("strategies must be a list or tuple")
            restored_strategies = []
            for raw_strategy in raw_strategies:
                if not isinstance(raw_strategy, Mapping):
                    raise ValueError("strategy must be a mapping")
                strategy_values = deepcopy(dict(raw_strategy))
                self._restore_tuples(ArchitecturalChangeStrategy, strategy_values)
                restored_strategies.append(ArchitecturalChangeStrategy(**strategy_values))
            values["strategies"] = tuple(restored_strategies)
        if contract_type is GeometryRealizationResult:
            raw_changes = values.get("geometry_changes")
            if not isinstance(raw_changes, (list, tuple)):
                raise ValueError("geometry_changes must be a list or tuple")
            restored_changes = []
            for raw_change in raw_changes:
                if not isinstance(raw_change, Mapping):
                    raise ValueError("geometry change must be a mapping")
                change_values = deepcopy(dict(raw_change))
                self._restore_tuples(GeometryDelta, change_values)
                restored_changes.append(GeometryDelta(**change_values))
            values["geometry_changes"] = tuple(restored_changes)
        if contract_type is AdjacencyRealizationResult:
            raw_changes = values.get("topology_changes")
            if not isinstance(raw_changes, (list, tuple)):
                raise ValueError("topology_changes must be a list or tuple")
            restored_changes = []
            for raw_change in raw_changes:
                if not isinstance(raw_change, Mapping):
                    raise ValueError("topology change must be a mapping")
                change_values = deepcopy(dict(raw_change))
                self._restore_tuples(TopologyDelta, change_values)
                restored_changes.append(TopologyDelta(**change_values))
            values["topology_changes"] = tuple(restored_changes)
        if contract_type is OpeningAccessRealizationResult:
            raw_changes = values.get("opening_access_changes")
            if not isinstance(raw_changes, (list, tuple)):
                raise ValueError("opening_access_changes must be a list or tuple")
            restored_changes = []
            for raw_change in raw_changes:
                if not isinstance(raw_change, Mapping):
                    raise ValueError("opening/access change must be a mapping")
                change_values = deepcopy(dict(raw_change))
                self._restore_tuples(OpeningAccessDelta, change_values)
                boundary = change_values.get("boundary_segment")
                if isinstance(boundary, (list, tuple)):
                    change_values["boundary_segment"] = tuple(tuple(point) for point in boundary)
                restored_changes.append(OpeningAccessDelta(**change_values))
            values["opening_access_changes"] = tuple(restored_changes)
        if contract_type is MultiRealizerTransactionPlan:
            values["dependency_edges"] = tuple(tuple(edge) for edge in values.get("dependency_edges", ()))
        if contract_type is MultiRealizerTransactionResult:
            values["dependency_edges"] = tuple(tuple(edge) for edge in values.get("dependency_edges", ()))
            raw_steps = values.get("step_results")
            if not isinstance(raw_steps, (list, tuple)):
                raise ValueError("step_results must be a list or tuple")
            restored_steps = []
            for raw_step in raw_steps:
                if not isinstance(raw_step, Mapping):
                    raise ValueError("transaction step result must be a mapping")
                step_values = deepcopy(dict(raw_step))
                self._restore_tuples(TransactionStepResult, step_values)
                restored_steps.append(TransactionStepResult(**step_values))
            values["step_results"] = tuple(restored_steps)
        return contract_type(**values)

    @staticmethod
    def _restore_tuples(contract_type: type[Any], values: dict[str, Any]) -> None:
        tuple_fields = {
            ArchitecturalChangeIntent: (
                "targets",
                "hard_constraints",
                "soft_objectives",
                "preserve_constraints",
            ),
            DesignChangeImpact: (
                "affected_spaces",
                "affected_relations",
                "affected_openings",
                "affected_windows_or_daylight",
                "affected_circulation",
                "possible_conflicts",
                "required_rechecks",
                "risk_flags",
                "feasibility_reasons",
                "evidence",
            ),
            DeclarativeChangePlan: (
                "proposed_operations",
                "target_entities",
                "preserve_constraints",
                "prerequisites",
                "rejection_conditions",
                "required_rechecks",
                "deferred_dependencies",
                "planning_reasons",
                "evidence",
            ),
            ExecutionReadinessResult: (
                "unresolved_dependencies",
                "constraint_conflicts",
                "preservation_requirements",
                "required_checks_before_execution",
                "rejection_reasons",
                "evidence",
            ),
            ArchitecturalChangeStrategy: (
                "target_entities",
                "proposed_semantic_actions",
                "required_tradeoffs",
                "preserved_constraints",
                "prerequisites",
                "expected_impacts",
                "risks",
                "required_rechecks",
                "evidence",
            ),
            StrategyGenerationResult: (
                "strategies",
                "blocker_reasons",
                "evidence",
            ),
            GeometryDelta: ("affected_neighbors",),
            GeometryRealizationResult: (
                "affected_entities", "geometry_changes", "preserved_entities",
                "applied_operations", "rejected_operations", "constraint_checks",
                "geometry_checks", "required_downstream_rechecks", "warnings", "failures",
            ),
            TopologyDelta: (
                "relation_pair", "affected_spaces", "affected_connections",
                "affected_circulation", "topology_operations", "preserved_constraints",
            ),
            AdjacencyRealizationResult: (
                "topology_changes", "affected_entities", "preserved_entities",
                "applied_operations", "rejected_operations", "constraint_checks",
                "topology_checks", "access_checks", "required_downstream_rechecks",
                "warnings", "failures",
            ),
            OpeningAccessDelta: (
                "target_space_pair", "boundary_segment", "affected_access_edges",
                "affected_circulation", "preserved_constraints",
            ),
            OpeningAccessRealizationResult: (
                "opening_access_changes", "affected_entities", "applied_operations",
                "rejected_operations", "geometry_checks", "access_checks",
                "circulation_checks", "constraint_checks", "required_downstream_rechecks",
                "warnings", "failures",
            ),
            MultiRealizerTransactionPlan: (
                "ordered_strategy_ids", "ordered_realizer_steps", "dependency_edges",
            ),
            TransactionStepResult: (
                "deltas", "invariant_checks", "warnings", "failures",
            ),
            MultiRealizerTransactionResult: (
                "ordered_strategy_ids", "ordered_realizer_steps", "dependency_edges",
                "step_results", "aggregate_deltas", "invariant_checks", "warnings", "failures",
            ),
            DesignVariant: ("preserved_constraints",),
            DesignRevisionRecord: ("child_revision_ids", "affected_entities"),
        }[contract_type]
        for field_name in tuple_fields:
            if field_name in values:
                raw = values[field_name]
                if not isinstance(raw, (list, tuple)):
                    raise ValueError(f"{field_name} must be a list or tuple")
                values[field_name] = tuple(raw)


CHANGE_CONTRACT_REGISTRY = ArchitecturalChangeContractRegistry()
for _contract_type in (
    ArchitecturalChangeIntent,
    DesignChangeImpact,
    DeclarativeChangePlan,
    ExecutionReadinessResult,
    ArchitecturalChangeStrategy,
    StrategyGenerationResult,
    GeometryDelta,
    GeometryRealizationResult,
    TopologyDelta,
    AdjacencyRealizationResult,
    OpeningAccessDelta,
    OpeningAccessRealizationResult,
    MultiRealizerTransactionPlan,
    TransactionStepResult,
    MultiRealizerTransactionResult,
    DesignVariant,
    DesignRevisionRecord,
):
    CHANGE_CONTRACT_REGISTRY.register(_contract_type)


def serialize_contract(contract: ContractT) -> dict[str, Any]:
    return CHANGE_CONTRACT_REGISTRY.serialize(contract)


def deserialize_contract(envelope: Mapping[str, Any]) -> ContractT:
    return CHANGE_CONTRACT_REGISTRY.deserialize(envelope)


def dumps_contract(contract: ContractT) -> str:
    """Serialize deterministically for storage, hashing, and audit trails."""
    return json.dumps(
        serialize_contract(contract),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def loads_contract(document: str) -> ContractT:
    if not isinstance(document, str):
        raise ValueError("contract document must be a string")
    return deserialize_contract(json.loads(document))


__all__ = [
    "SCHEMA_VERSION",
    "PLANNING_STATUS_PLANNABLE",
    "PLANNING_STATUS_PLANNABLE_WITH_PREREQUISITES",
    "PLANNING_STATUS_SITE_DEPENDENT",
    "PLANNING_STATUS_GEOMETRY_DEPENDENT",
    "PLANNING_STATUS_REJECTED_BY_CONSTRAINT",
    "PLANNING_STATUS_INSUFFICIENT_EVIDENCE",
    "DECLARATIVE_CHANGE_PLANNING_STATUSES",
    "READINESS_STATUS_READY",
    "READINESS_STATUS_READY_WITH_PREREQUISITES",
    "READINESS_STATUS_BLOCKED_SITE",
    "READINESS_STATUS_BLOCKED_GEOMETRY",
    "READINESS_STATUS_BLOCKED_CONSTRAINT",
    "READINESS_STATUS_INSUFFICIENT_EVIDENCE",
    "EXECUTION_READINESS_STATUSES",
    "STRATEGY_GENERATION_STATUS_GENERATED",
    "STRATEGY_GENERATION_STATUS_BLOCKED_READINESS",
    "STRATEGY_GENERATION_STATUSES",
    "STRATEGY_APPLICABILITY_APPLICABLE",
    "STRATEGY_APPLICABILITY_WITH_PREREQUISITES",
    "STRATEGY_APPLICABILITY_STATUSES",
    "GEOMETRY_REALIZATION_STATUS_REALIZED",
    "GEOMETRY_REALIZATION_STATUS_REALIZED_WITH_WARNINGS",
    "GEOMETRY_REALIZATION_STATUS_REJECTED_CONSTRAINT",
    "GEOMETRY_REALIZATION_STATUS_REJECTED_GEOMETRY",
    "GEOMETRY_REALIZATION_STATUS_STALE_PARENT",
    "GEOMETRY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY",
    "GEOMETRY_REALIZATION_STATUS_FAILED",
    "GEOMETRY_REALIZATION_STATUSES",
    "TOPOLOGY_REALIZATION_STATUS_REALIZED",
    "TOPOLOGY_REALIZATION_STATUS_REALIZED_WITH_WARNINGS",
    "TOPOLOGY_REALIZATION_STATUS_REJECTED_CONSTRAINT",
    "TOPOLOGY_REALIZATION_STATUS_REJECTED_TOPOLOGY",
    "TOPOLOGY_REALIZATION_STATUS_STALE_PARENT",
    "TOPOLOGY_REALIZATION_STATUS_UNSUPPORTED_STRATEGY",
    "TOPOLOGY_REALIZATION_STATUS_FAILED",
    "TOPOLOGY_REALIZATION_STATUSES",
    "OPENING_ACCESS_REALIZATION_STATUS_REALIZED",
    "OPENING_ACCESS_REALIZATION_STATUS_REALIZED_WITH_WARNINGS",
    "OPENING_ACCESS_REALIZATION_STATUS_REJECTED_CONSTRAINT",
    "OPENING_ACCESS_REALIZATION_STATUS_REJECTED_OPENING_GEOMETRY",
    "OPENING_ACCESS_REALIZATION_STATUS_REJECTED_ACCESS",
    "OPENING_ACCESS_REALIZATION_STATUS_STALE_PARENT",
    "OPENING_ACCESS_REALIZATION_STATUS_UNSUPPORTED_STRATEGY",
    "OPENING_ACCESS_REALIZATION_STATUS_FAILED",
    "OPENING_ACCESS_REALIZATION_STATUSES",
    "TRANSACTION_STATUS_COMMITTED",
    "TRANSACTION_STATUS_COMMITTED_WITH_WARNINGS",
    "TRANSACTION_STATUS_REJECTED_DEPENDENCY_ORDER",
    "TRANSACTION_STATUS_REJECTED_CONSTRAINT",
    "TRANSACTION_STATUS_REJECTED_STEP_FAILURE",
    "TRANSACTION_STATUS_STALE_PARENT",
    "TRANSACTION_STATUS_UNSUPPORTED_STRATEGY_SEQUENCE",
    "TRANSACTION_STATUS_FAILED",
    "MULTI_REALIZER_TRANSACTION_STATUSES",
    "ArchitecturalChangeIntent",
    "DesignChangeImpact",
    "DeclarativeChangePlan",
    "ExecutionReadinessResult",
    "ArchitecturalChangeStrategy",
    "StrategyGenerationResult",
    "GeometryDelta",
    "GeometryRealizationResult",
    "TopologyDelta",
    "AdjacencyRealizationResult",
    "OpeningAccessDelta",
    "OpeningAccessRealizationResult",
    "MultiRealizerTransactionPlan",
    "TransactionStepResult",
    "MultiRealizerTransactionResult",
    "DesignVariant",
    "DesignRevisionRecord",
    "ArchitecturalChangeContractRegistry",
    "CHANGE_CONTRACT_REGISTRY",
    "serialize_contract",
    "deserialize_contract",
    "dumps_contract",
    "loads_contract",
]
