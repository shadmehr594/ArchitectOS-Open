"""Read-only access boundary for ArchitecturalFoundationKnowledgeSetV1."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalFoundationKnowledgeAccessV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalFoundationKnowledgeSetV1"
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

_AREAS = {
    "space_identity_cases": "space_identity",
    "functional_relationship_cases": "functional_relationship",
    "semantic_zone_cases": "semantic_zone",
}


def _list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return deepcopy(value)
    if isinstance(value, tuple):
        return deepcopy(list(value))
    if value is None:
        return []
    return [deepcopy(value)]


def _validate_foundation(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalFoundationKnowledgeAccessV1 requires an "
            "ArchitecturalFoundationKnowledgeSetV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalFoundationKnowledgeAccessV1 accepts only "
            "ArchitecturalFoundationKnowledgeSetV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalFoundationKnowledgeAccessV1 requires foundation version 1.0"
        )
    return value


def _query_terms(query: Any) -> List[str]:
    if isinstance(query, dict):
        values = []
        for key in ("area", "knowledge_area", "pattern", "source_pattern", "query"):
            value = query.get(key)
            if isinstance(value, list):
                values.extend(value)
            else:
                values.append(value)
    else:
        values = _list(query)
    return [
        value.strip().lower()
        for value in values
        if isinstance(value, str) and value.strip()
    ]


def _case_matches(case: Dict[str, Any], terms: List[str]) -> bool:
    if not terms:
        return True
    area = str(case.get("semantic_area") or "").lower()
    area_aliases = {
        "functional_association": "functional_relationship",
    }
    haystack = " ".join(
        [
            str(case.get(key) or "").lower()
            for key in ("source_pattern", "teaching_topic", "semantic_area")
        ]
        + [area_aliases.get(area, "")]
    )
    return any(term in haystack for term in terms)


def _source_case(case: Dict[str, Any]) -> Dict[str, Any]:
    return deepcopy(case)


def access_architectural_foundation_knowledge_v1(
    foundation_set: Dict[str, Any],
    query: Any,
) -> Dict[str, Any]:
    """Perform deterministic lookup over a foundation set only."""
    foundation = _validate_foundation(foundation_set)
    terms = _query_terms(query)
    matches = []
    for key, area in _AREAS.items():
        cases = [
            case
            for case in _list(foundation.get(key))
            if isinstance(case, dict) and _case_matches(case, terms)
        ]
        if not cases:
            continue
        matches.append(
            {
                "knowledge_area": area,
                "source_cases": [_source_case(case) for case in cases],
                "source_patterns": [
                    case.get("source_pattern") for case in cases
                    if case.get("source_pattern") is not None
                ],
                "evidence_reference": [
                    evidence
                    for case in cases
                    for evidence in _list(case.get("evidence_reference"))
                ],
                "uncertainty": [
                    deepcopy(case.get("uncertainty"))
                    for case in cases
                    if case.get("uncertainty")
                ],
                "status": "bounded_access_match",
            }
        )

    source_evidence = deepcopy(foundation.get("source_evidence") or [])
    if terms:
        source_patterns = {
            pattern
            for match in matches
            for pattern in match["source_patterns"]
        }
        source_evidence = [
            item
            for item in source_evidence
            if not source_patterns
            or item.get("source_pattern") in source_patterns
        ]

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "matches": matches,
        "source_evidence": source_evidence,
        "uncertainty": deepcopy(foundation.get("uncertainty") or {}),
        "non_claims": deepcopy(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }
    payload = {key: value for key, value in result.items() if key != "non_claims"}
    serialized = str(payload).lower()
    for term in _FORBIDDEN_TERMS:
        if term in serialized:
            raise AssertionError(
                "ArchitecturalFoundationKnowledgeAccessV1 emitted forbidden term: "
                + term
            )
    return result
