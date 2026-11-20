"""Transient ArchitecturalConceptOntologyV1 organization boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalConceptOntologyV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalConceptRelationshipV1"
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


def _validate_relationships(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalConceptOntologyV1 requires an "
            "ArchitecturalConceptRelationshipV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalConceptOntologyV1 accepts only "
            "ArchitecturalConceptRelationshipV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalConceptOntologyV1 requires relationship version 1.0"
        )
    return value


def _concept_id(label: Any) -> str:
    return str(label or "unresolved_concept")


def _build_node(label: Any, relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "concept_id": _concept_id(label),
        "semantic_label": label,
        "source_relationships": [
            relationship.get("relationship_type")
            for relationship in relationships
        ],
        "source_patterns": _unique(
            pattern
            for relationship in relationships
            for pattern in _list(relationship.get("source_patterns"))
        ),
        "evidence_reference": _unique(
            evidence
            for relationship in relationships
            for evidence in _list(relationship.get("evidence_reference"))
        ),
        "uncertainty": [
            deepcopy(relationship.get("uncertainty"))
            for relationship in relationships
            if relationship.get("uncertainty")
        ],
        "status": "bounded_concept_node",
    }


def build_architectural_concept_ontology_v1(
    concept_relationships: Dict[str, Any],
) -> Dict[str, Any]:
    """Organize concept relationships into a transient ontology representation."""
    source = _validate_relationships(concept_relationships)
    relationships = [
        relationship
        for relationship in _list(source.get("relationships"))
        if isinstance(relationship, dict)
    ]

    labels = _unique(
        concept
        for relationship in relationships
        for concept in _list(relationship.get("related_concepts"))
    )
    concept_nodes = [
        _build_node(
            label,
            [
                relationship
                for relationship in relationships
                if label in _list(relationship.get("related_concepts"))
            ],
        )
        for label in labels
    ]
    relationship_edges = [
        {
            "relationship_type": relationship.get("relationship_type"),
            "source_concepts": _list(relationship.get("related_concepts")),
            "status": "bounded_relationship_edge",
        }
        for relationship in relationships
    ]

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "concept_nodes": concept_nodes,
        "relationship_edges": relationship_edges,
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
                "ArchitecturalConceptOntologyV1 emitted forbidden term: "
                + term
            )
    return result
