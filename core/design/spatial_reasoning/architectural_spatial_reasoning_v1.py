"""Transient ArchitecturalSpatialReasoningCandidateV1 boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalSpatialReasoningCandidateV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalDesignReasoningResultV1"
SOURCE_VERSION = "1.0"

_NON_CLAIMS = (
    "not_layout",
    "not_placement",
    "not_geometry",
    "not_cad",
    "not_bim",
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
    "adjacent",
    "layout",
    "dimension",
    "geometry",
)

_DOMAIN_BY_REASONING_TYPE = {
    "space_identity_reasoning": "private_sleeping_zone",
    "semantic_group_reasoning": "circulation_zone",
    "functional_relationship_reasoning": "opening_related_zone",
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


def _validate_reasoning(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalSpatialReasoningCandidateV1 requires an "
            "ArchitecturalDesignReasoningResultV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalSpatialReasoningCandidateV1 accepts only "
            "ArchitecturalDesignReasoningResultV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalSpatialReasoningCandidateV1 requires reasoning version 1.0"
        )
    return value


def build_spatial_reasoning_candidate_v1(
    reasoning_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Map bounded reasoning statements to spatial semantic candidates."""
    source = _validate_reasoning(reasoning_result)
    statements = [
        statement
        for statement in _list(source.get("reasoning_statements"))
        if isinstance(statement, dict)
    ]
    candidates = []
    for statement in statements:
        domain = _DOMAIN_BY_REASONING_TYPE.get(statement.get("type"))
        if not domain:
            continue
        candidates.append(
            {
                "spatial_domain": domain,
                "source_reasoning": [statement.get("type")],
                "status": "bounded_spatial_candidate",
                "evidence_reference": _list(
                    statement.get("evidence_reference")
                ),
                "uncertainty": deepcopy(statement.get("uncertainty") or {}),
            }
        )

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "spatial_candidates": candidates,
        "reasoning_basis": deepcopy(source.get("intent_basis") or []),
        "evidence_basis": deepcopy(source.get("evidence_basis") or []),
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
                "ArchitecturalSpatialReasoningCandidateV1 emitted forbidden term: "
                + term
            )
    return result
