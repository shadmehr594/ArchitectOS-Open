"""Transient ArchitecturalFoundationKnowledgeSetV1 container."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalFoundationKnowledgeSetV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalKnowledgeCurriculumV1"
SOURCE_VERSION = "1.0"

_NON_CLAIMS = {
    "not_design_rule": True,
    "not_recommendation": True,
    "not_authoritative_standard": True,
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


def _validate_curriculum(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalFoundationKnowledgeSetV1 requires an "
            "ArchitecturalKnowledgeCurriculumV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalFoundationKnowledgeSetV1 accepts only "
            "ArchitecturalKnowledgeCurriculumV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalFoundationKnowledgeSetV1 requires curriculum version 1.0"
        )
    return value


def _case_area(case: Dict[str, Any]) -> str:
    area = case.get("semantic_area")
    if area in {"space_identity", "functional_association", "semantic_zone"}:
        return area
    return "unresolved"


def _case_copy(case: Dict[str, Any]) -> Dict[str, Any]:
    return deepcopy(case)


def build_architectural_foundation_knowledge_set_v1(
    curriculum: Dict[str, Any],
) -> Dict[str, Any]:
    """Organize only an ArchitecturalKnowledgeCurriculumV1."""
    source = _validate_curriculum(curriculum)
    cases = [
        case
        for case in _list(source.get("learning_cases"))
        if isinstance(case, dict)
    ]
    if not cases:
        raise ValueError("ArchitecturalKnowledgeCurriculumV1 contains no learning cases")

    grouped = {
        "space_identity": [],
        "functional_association": [],
        "semantic_zone": [],
    }
    for case in cases:
        area = _case_area(case)
        if area in grouped:
            grouped[area].append(_case_copy(case))

    source_evidence = _list(source.get("source_evidence"))
    if not source_evidence:
        source_evidence = [
            {
                "source_pattern": case.get("source_pattern"),
                "source_claim_ids": _list(case.get("source_claim_ids")),
                "evidence_reference": _list(case.get("evidence_reference")),
                "grounding_status": _list(case.get("grounding_status")),
            }
            for case in cases
        ]

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "knowledge_domain": "foundation_spatial_semantics",
        "space_identity_cases": grouped["space_identity"],
        "functional_relationship_cases": grouped["functional_association"],
        "semantic_zone_cases": grouped["semantic_zone"],
        "source_curriculum": deepcopy(cases),
        "source_evidence": source_evidence,
        "uncertainty": deepcopy(source.get("uncertainty") or {}),
        "non_claims": deepcopy(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }
    payload = {
        key: value for key, value in result.items() if key != "non_claims"
    }
    serialized = str(payload).lower()
    for term in _FORBIDDEN_TERMS:
        if term in serialized:
            raise AssertionError(
                "ArchitecturalFoundationKnowledgeSetV1 emitted forbidden term: "
                + term
            )
    return result
