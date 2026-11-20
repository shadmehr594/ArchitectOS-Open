"""Transient ArchitecturalSemanticGraphV1 boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalSemanticGraphV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalConceptOntologyV1"
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


def _validate_ontology(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalSemanticGraphV1 requires an "
            "ArchitecturalConceptOntologyV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalSemanticGraphV1 accepts only "
            "ArchitecturalConceptOntologyV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalSemanticGraphV1 requires ontology version 1.0"
        )
    return value


def _node(node: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "node_id": node.get("concept_id") or node.get("semantic_label") or "",
        "concept_type": "architectural_concept",
        "semantic_label": node.get("semantic_label"),
        "source_patterns": _list(node.get("source_patterns")),
        "evidence_reference": _list(node.get("evidence_reference")),
        "uncertainty": deepcopy(node.get("uncertainty") or {}),
        "status": "bounded_semantic_node",
    }


def _edge(edge: Dict[str, Any]) -> Dict[str, Any]:
    concepts = _list(edge.get("source_concepts"))
    return {
        "edge_type": edge.get("relationship_type"),
        "source_node": concepts[0] if concepts else "",
        "target_node": concepts[1] if len(concepts) > 1 else "",
        "status": "bounded_semantic_edge",
    }


def build_architectural_semantic_graph_v1(
    ontology: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a transient graph from ArchitecturalConceptOntologyV1 only."""
    source = _validate_ontology(ontology)
    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "nodes": [
            _node(node)
            for node in _list(source.get("concept_nodes"))
            if isinstance(node, dict)
        ],
        "edges": [
            _edge(edge)
            for edge in _list(source.get("relationship_edges"))
            if isinstance(edge, dict)
        ],
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
                "ArchitecturalSemanticGraphV1 emitted forbidden term: " + term
            )
    return result
