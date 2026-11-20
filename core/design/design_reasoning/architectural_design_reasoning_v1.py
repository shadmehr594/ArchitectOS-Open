"""Bounded ArchitecturalDesignReasoningResultV1 engine."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalDesignReasoningResultV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalDesignReasoningInputV1"
SOURCE_VERSION = "1.0"

_NON_CLAIMS = (
    "not_geometry",
    "not_cad",
    "not_bim",
    "not_layout_solution",
    "not_final_design",
)

_FORBIDDEN_TERMS = (
    "should",
    "must",
    "required",
    "optimal",
    "best",
    "recommended",
    "place",
    "move",
    "layout",
    "geometry",
    "dimension",
    "wall",
    "door",
    "window_position",
)

_STATEMENTS = {
    "private_sleeping_zone_intent": (
        "space_identity_reasoning",
        "Private sleeping-space semantic context is present.",
    ),
    "circulation_zone_intent": (
        "semantic_group_reasoning",
        "Circulation-related semantic context is present.",
    ),
    "opening_relationship_intent": (
        "functional_relationship_reasoning",
        "Opening relationship semantic context is present.",
    ),
}


def _list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return deepcopy(value)
    if isinstance(value, tuple):
        return deepcopy(list(value))
    if value is None:
        return []
    return [deepcopy(value)]


def _unique(values: Iterable[Any]) -> List[Any]:
    result = []
    for value in values:
        if value not in result:
            result.append(deepcopy(value))
    return result


def _validate_input(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalDesignReasoningResultV1 requires an "
            "ArchitecturalDesignReasoningInputV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalDesignReasoningResultV1 accepts only "
            "ArchitecturalDesignReasoningInputV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalDesignReasoningResultV1 requires input version 1.0"
        )
    return value


def _statement_for_group(
    group: Dict[str, Any],
    evidence_by_group: Dict[str, Dict[str, Any]],
) -> Dict[str, Any] | None:
    component = group.get("intent_group")
    definition = _STATEMENTS.get(component)
    if not definition:
        return None
    statement_type, text = definition
    evidence = evidence_by_group.get(component) or {}
    return {
        "type": statement_type,
        "statement": text,
        "basis": _list(
            evidence.get("source_patterns")
            or group.get("source_patterns")
        ),
        "evidence_reference": _list(
            evidence.get("evidence_reference")
            or group.get("evidence_reference")
        ),
        "uncertainty": deepcopy(
            group.get("uncertainty")
            or evidence.get("uncertainty")
            or {}
        ),
    }


def reason_architectural_design_v1(
    reasoning_input: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate bounded semantic reasoning statements only."""
    source = _validate_input(reasoning_input)
    groups = [
        group
        for group in _list(source.get("intent_context"))
        if isinstance(group, dict)
    ]
    evidence_by_group = {
        item.get("intent_group"): item
        for item in _list(source.get("source_evidence"))
        if isinstance(item, dict) and item.get("intent_group")
    }
    statements = []
    for group in groups:
        statement = _statement_for_group(group, evidence_by_group)
        if statement is not None:
            statements.append(statement)

    intent_basis = [
        {
            "intent_group": group.get("intent_group"),
            "source_intents": _list(group.get("source_intents")),
            "status": group.get("status"),
        }
        for group in groups
    ]
    evidence_basis = deepcopy(source.get("source_evidence") or [])
    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "reasoning_statements": statements,
        "intent_basis": intent_basis,
        "evidence_basis": evidence_basis,
        "uncertainty": deepcopy(source.get("uncertainty") or {}),
        "non_claims": list(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }
    text = str(
        {key: value for key, value in result.items() if key != "non_claims"}
    ).lower()
    for term in _FORBIDDEN_TERMS:
        if term in text:
            raise AssertionError(
                "ArchitecturalDesignReasoningResultV1 emitted forbidden term: "
                + term
            )
    return result
