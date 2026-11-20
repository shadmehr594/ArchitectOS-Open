"""Transient ArchitecturalConceptUnderstandingV1 boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalConceptUnderstandingV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalFoundationKnowledgeAccessV1"
SOURCE_VERSION = "1.0"

_NON_CLAIMS = {
    "not_design_rule": True,
    "not_recommendation": True,
    "not_authoritative_knowledge": True,
    "not_memory": True,
    "not_learned_model": True,
    "not_design_solution": True,
}

_FORBIDDEN_TERMS = (
    "should",
    "must",
    "required",
    "optimal",
    "best",
    "recommended",
    "design_solution",
    "design_rule",
    "layout_rule",
    "placement",
    "geometry",
    "dimension",
    "cad",
    "bim",
    "ifc",
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


def _validate_access(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalConceptUnderstandingV1 requires an "
            "ArchitecturalFoundationKnowledgeAccessV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalConceptUnderstandingV1 accepts only "
            "ArchitecturalFoundationKnowledgeAccessV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalConceptUnderstandingV1 requires access version 1.0"
        )
    return value


def _concept_type(area: Any) -> str:
    return {
        "space_identity": "space_concept",
        "functional_relationship": "functional_association_concept",
        "semantic_zone": "semantic_zone_concept",
    }.get(area, "unresolved_concept")


def _semantic_label(patterns: List[Any], area: Any) -> str:
    if "sleeping_storage_relation" in patterns:
        return "sleeping_space_with_storage_association"
    if "sleeping_sanitary_relation" in patterns:
        return "sleeping_space_with_sanitary_association"
    if any("circulation" in str(pattern).lower() for pattern in patterns):
        return "circulation_related_semantic_context"
    if any("opening" in str(pattern).lower() for pattern in patterns):
        return "opening_related_semantic_context"
    if patterns:
        return str(patterns[0])
    return str(area or "unresolved_semantic_context")


def build_architectural_concept_understanding_v1(
    foundation_access_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Build bounded concepts from FoundationKnowledgeAccessV1 only."""
    access = _validate_access(foundation_access_result)
    concepts = []
    source_patterns = []
    for match in _list(access.get("matches")):
        if not isinstance(match, dict):
            continue
        area = match.get("knowledge_area")
        patterns = _list(match.get("source_patterns"))
        source_patterns.extend(patterns)
        concepts.append(
            {
                "concept_type": _concept_type(area),
                "semantic_label": _semantic_label(patterns, area),
                "source_patterns": patterns,
                "evidence_reference": _list(match.get("evidence_reference")),
                "uncertainty": deepcopy(match.get("uncertainty") or {}),
                "status": "bounded_concept_understanding",
            }
        )

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "concepts": concepts,
        "source_patterns": _unique(source_patterns),
        "evidence_basis": deepcopy(access.get("source_evidence") or []),
        "uncertainty": deepcopy(access.get("uncertainty") or {}),
        "non_claims": deepcopy(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }
    payload = {key: value for key, value in result.items() if key != "non_claims"}
    serialized = str(payload).lower()
    for term in _FORBIDDEN_TERMS:
        if term in serialized:
            raise AssertionError(
                "ArchitecturalConceptUnderstandingV1 emitted forbidden term: "
                + term
            )
    return result
