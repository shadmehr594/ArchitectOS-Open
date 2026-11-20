"""Transient Architectural Semantic Library Candidate V1.

This module organizes validated teaching-session patterns into bounded semantic
groups. It does not write memory, promote knowledge, or create design rules.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalSemanticLibraryCandidateV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalTeachingSessionV1"
SOURCE_VERSION = "1.0"

_NON_CLAIMS = (
    "not_design_rule",
    "not_recommendation",
    "not_permanent_memory",
    "not_authoritative_knowledge",
)

_GROUP_BY_PATTERN = {
    "sleeping_storage_relation": "sleeping_space_association",
    "sleeping_sanitary_relation": "sleeping_space_association",
}

_FORBIDDEN_TERMS = (
    "rule",
    "standard",
    "requirement",
    "optimal_solution",
    "recommendation",
    "best_practice",
    "design_rule",
    "should",
    "must",
    "required",
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


def _validate_session(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalSemanticLibraryCandidateV1 requires an "
            "ArchitecturalTeachingSessionV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalSemanticLibraryCandidateV1 accepts only "
            "ArchitecturalTeachingSessionV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalSemanticLibraryCandidateV1 requires session version 1.0"
        )
    return value


def _group_for_pattern(pattern: Any) -> str:
    if pattern in _GROUP_BY_PATTERN:
        return _GROUP_BY_PATTERN[pattern]
    return "unresolved_architectural_association"


def _group_status(patterns: List[str]) -> str:
    if not patterns:
        return "unresolved_group"
    if all(pattern in _GROUP_BY_PATTERN for pattern in patterns):
        return "observed_semantic_group"
    return "bounded_pattern_group"


def _record_evidence(record: Dict[str, Any]) -> List[Any]:
    return _list(record.get("evidence_reference"))


def _record_uncertainty(record: Dict[str, Any]) -> Dict[str, Any]:
    value = record.get("uncertainty")
    return deepcopy(value) if isinstance(value, dict) else {}


def _record_source_pattern(record: Dict[str, Any]) -> Any:
    return record.get("source_pattern")


def _build_group(
    group_name: str,
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    patterns = _unique(
        _record_source_pattern(record)
        for record in records
        if _record_source_pattern(record)
    )
    evidence = _unique(
        evidence
        for record in records
        for evidence in _record_evidence(record)
    )
    grounding = _unique(
        status
        for record in records
        for status in _list(record.get("grounding_status"))
    )
    claim_ids = _unique(
        claim_id
        for record in records
        for claim_id in _list(record.get("source_claim_ids"))
    )
    uncertainties = [
        _record_uncertainty(record)
        for record in records
        if _record_uncertainty(record)
    ]
    return {
        "group": group_name,
        "patterns": patterns,
        "status": _group_status(patterns),
        "claim_ids": claim_ids,
        "evidence_reference": evidence,
        "grounding_status": grounding,
        "uncertainty": uncertainties,
    }


def _assert_safe(value: Any) -> None:
    text = str(value).lower()
    for term in _FORBIDDEN_TERMS:
        if term in text:
            raise AssertionError(
                "ArchitecturalSemanticLibraryCandidateV1 emitted forbidden term: "
                + term
            )


def build_architectural_semantic_library_candidate_v1(
    teaching_session: Dict[str, Any],
) -> Dict[str, Any]:
    """Group only a validated ArchitecturalTeachingSessionV1."""
    session = _validate_session(teaching_session)
    records = [
        record
        for record in _list(session.get("teaching_records"))
        if isinstance(record, dict)
    ]
    if not records:
        raise ValueError("ArchitecturalTeachingSessionV1 contains no teaching records")

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for record in records:
        group_name = _group_for_pattern(_record_source_pattern(record))
        if group_name not in grouped:
            grouped[group_name] = []
            order.append(group_name)
        grouped[group_name].append(record)

    semantic_groups = [
        _build_group(group_name, grouped[group_name])
        for group_name in order
    ]
    pattern_index = _unique(
        _record_source_pattern(record)
        for record in records
        if _record_source_pattern(record)
    )
    evidence_chain = [
        {
            "source_pattern": _record_source_pattern(record),
            "claim_ids": _list(record.get("source_claim_ids")),
            "evidence_reference": _record_evidence(record),
            "grounding_status": _list(record.get("grounding_status")),
            "uncertainty": _record_uncertainty(record),
        }
        for record in records
    ]
    uncertainty = {
        "session": deepcopy(session.get("uncertainty") or {}),
        "records": [
            _record_uncertainty(record)
            for record in records
            if _record_uncertainty(record)
        ],
    }

    candidate = {
        "contract": CONTRACT,
        "version": VERSION,
        "semantic_groups": semantic_groups,
        "pattern_index": pattern_index,
        "evidence_chain": evidence_chain,
        "uncertainty": uncertainty,
        "source_sessions": [
            {
                "contract": SOURCE_CONTRACT,
                "version": SOURCE_VERSION,
                "session_topic": session.get("session_topic"),
                "source_patterns": _list(session.get("source_patterns")),
            }
        ],
        "non_claims": list(_NON_CLAIMS),
        "persistent": False,
        "promoted": False,
    }
    _assert_safe(
        {
            key: value
            for key, value in candidate.items()
            if key != "non_claims"
        }
    )
    return candidate
