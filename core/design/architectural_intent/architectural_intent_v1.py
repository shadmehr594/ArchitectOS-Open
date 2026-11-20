"""Transient ArchitecturalIntentCandidateV1 boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalIntentCandidateV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalSemanticRetrievalResultV1"
SOURCE_VERSION = "1.0"

_NON_CLAIMS = (
    "not_design_reasoning",
    "not_design_solution",
    "not_geometry",
    "not_layout",
    "not_rule",
)

_FORBIDDEN_TERMS = (
    "should",
    "must",
    "required",
    "optimal",
    "best",
    "recommended",
    "design_solution",
    "layout_rule",
    "place_bed",
    "move_wall",
    "optimize_daylight",
    "recommended_plan",
)

_INTENTS_BY_PATTERN = {
    "sleeping_storage_relation": (
        "sleeping_private_space_intent",
        "storage_associated_intent",
    ),
    "sleeping_sanitary_relation": (
        "sleeping_private_space_intent",
        "sanitary_service_associated_intent",
    ),
    "opening_associated_with_space": (
        "opening_relationship_intent",
    ),
    "opening_within_facade_plane": (
        "opening_relationship_intent",
    ),
    "platform_connected_to_facade_plane": (
        "opening_relationship_intent",
    ),
    "entrance_threshold_in_facade_composition": (
        "circulation_associated_intent",
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


def _validate_retrieval(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalIntentCandidateV1 requires an "
            "ArchitecturalSemanticRetrievalResultV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalIntentCandidateV1 accepts only "
            "ArchitecturalSemanticRetrievalResultV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalIntentCandidateV1 requires retrieval version 1.0"
        )
    return value


def _intent_types(patterns: Iterable[Any]) -> List[str]:
    intents = []
    for pattern in patterns:
        for intent in _INTENTS_BY_PATTERN.get(pattern, ()):
            if intent not in intents:
                intents.append(intent)
    return intents


def _match_uncertainty(match: Dict[str, Any]) -> Any:
    return deepcopy(match.get("uncertainty"))


def _build_intent(
    intent_type: str,
    patterns: List[str],
    matches: List[Dict[str, Any]],
) -> Dict[str, Any]:
    evidence = _unique(
        evidence
        for match in matches
        for evidence in _list(match.get("source_evidence"))
    )
    uncertainty = [
        _match_uncertainty(match)
        for match in matches
        if _match_uncertainty(match)
    ]
    return {
        "intent_type": intent_type,
        "status": "bounded_intent_candidate",
        "source_pattern": patterns,
        "evidence_reference": evidence,
        "uncertainty": uncertainty,
    }


def _assert_safe(value: Any) -> None:
    text = str(value).lower()
    for term in _FORBIDDEN_TERMS:
        if term in text:
            raise AssertionError(
                "ArchitecturalIntentCandidateV1 emitted forbidden term: "
                + term
            )


def build_architectural_intent_candidate_v1(
    retrieval_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Build bounded intent candidates from retrieval results only."""
    retrieval = _validate_retrieval(retrieval_result)
    matches = [
        match
        for match in _list(retrieval.get("matches"))
        if isinstance(match, dict)
    ]

    patterns = _unique(
        pattern
        for match in matches
        for pattern in _list(match.get("matched_patterns"))
        if isinstance(pattern, str)
    )
    intent_types = _intent_types(patterns)
    intent_candidates = [
        _build_intent(
            intent_type,
            [
                pattern
                for pattern in patterns
                if intent_type in _INTENTS_BY_PATTERN.get(pattern, ())
            ],
            [
                match
                for match in matches
                if any(
                    intent_type in _INTENTS_BY_PATTERN.get(pattern, ())
                    for pattern in _list(match.get("matched_patterns"))
                )
            ],
        )
        for intent_type in intent_types
    ]

    evidence_basis = [
        {
            "semantic_group": match.get("semantic_group"),
            "matched_patterns": _list(match.get("matched_patterns")),
            "source_evidence": _list(match.get("source_evidence")),
            "uncertainty": _match_uncertainty(match),
        }
        for match in matches
    ]
    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "intent_candidates": intent_candidates,
        "source_patterns": patterns,
        "evidence_basis": evidence_basis,
        "uncertainty": deepcopy(retrieval.get("uncertainty") or {}),
        "non_claims": list(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }
    _assert_safe(
        {key: value for key, value in result.items() if key != "non_claims"}
    )
    return result
