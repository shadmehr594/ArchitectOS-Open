"""Transient Architectural Teaching Candidate V1.

This module prepares bounded teaching units from an
ArchitecturalKnowledgeStructureV1. It does not write memory, learn
automatically, promote knowledge, or generate design reasoning.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalTeachingCandidateV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalKnowledgeStructureV1"
SOURCE_VERSION = "1.0"

_NON_CLAIMS = (
    "not_memory",
    "not_learned_model",
    "not_design_rule",
    "not_authoritative_knowledge",
)

_FORBIDDEN_TERMS = (
    "why this design is good",
    "recommended layout",
    "optimal arrangement",
    "architectural rule",
    "should",
    "must",
    "required",
    "optimized",
    "best",
    "recommended",
)

_TOPIC_BY_PATTERN = {
    "sleeping_storage_relation": "sleeping_space_and_storage_association",
    "sleeping_sanitary_relation": "sleeping_space_and_sanitary_service_association",
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


def _validate_structure(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalTeachingCandidateV1 requires an "
            "ArchitecturalKnowledgeStructureV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalTeachingCandidateV1 accepts only "
            "ArchitecturalKnowledgeStructureV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalTeachingCandidateV1 requires structure version 1.0"
        )
    return value


def _claim_ids(item: Dict[str, Any]) -> List[Any]:
    return _list(item.get("source_claim_ids"))


def _evidence(item: Dict[str, Any]) -> List[Any]:
    return _list(item.get("evidence_reference"))


def _statuses(item: Dict[str, Any]) -> List[Any]:
    return _list(item.get("grounding_status"))


def _uncertainty(structure: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    result = {}
    source_uncertainty = structure.get("uncertainty")
    if isinstance(source_uncertainty, dict):
        result.update(deepcopy(source_uncertainty))
    item_uncertainty = item.get("uncertainty")
    if isinstance(item_uncertainty, dict):
        result["source_item"] = deepcopy(item_uncertainty)
    return result


def _topic(pattern: Any, association: Any) -> str:
    if pattern in _TOPIC_BY_PATTERN:
        return _TOPIC_BY_PATTERN[pattern]
    if association:
        return "%s_association" % association
    return str(pattern or "architectural_association")


def _source_pattern(item: Dict[str, Any], structure: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pattern": item.get("pattern"),
        "space": item.get("space"),
        "associated_element": item.get("associated_element"),
        "status": item.get("status"),
        "source_claim_ids": _claim_ids(item),
        "evidence_reference": _evidence(item),
        "grounding_status": _statuses(item),
        "uncertainty": _uncertainty(structure, item),
    }


def _teaching_unit_from_pattern(
    item: Dict[str, Any],
    structure: Dict[str, Any],
) -> Dict[str, Any]:
    pattern = item.get("pattern")
    association = item.get("associated_element")
    return {
        "topic": _topic(pattern, association),
        "source_pattern": pattern,
        "explanation_status": "needs_human_explanation",
        "evidence_reference": _evidence(item),
        "grounding_status": _statuses(item),
        "source_claim_ids": _claim_ids(item),
        "confidence": "bounded",
        "uncertainty": _uncertainty(structure, item),
    }


def build_architectural_teaching_candidate_v1(
    knowledge_structure: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a transient teaching container from a V1 knowledge structure."""
    structure = _validate_structure(knowledge_structure)
    patterns = [
        item
        for item in _list(structure.get("patterns"))
        if isinstance(item, dict)
    ]

    teaching_units = [
        _teaching_unit_from_pattern(item, structure)
        for item in patterns
    ]
    source_patterns = [
        _source_pattern(item, structure)
        for item in patterns
    ]

    evidence_basis = structure.get("evidence_basis")
    evidence_basis = deepcopy(evidence_basis) if isinstance(evidence_basis, dict) else {}
    evidence_basis["source_contract"] = SOURCE_CONTRACT
    evidence_basis["source_version"] = SOURCE_VERSION

    candidate = {
        "contract": CONTRACT,
        "version": VERSION,
        "teaching_units": teaching_units,
        "source_patterns": source_patterns,
        "evidence_basis": evidence_basis,
        "uncertainty": deepcopy(structure.get("uncertainty") or {}),
        "non_claims": list(_NON_CLAIMS),
        "is_training_input": True,
        "persistent": False,
    }

    serialized = str(candidate).lower()
    for term in _FORBIDDEN_TERMS:
        if term in serialized:
            raise AssertionError(
                "ArchitecturalTeachingCandidateV1 emitted forbidden teaching term: "
                + term
            )

    return candidate
