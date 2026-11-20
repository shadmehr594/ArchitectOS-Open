"""Minimal 01G wiring from an explicit 01E selection to the existing 01F-D API.

The 01E strategy contract is intentionally semantic.  This adapter does not
select a strategy or invent realization evidence: callers must supply both the
selected strategy and authoritative execution bindings.  It only produces
uniquely identified strategy applications and the transaction plan required by
the frozen 01F-D coordinator.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import replace
from typing import Any

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeStrategy,
    ExecutionReadinessResult,
    MultiRealizerTransactionPlan,
    READINESS_STATUS_READY,
    READINESS_STATUS_READY_WITH_PREREQUISITES,
)
from core.architecture.reasoning.architectural_change_space_geometry_realizer_v1 import (
    candidate_semantic_hash,
)


ADMITTED_READINESS_STATUSES = frozenset({
    READINESS_STATUS_READY,
    READINESS_STATUS_READY_WITH_PREREQUISITES,
})

_EVIDENCE_KEY_BY_STEP = {
    "SPACE_BOUNDARY_REALIZATION": "area_transfer",
    "ADJACENCY_TOPOLOGY_REALIZATION": "topology_realization",
    "OPENING_ACCESS_REALIZATION": "opening_access_realization",
}


def prepare_explicitly_selected_transaction(
    selected_strategy: ArchitecturalChangeStrategy,
    readiness: ExecutionReadinessResult,
    parent_candidate: Mapping[str, Any],
    *,
    transaction_id: str,
    execution_bindings: Sequence[Mapping[str, Any]],
    dependency_edges: tuple[tuple[str, str], ...] = (),
    lineage: Mapping[str, Any] | None = None,
) -> tuple[
    MultiRealizerTransactionPlan,
    tuple[ArchitecturalChangeStrategy, ...],
    dict[str, ExecutionReadinessResult],
]:
    """Bind caller-proved evidence to one explicitly selected semantic strategy.

    Each binding must provide ``application_id``, ``realizer_step``, and an
    ``evidence`` mapping.  Geometry, topology, opening dimensions, and ordering
    remain caller-owned evidence; this function derives none of them.
    """
    if not isinstance(selected_strategy, ArchitecturalChangeStrategy):
        raise ValueError("selected_strategy must be ArchitecturalChangeStrategy")
    if not isinstance(readiness, ExecutionReadinessResult):
        raise ValueError("readiness must be ExecutionReadinessResult")
    if readiness.plan_id != selected_strategy.plan_id:
        raise ValueError("readiness and selected strategy plan identifiers must match")
    if readiness.readiness_status not in ADMITTED_READINESS_STATUSES:
        raise ValueError("selected strategy readiness is not admitted for execution")
    if not isinstance(parent_candidate, Mapping):
        raise ValueError("parent_candidate must be a mapping")
    if not isinstance(transaction_id, str) or not transaction_id.strip():
        raise ValueError("transaction_id must be a non-empty string")
    if not execution_bindings:
        raise ValueError("execution_bindings must not be empty")

    candidate_id = parent_candidate.get("candidate_id") or parent_candidate.get("id")
    candidate_version = parent_candidate.get("candidate_version") or parent_candidate.get("version")
    if candidate_id is None or candidate_version is None:
        raise ValueError("parent candidate identity and version are required")

    applications: list[ArchitecturalChangeStrategy] = []
    ordered_steps: list[str] = []
    readiness_by_strategy: dict[str, ExecutionReadinessResult] = {}
    source_provenance = (
        deepcopy(dict(selected_strategy.provenance))
        if isinstance(selected_strategy.provenance, Mapping)
        else {}
    )
    lineage_value = deepcopy(dict(lineage)) if isinstance(lineage, Mapping) else {}

    for index, binding in enumerate(execution_bindings):
        if not isinstance(binding, Mapping):
            raise ValueError("each execution binding must be a mapping")
        application_id = binding.get("application_id")
        step = binding.get("realizer_step")
        evidence = binding.get("evidence")
        if not isinstance(application_id, str) or not application_id.strip():
            raise ValueError("execution binding application_id must be non-empty")
        if step not in _EVIDENCE_KEY_BY_STEP:
            raise ValueError(f"unsupported existing realizer step: {step}")
        if not isinstance(evidence, Mapping):
            raise ValueError("execution binding evidence must be a mapping")
        expected_family = step
        if evidence.get("execution_family") != expected_family:
            raise ValueError("execution evidence family must match realizer_step")
        if application_id in readiness_by_strategy:
            raise ValueError("execution application identifiers must be unique")

        provenance = deepcopy(source_provenance)
        provenance.update({
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01G",
            "selection_mode": "EXPLICIT_CALLER_SELECTION",
            "selected_semantic_strategy_id": selected_strategy.strategy_id,
            "execution_application_index": index,
            "acceptance_lineage": deepcopy(lineage_value),
            _EVIDENCE_KEY_BY_STEP[step]: deepcopy(dict(evidence)),
        })
        application = replace(
            selected_strategy,
            strategy_id=application_id,
            provenance=provenance,
        )
        applications.append(application)
        ordered_steps.append(step)
        readiness_by_strategy[application_id] = readiness

    plan = MultiRealizerTransactionPlan(
        transaction_id=transaction_id,
        parent_candidate_id=str(candidate_id),
        parent_candidate_hash=candidate_semantic_hash(parent_candidate),
        parent_candidate_version=str(candidate_version),
        ordered_strategy_ids=tuple(item.strategy_id for item in applications),
        ordered_realizer_steps=tuple(ordered_steps),
        dependency_edges=dependency_edges,
        provenance={
            "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01G",
            "selection_mode": "EXPLICIT_CALLER_SELECTION",
            "selected_semantic_strategy_id": selected_strategy.strategy_id,
            "acceptance_lineage": lineage_value,
            "execution_evidence_derived": False,
        },
    )
    return plan, tuple(applications), readiness_by_strategy


__all__ = [
    "ADMITTED_READINESS_STATUSES",
    "prepare_explicitly_selected_transaction",
]
