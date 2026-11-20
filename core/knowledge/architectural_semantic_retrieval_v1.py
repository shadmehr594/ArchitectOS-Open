"""Transient retrieval boundary for ArchitecturalSemanticLibraryCandidateV1."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalSemanticRetrievalResultV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalSemanticLibraryCandidateV1"
SOURCE_VERSION = "1.0"

_NON_CLAIMS = (
    "not_design_reasoning",
    "not_recommendation",
    "not_rule",
    "not_geometry",
)
_FORBIDDEN_TERMS = (
    "should",
    "must",
    "required",
    "optimal",
    "best",
    "recommended",
    "design_solution",
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


def _validate_library(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalSemanticRetrievalResultV1 requires an "
            "ArchitecturalSemanticLibraryCandidateV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalSemanticRetrievalResultV1 accepts only "
            "ArchitecturalSemanticLibraryCandidateV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalSemanticRetrievalResultV1 requires library version 1.0"
        )
    return value


def _query_terms(query: Any) -> List[str]:
    if isinstance(query, dict):
        values = []
        for key in ("semantic_group", "group", "pattern", "query"):
            values.extend(_list(query.get(key)))
    else:
        values = _list(query)
    return [value.strip().lower() for value in values if isinstance(value, str) and value.strip()]


def _match_status(group: Dict[str, Any], matched: List[str], terms: List[str]) -> str:
    if not matched:
        return "unresolved_match"
    group_name = str(group.get("group") or "").lower()
    if any(term == group_name for term in terms):
        return "semantic_match"
    return "bounded_match"


def _matches(group: Dict[str, Any], terms: List[str]) -> List[str]:
    patterns = [pattern for pattern in _list(group.get("patterns")) if isinstance(pattern, str)]
    group_name = group.get("group")
    matched = []
    for pattern in patterns:
        if any(term == pattern.lower() or term in pattern.lower() for term in terms):
            matched.append(pattern)
    if any(term == str(group_name or "").lower() for term in terms):
        matched = patterns
    return _unique(matched)


def _match_object(group: Dict[str, Any], matched: List[str], terms: List[str]) -> Dict[str, Any]:
    return {
        "semantic_group": group.get("group") or "",
        "matched_patterns": matched,
        "source_evidence": _list(group.get("evidence_reference")),
        "uncertainty": deepcopy(group.get("uncertainty") or {}),
        "status": _match_status(group, matched, terms),
    }


def _assert_safe(value: Any) -> None:
    text = str(value).lower()
    for term in _FORBIDDEN_TERMS:
        if term in text:
            raise AssertionError(
                "ArchitecturalSemanticRetrievalResultV1 emitted forbidden term: "
                + term
            )


def retrieve_architectural_semantic_patterns_v1(
    semantic_library: Dict[str, Any],
    query: Any,
) -> Dict[str, Any]:
    """Retrieve matching semantic groups/patterns without inference or mutation."""
    library = _validate_library(semantic_library)
    terms = _query_terms(query)
    query_copy = deepcopy(query)
    groups = [
        group
        for group in _list(library.get("semantic_groups"))
        if isinstance(group, dict)
    ]
    matches = [
        _match_object(group, _matches(group, terms), terms)
        for group in groups
        if _matches(group, terms)
    ]
    evidence_basis = [
        {
            "semantic_group": match["semantic_group"],
            "source_evidence": deepcopy(match["source_evidence"]),
            "uncertainty": deepcopy(match["uncertainty"]),
        }
        for match in matches
    ]
    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "query": query_copy,
        "matches": matches,
        "evidence_basis": evidence_basis,
        "uncertainty": {
            "library": deepcopy(library.get("uncertainty") or {}),
            "matched_groups": len(matches),
        },
        "non_claims": list(_NON_CLAIMS),
        "persistent": False,
    }
    _assert_safe(
        {key: value for key, value in result.items() if key != "non_claims"}
    )
    return result
