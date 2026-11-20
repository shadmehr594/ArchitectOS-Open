"""Minimal post-selection binding from a semantic 01E strategy to 01H evidence."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from typing import Any

from core.architecture.contracts.architectural_change_contracts_v1 import (
    ArchitecturalChangeStrategy,
    ExecutionReadinessResult,
    READINESS_STATUS_READY,
    READINESS_STATUS_READY_WITH_PREREQUISITES,
)


ADMITTED_READINESS_STATUSES = frozenset({READINESS_STATUS_READY, READINESS_STATUS_READY_WITH_PREREQUISITES})
EXECUTION_FAMILY = "WINDOW_DAYLIGHT_REALIZATION"


def bind_explicitly_selected_daylight_strategy(
    selected_strategy: ArchitecturalChangeStrategy,
    readiness: ExecutionReadinessResult,
    *,
    application_id: str,
    execution_evidence: Mapping[str, Any],
    lineage: Mapping[str, Any] | None = None,
) -> ArchitecturalChangeStrategy:
    """Attach caller-proved execution evidence without selecting or ranking a strategy."""
    if not isinstance(selected_strategy, ArchitecturalChangeStrategy):
        raise ValueError("selected_strategy must be ArchitecturalChangeStrategy")
    if not isinstance(readiness, ExecutionReadinessResult):
        raise ValueError("readiness must be ExecutionReadinessResult")
    if readiness.plan_id != selected_strategy.plan_id:
        raise ValueError("readiness and selected strategy plan identifiers must match")
    if readiness.readiness_status not in ADMITTED_READINESS_STATUSES:
        raise ValueError("selected strategy readiness is not admitted for execution")
    if not isinstance(application_id, str) or not application_id.strip():
        raise ValueError("application_id must be a non-empty string")
    if not isinstance(execution_evidence, Mapping):
        raise ValueError("execution_evidence must be a mapping")
    if execution_evidence.get("execution_family") != EXECUTION_FAMILY:
        raise ValueError("execution evidence family must be WINDOW_DAYLIGHT_REALIZATION")
    provenance = (
        deepcopy(dict(selected_strategy.provenance))
        if isinstance(selected_strategy.provenance, Mapping)
        else {}
    )
    provenance.update({
        "phase": "ARCHITECTURAL-CHANGE-ORCHESTRATOR-01H",
        "selection_mode": "EXPLICIT_CALLER_SELECTION",
        "selected_semantic_strategy_id": selected_strategy.strategy_id,
        "window_daylight_realization": deepcopy(dict(execution_evidence)),
        "acceptance_lineage": deepcopy(dict(lineage)) if isinstance(lineage, Mapping) else {},
        "execution_evidence_derived": False,
    })
    return replace(selected_strategy, strategy_id=application_id, provenance=provenance)


__all__ = ["ADMITTED_READINESS_STATUSES", "EXECUTION_FAMILY", "bind_explicitly_selected_daylight_strategy"]
