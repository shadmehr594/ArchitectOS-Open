"""Transient Architectural Knowledge Candidate V1.

This module consumes only completed ArchitecturalUnderstandingV2 objects. It
extracts bounded architectural patterns and associations without promoting
them to permanent knowledge or producing design decisions.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalKnowledgeCandidateV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalUnderstandingV2"
SOURCE_VERSION = "2.0"

_FORBIDDEN_TERMS = (
    "should",
    "must",
    "required",
    "optimized",
    "best",
    "recommended",
    "design solution",
)

_NON_CLAIMS = (
    "not_permanent_knowledge",
    "not_design_reasoning",
    "not_geometry",
    "not_cad_or_bim",
    "not_promoted",
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


def _claim_index(v2: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        claim.get("claim_id"): claim
        for claim in _list(v2.get("claim_trace"))
        if isinstance(claim, dict) and claim.get("claim_id")
    }


def _claim_ids(item: Dict[str, Any]) -> List[str]:
    claim_id = item.get("claim_id")
    return [claim_id] if claim_id else []


def _evidence_from_item(item: Dict[str, Any]) -> List[Any]:
    return _list(item.get("evidence_reference"))


def _statuses_from_item(item: Dict[str, Any]) -> List[Any]:
    return _list(item.get("grounding_status"))


def _basis_from_claims(
    claim_ids: Iterable[str],
    claims: Dict[str, Dict[str, Any]],
) -> List[Any]:
    basis = []
    for claim_id in claim_ids:
        claim = claims.get(claim_id) or {}
        basis.extend(_list(claim.get("interpretation_basis")))
    return _unique(basis)


def _uncertainty_from_items(
    items: Iterable[Dict[str, Any]],
    source: Dict[str, Any],
) -> Dict[str, Any]:
    uncertainties = []
    for item in items:
        if isinstance(item, dict):
            uncertainty = item.get("uncertainty")
            if isinstance(uncertainty, dict):
                uncertainties.append(deepcopy(uncertainty))
    return {
        "source_confidence": source.get("uncertainty", {}).get("confidence")
        if isinstance(source.get("uncertainty"), dict)
        else None,
        "items": uncertainties,
        "unknowns": _list(
            source.get("uncertainty", {}).get("unknowns")
            if isinstance(source.get("uncertainty"), dict)
            else []
        ),
        "evidence_conflicts": _list(
            source.get("uncertainty", {}).get("evidence_conflicts")
            if isinstance(source.get("uncertainty"), dict)
            else []
        ),
    }


def _require_v2(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalKnowledgeCandidateV1 requires an ArchitecturalUnderstandingV2 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalKnowledgeCandidateV1 accepts only ArchitecturalUnderstandingV2"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalKnowledgeCandidateV1 requires ArchitecturalUnderstandingV2 version 2.0"
        )
    return value


def _assert_safe(value: Any) -> None:
    text = str(value).lower()
    for term in _FORBIDDEN_TERMS:
        if term in text:
            raise AssertionError(
                "ArchitecturalKnowledgeCandidateV1 emitted forbidden term: "
                + term
            )


def build_architectural_knowledge_candidate_v1(
    understanding_v2: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract a transient candidate from an ArchitecturalUnderstandingV2 object."""

    v2 = _require_v2(understanding_v2)
    claims = _claim_index(v2)
    semantic_space = v2.get("semantic_space") or {}
    space_label = semantic_space.get("label")
    functional = v2.get("functional_understanding") or {}

    role_candidates = []
    for role in _list(functional.get("role_candidates")):
        if not isinstance(role, dict):
            continue
        claim_ids = _claim_ids(role)
        role_candidates.append(
            {
                "role": role.get("role"),
                "status": "derived_candidate",
                "space": space_label,
                "source_claim_ids": claim_ids,
                "evidence_reference": _evidence_from_item(role),
                "grounding_status": _statuses_from_item(role),
                "interpretation_basis": _basis_from_claims(claim_ids, claims),
                "uncertainty": deepcopy(role.get("uncertainty") or {}),
            }
        )

    associated_elements = []
    for item in _list(functional.get("associated_elements")):
        if not isinstance(item, dict):
            continue
        claim_ids = _claim_ids(item)
        associated_elements.append(
            {
                "space": space_label,
                "element": item.get("element"),
                "association": item.get("relationship"),
                "status": "bounded_association",
                "source_claim_ids": claim_ids,
                "evidence_reference": _evidence_from_item(item),
                "grounding_status": _statuses_from_item(item),
                "interpretation_basis": _basis_from_claims(claim_ids, claims),
                "uncertainty": deepcopy(item.get("uncertainty") or {}),
            }
        )

    functional_relationships = []
    for item in _list(functional.get("functional_relationships")):
        if not isinstance(item, dict):
            continue
        claim_ids = _claim_ids(item)
        functional_relationships.append(
            {
                "relationship_type": item.get("type"),
                "status": "derived_candidate",
                "space": space_label,
                "source_claim_ids": claim_ids,
                "evidence_reference": _evidence_from_item(item),
                "grounding_status": _statuses_from_item(item),
                "interpretation_basis": _basis_from_claims(claim_ids, claims),
                "uncertainty": deepcopy(item.get("uncertainty") or {}),
            }
        )

    semantic_relationships = []
    for item in functional_relationships:
        semantic_relationships.append(
            {
                "relationship_type": item["relationship_type"],
                "relationship_status": item["status"],
                "source_claim_ids": item["source_claim_ids"],
                "evidence_reference": item["evidence_reference"],
                "grounding_status": item["grounding_status"],
                "uncertainty": deepcopy(item["uncertainty"]),
            }
        )

    for item in _list(v2.get("spatial_relationships")):
        if not isinstance(item, dict):
            continue
        semantic_relationships.append(
            {
                "relationship_type": item.get("relation_type"),
                "relationship_status": item.get("relation_status"),
                "source_claim_ids": _claim_ids(item),
                "evidence_reference": _evidence_from_item(item),
                "grounding_status": _statuses_from_item(item),
                "uncertainty": deepcopy(item.get("uncertainty") or {}),
            }
        )

    patterns = []
    for item in functional_relationships:
        patterns.append(
            {
                "pattern": item["relationship_type"],
                "status": "derived_candidate",
                "space": space_label,
                "source_claim_ids": item["source_claim_ids"],
                "evidence_reference": item["evidence_reference"],
                "grounding_status": item["grounding_status"],
                "interpretation_basis": item["interpretation_basis"],
                "uncertainty": deepcopy(item["uncertainty"]),
            }
        )

    source_claim_ids = _unique(
        claim.get("claim_id")
        for claim in _list(v2.get("claim_trace"))
        if isinstance(claim, dict) and claim.get("claim_id")
    )
    source_evidence = _unique(
        evidence
        for claim in _list(v2.get("claim_trace"))
        if isinstance(claim, dict)
        for evidence in _list(claim.get("source_evidence"))
    )
    grounding_status = _unique(
        status
        for claim in _list(v2.get("claim_trace"))
        if isinstance(claim, dict)
        for status in _list(claim.get("grounding_status"))
    )
    interpretation_basis = _unique(
        basis
        for claim in _list(v2.get("claim_trace"))
        if isinstance(claim, dict)
        for basis in _list(claim.get("interpretation_basis"))
    )

    candidate = {
        "contract": CONTRACT,
        "version": VERSION,
        "status": "candidate",
        "candidate_type": "derived_pattern",
        "source": {
            "contract": SOURCE_CONTRACT,
            "version": SOURCE_VERSION,
            "claim_ids": source_claim_ids,
        },
        "patterns": patterns,
        "space_associations": [
            {
                "space": space_label,
                "status": "bounded_association",
                "source_claim_ids": [semantic_space.get("claim_id")]
                if semantic_space.get("claim_id")
                else [],
                "evidence_reference": source_evidence,
                "grounding_status": grounding_status,
                "interpretation_basis": _list(semantic_space.get("basis")),
                "uncertainty": _uncertainty_from_items(
                    [semantic_space], v2
                ),
            }
        ]
        if space_label
        else [],
        "element_associations": associated_elements,
        "semantic_relationships": semantic_relationships,
        "evidence_chain": {
            "source_contract": SOURCE_CONTRACT,
            "source_version": SOURCE_VERSION,
            "claim_ids": source_claim_ids,
            "source_evidence": source_evidence,
            "grounding_status": grounding_status,
            "interpretation_basis": interpretation_basis,
            "uncertainty": deepcopy(v2.get("uncertainty") or {}),
        },
        "uncertainty": deepcopy(v2.get("uncertainty") or {}),
        "non_claims": list(_NON_CLAIMS),
        "is_knowledge": False,
        "promoted": False,
        "persistent": False,
        "read_only": True,
    }

    _assert_safe(candidate)
    return candidate
