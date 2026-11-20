"""Transient ArchitecturalConceptRelationshipV1 boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalConceptRelationshipV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalConceptUnderstandingV1"
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


def _validate_understanding(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalConceptRelationshipV1 requires an "
            "ArchitecturalConceptUnderstandingV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalConceptRelationshipV1 accepts only "
            "ArchitecturalConceptUnderstandingV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalConceptRelationshipV1 requires understanding version 1.0"
        )
    return value


def _relationship_for_labels(labels: List[str]) -> tuple[str, str] | None:
    label_set = set(labels)
    if {
        "sleeping_space_with_storage_association",
        "sleeping_space_with_sanitary_association",
    }.issubset(label_set):
        return (
            "private_sleeping_concept_context",
            "bounded_concept_relationship",
        )
    if "circulation_related_semantic_context" in label_set:
        return (
            "movement_related_concept_context",
            "bounded_concept_relationship",
        )
    if "opening_related_semantic_context" in label_set:
        return (
            "boundary_connection_concept_context",
            "bounded_concept_relationship",
        )
    return None


def _build_relationship(
    relationship_type: str,
    concepts: List[Dict[str, Any]],
    status: str,
) -> Dict[str, Any]:
    return {
        "relationship_type": relationship_type,
        "related_concepts": [
            deepcopy(concept.get("semantic_label"))
            for concept in concepts
        ],
        "source_patterns": _unique(
            pattern
            for concept in concepts
            for pattern in _list(concept.get("source_patterns"))
        ),
        "evidence_reference": _unique(
            evidence
            for concept in concepts
            for evidence in _list(concept.get("evidence_reference"))
        ),
        "uncertainty": [
            deepcopy(concept.get("uncertainty"))
            for concept in concepts
            if concept.get("uncertainty")
        ],
        "status": status,
    }


def build_architectural_concept_relationship_v1(
    concept_understanding: Dict[str, Any],
) -> Dict[str, Any]:
    """Build bounded relationships from concept understanding only."""
    source = _validate_understanding(concept_understanding)
    concepts = [
        concept
        for concept in _list(source.get("concepts"))
        if isinstance(concept, dict)
    ]
    labels = [
        concept.get("semantic_label")
        for concept in concepts
        if isinstance(concept.get("semantic_label"), str)
    ]
    relationship_spec = _relationship_for_labels(labels)
    relationships = []
    if relationship_spec:
        relationship_type, status = relationship_spec
        if relationship_type == "private_sleeping_concept_context":
            selected = [
                concept
                for concept in concepts
                if concept.get("semantic_label") in {
                    "sleeping_space_with_storage_association",
                    "sleeping_space_with_sanitary_association",
                }
            ]
        elif relationship_type == "movement_related_concept_context":
            selected = [
                concept
                for concept in concepts
                if concept.get("semantic_label")
                == "circulation_related_semantic_context"
            ]
        else:
            selected = [
                concept
                for concept in concepts
                if concept.get("semantic_label")
                == "opening_related_semantic_context"
            ]
        relationships.append(_build_relationship(relationship_type, selected, status))

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "relationships": relationships,
        "source_concepts": deepcopy(concepts),
        "evidence_basis": deepcopy(source.get("evidence_basis") or []),
        "uncertainty": deepcopy(source.get("uncertainty") or {}),
        "non_claims": deepcopy(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }
    payload = {key: value for key, value in result.items() if key != "non_claims"}
    serialized = str(payload).lower()
    for term in _FORBIDDEN_TERMS:
        if term in serialized:
            raise AssertionError(
                "ArchitecturalConceptRelationshipV1 emitted forbidden term: "
                + term
            )
    return result
