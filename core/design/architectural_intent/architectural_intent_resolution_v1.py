"""Transient ArchitecturalIntentResolutionV1 grouping boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalIntentResolutionV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalIntentCandidateV1"
SOURCE_VERSION = "1.0"

_NON_CLAIMS = (
    "not_design_reasoning",
    "not_layout",
    "not_geometry",
    "not_rule",
)

_FORBIDDEN_TERMS = (
    "should",
    "must",
    "required",
    "optimal",
    "best",
    "recommended",
    "adjacent",
    "place",
    "layout",
    "geometry",
)

_GROUP_ORDER = (
    "private_sleeping_zone_intent",
    "circulation_zone_intent",
    "opening_relationship_intent",
)


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


def _validate_candidate(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalIntentResolutionV1 requires an "
            "ArchitecturalIntentCandidateV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalIntentResolutionV1 accepts only "
            "ArchitecturalIntentCandidateV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalIntentResolutionV1 requires intent version 1.0"
        )
    return value


def _resolved_group(intent_types: Iterable[str]) -> str | None:
    types = set(intent_types)
    if {
        "sleeping_private_space_intent",
        "storage_associated_intent",
        "sanitary_service_associated_intent",
    }.issubset(types):
        return "private_sleeping_zone_intent"
    if "circulation_associated_intent" in types:
        return "circulation_zone_intent"
    if "opening_relationship_intent" in types:
        return "opening_relationship_intent"
    return None


def _group_status(source_intents: List[Dict[str, Any]]) -> str:
    if not source_intents:
        return "unresolved_group"
    if all(
        item.get("status") == "bounded_intent_candidate"
        for item in source_intents
    ):
        return "bounded_pattern_group"
    return "unresolved_group"


def _build_group(
    group_name: str,
    source_intents: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "intent_group": group_name,
        "source_intents": [
            item.get("intent_type") for item in source_intents
        ],
        "status": _group_status(source_intents),
        "source_patterns": _unique(
            pattern
            for item in source_intents
            for pattern in _list(item.get("source_pattern"))
        ),
        "evidence_reference": _unique(
            evidence
            for item in source_intents
            for evidence in _list(item.get("evidence_reference"))
        ),
        "uncertainty": [
            deepcopy(item.get("uncertainty"))
            for item in source_intents
            if item.get("uncertainty")
        ],
    }


def resolve_architectural_intent_v1(
    intent_candidate: Dict[str, Any],
) -> Dict[str, Any]:
    """Normalize only an ArchitecturalIntentCandidateV1."""
    candidate = _validate_candidate(intent_candidate)
    intents = [
        item
        for item in _list(candidate.get("intent_candidates"))
        if isinstance(item, dict) and item.get("intent_type")
    ]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    all_intent_types = [item["intent_type"] for item in intents]
    complete_private_sleeping = _resolved_group(all_intent_types)
    if complete_private_sleeping:
        grouped[complete_private_sleeping] = [
            item
            for item in intents
            if item["intent_type"] in {
                "sleeping_private_space_intent",
                "storage_associated_intent",
                "sanitary_service_associated_intent",
            }
        ]
    for item in intents:
        intent_type = item["intent_type"]
        if intent_type in {
            "sleeping_private_space_intent",
            "storage_associated_intent",
            "sanitary_service_associated_intent",
        }:
            continue
        group_name = _resolved_group([intent_type])
        if group_name:
            grouped.setdefault(group_name, []).append(item)

    intent_groups = [
        _build_group(group_name, grouped[group_name])
        for group_name in _GROUP_ORDER
        if group_name in grouped
    ]
    semantic_components = _unique(
        group["intent_group"] for group in intent_groups
    )
    source_intents = _unique(
        item.get("intent_type") for item in intents
    )
    evidence_basis = deepcopy(candidate.get("evidence_basis") or [])
    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "intent_groups": intent_groups,
        "semantic_components": semantic_components,
        "source_intents": source_intents,
        "evidence_basis": evidence_basis,
        "uncertainty": deepcopy(candidate.get("uncertainty") or {}),
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
                "ArchitecturalIntentResolutionV1 emitted forbidden term: "
                + term
            )
    return result
