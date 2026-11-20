"""Transient ArchitecturalDesignReasoningContextV1 join boundary.

This module JOINS two upstream semantic contracts into a single read-only
context object:

    ArchitecturalIntentResolutionV1  (meaning spine)
    ArchitecturalSemanticGraphV1     (structure spine)
                |
                v
    ArchitecturalDesignReasoningContextV1

It is the rejoin point declared by
ARCHITECTURAL_SEMANTIC_PIPELINE_DIRECTION_DECISION_V1: the two spines are
siblings off ArchitecturalTeachingSessionV1 and rejoin before design reasoning.

The join key is ``source_patterns`` — the ONLY canonical shared semantic
identifier. Concept labels, intent group names and node ids are CONTEXTUAL
representations and are never used to establish identity.

This boundary only joins semantic context. It does NOT interpret, reason,
decide, recommend, or generate anything.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalDesignReasoningContextV1"
VERSION = "1.0"

# The only two accepted inputs.
RESOLUTION_CONTRACT = "ArchitecturalIntentResolutionV1"
RESOLUTION_VERSION = "1.0"
GRAPH_CONTRACT = "ArchitecturalSemanticGraphV1"
GRAPH_VERSION = "1.0"

# The canonical shared semantic key.
CANONICAL_KEY = "source_patterns"

_NON_CLAIMS = {
    "not_design_reasoning": True,
    "not_design_solution": True,
    "not_recommendation": True,
    "not_design_rule": True,
    "not_layout": True,
    "not_spatial_decision": True,
    "not_geometry": True,
    "not_memory": True,
    "not_authoritative_knowledge": True,
}

_FORBIDDEN_TERMS = (
    "should",
    "must",
    "required",
    "optimal",
    "best",
    "recommended",
    "design solution",
    "design_solution",
    "design rule",
    "design_rule",
    "layout",
    "placement",
    "spatial decision",
    "geometry",
    "dimension",
    "cad",
    "bim",
    "ifc",
    "memory",
)

# Contracts that must never be accepted in place of the two declared inputs.
_REJECTED_CONTRACTS = {
    "ArchitecturalSemanticRetrievalResultV1",
    "ArchitecturalIntentCandidateV1",
    "ArchitecturalDesignReasoningInputV1",
    "ArchitecturalDesignReasoningResultV1",
    "ArchitecturalSpatialReasoningCandidateV1",
    "ArchitecturalKnowledgeAcquisitionBoundaryV1",
    "ArchitecturalConceptOntologyV1",
    "ArchitecturalConceptRelationshipV1",
    "ArchitecturalConceptUnderstandingV1",
    "ArchitecturalFoundationKnowledgeAccessV1",
    "ArchitecturalFoundationKnowledgeSetV1",
    "ArchitecturalKnowledgeCurriculumV1",
    "ArchitecturalTeachingSessionV1",
    "ArchitecturalTeachingRecordV1",
    "SiteIntentV1",
    "ImageIntentV1",
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return deepcopy(value)
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    return [deepcopy(value)]


def _strings(value: Any) -> List[str]:
    return [
        item.strip()
        for item in _list(value)
        if isinstance(item, str) and item.strip()
    ]


def _unique(values: Iterable[Any]) -> List[Any]:
    result: List[Any] = []
    for value in values:
        if value not in result:
            result.append(deepcopy(value))
    return result


def _assert_safe(value: Any, label: str) -> None:
    """Scan a structural payload the boundary itself authored.

    ``non_claims`` is excluded by the caller because its keys literally contain
    the forbidden terms (``not_design_rule``, ``not_recommendation``).
    """
    text = str(value).lower()
    for term in _FORBIDDEN_TERMS:
        if term in text:
            raise AssertionError(
                "ArchitecturalDesignReasoningContextV1 emitted forbidden term "
                "in " + label + ": " + term
            )


# --------------------------------------------------------------------------- #
# input validation
# --------------------------------------------------------------------------- #
def _validate_resolution(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalDesignReasoningContextV1 requires an "
            "ArchitecturalIntentResolutionV1 dict as its first argument"
        )
    contract = value.get("contract")
    if contract != RESOLUTION_CONTRACT:
        if contract in _REJECTED_CONTRACTS:
            raise ValueError(
                "ArchitecturalDesignReasoningContextV1 accepts only "
                "ArchitecturalIntentResolutionV1 and ArchitecturalSemanticGraphV1; "
                "rejected first-argument contract: " + str(contract)
            )
        raise ValueError(
            "ArchitecturalDesignReasoningContextV1 accepts only "
            "ArchitecturalIntentResolutionV1 (got: " + str(contract) + ")"
        )
    if value.get("version") != RESOLUTION_VERSION:
        raise ValueError(
            "ArchitecturalDesignReasoningContextV1 requires intent resolution "
            "version " + RESOLUTION_VERSION
        )
    return value


def _validate_graph(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalDesignReasoningContextV1 requires an "
            "ArchitecturalSemanticGraphV1 dict as its second argument"
        )
    contract = value.get("contract")
    if contract != GRAPH_CONTRACT:
        if contract in _REJECTED_CONTRACTS:
            raise ValueError(
                "ArchitecturalDesignReasoningContextV1 accepts only "
                "ArchitecturalIntentResolutionV1 and ArchitecturalSemanticGraphV1; "
                "rejected second-argument contract: " + str(contract)
            )
        raise ValueError(
            "ArchitecturalDesignReasoningContextV1 accepts only "
            "ArchitecturalSemanticGraphV1 (got: " + str(contract) + ")"
        )
    if value.get("version") != GRAPH_VERSION:
        raise ValueError(
            "ArchitecturalDesignReasoningContextV1 requires semantic graph "
            "version " + GRAPH_VERSION
        )
    return value


# --------------------------------------------------------------------------- #
# source extraction
# --------------------------------------------------------------------------- #
def _intent_group(group: Dict[str, Any]) -> Dict[str, Any]:
    """Preserve an intent group's declared fields exactly."""
    return {
        "intent_group": group.get("intent_group"),
        "source_intents": _list(group.get("source_intents")),
        "status": group.get("status"),
        "source_patterns": _list(group.get("source_patterns")),
        "evidence_reference": _list(group.get("evidence_reference")),
        "uncertainty": deepcopy(group.get("uncertainty") or []),
    }


def _graph_node(node: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "node_id": node.get("node_id"),
        "concept_type": node.get("concept_type"),
        "semantic_label": node.get("semantic_label"),
        "source_patterns": _list(node.get("source_patterns")),
        "evidence_reference": _list(node.get("evidence_reference")),
        "uncertainty": deepcopy(node.get("uncertainty")),
        "status": node.get("status"),
    }


def _graph_edge(edge: Dict[str, Any]) -> Dict[str, Any]:
    """Edges carry no uncertainty and no evidence — never invent either."""
    return {
        "edge_type": edge.get("edge_type"),
        "source_node": edge.get("source_node"),
        "target_node": edge.get("target_node"),
        "status": edge.get("status"),
    }


def _pattern_index(nodes: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Map each canonical source_pattern to the node ids that declare it."""
    index: Dict[str, List[str]] = {}
    for node in nodes:
        for pattern in _strings(node.get("source_patterns")):
            index.setdefault(pattern, [])
            if node.get("node_id") not in index[pattern]:
                index[pattern].append(node.get("node_id"))
    return index


def _context_link(
    group: Dict[str, Any],
    pattern_index: Dict[str, List[str]],
) -> Dict[str, Any]:
    """Associate one intent group with graph nodes via source_patterns only."""
    group_patterns = _strings(group.get("source_patterns"))
    linked_node_ids: List[str] = []
    unlinked_patterns: List[str] = []
    for pattern in group_patterns:
        node_ids = pattern_index.get(pattern)
        if node_ids:
            for node_id in node_ids:
                if node_id not in linked_node_ids:
                    linked_node_ids.append(node_id)
        else:
            unlinked_patterns.append(pattern)
    return {
        "intent_group": group.get("intent_group"),
        "canonical_key": CANONICAL_KEY,
        "group_source_patterns": group_patterns,
        "linked_node_ids": linked_node_ids,
        "unlinked_patterns": unlinked_patterns,
        "status": (
            "bounded_context_link" if linked_node_ids else "unlinked_context"
        ),
    }


# --------------------------------------------------------------------------- #
# public function
# --------------------------------------------------------------------------- #
def build_architectural_design_reasoning_context_v1(
    intent_resolution: Any,
    semantic_graph: Any,
) -> Dict[str, Any]:
    """Join intent resolution with semantic graph context. Read-only, transient."""
    resolution = _validate_resolution(intent_resolution)
    graph = _validate_graph(semantic_graph)

    groups = [
        _intent_group(group)
        for group in _list(resolution.get("intent_groups"))
        if isinstance(group, dict)
    ]
    nodes = [
        _graph_node(node)
        for node in _list(graph.get("nodes"))
        if isinstance(node, dict)
    ]
    edges = [
        _graph_edge(edge)
        for edge in _list(graph.get("edges"))
        if isinstance(edge, dict)
    ]
    pattern_index = _pattern_index(nodes)
    context_links = [_context_link(group, pattern_index) for group in groups]

    canonical_patterns = _unique(
        pattern
        for group in groups
        for pattern in _strings(group.get("source_patterns"))
    )
    unlinked_patterns = _unique(
        pattern
        for link in context_links
        for pattern in _list(link.get("unlinked_patterns"))
    )

    evidence_basis = [
        {
            "evidence_type": "intent_resolution",
            "reference": {
                "contract": resolution.get("contract"),
                "version": resolution.get("version"),
            },
            "basis": deepcopy(resolution.get("evidence_basis") or []),
        },
        {
            "evidence_type": "semantic_graph",
            "reference": {
                "contract": graph.get("contract"),
                "version": graph.get("version"),
            },
            "basis": deepcopy(graph.get("evidence_basis") or []),
        },
    ]

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "intent_groups": groups,
        "source_intents": _list(resolution.get("source_intents")),
        "semantic_components": _list(resolution.get("semantic_components")),
        "canonical_key": CANONICAL_KEY,
        "canonical_patterns": canonical_patterns,
        "context_links": context_links,
        "semantic_graph_nodes": nodes,
        "semantic_graph_edges": edges,
        "evidence_basis": evidence_basis,
        "uncertainty": {
            "intent_resolution": deepcopy(resolution.get("uncertainty") or {}),
            "semantic_graph": deepcopy(graph.get("uncertainty") or {}),
            "unlinked_patterns": unlinked_patterns,
            "unlinked_pattern_count": len(unlinked_patterns),
            "interpreted": False,
            "reasoned": False,
        },
        "non_claims": deepcopy(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }

    # Forbidden-language check over everything the boundary authored.
    _assert_safe(
        {
            key: value
            for key, value in result.items()
            if key not in ("non_claims", "intent_groups", "semantic_graph_nodes")
        },
        "context payload",
    )
    # Intent groups and graph nodes are pass-through upstream structures; scan
    # only their boundary-authored critical_key fields, never their raw source.
    for link in context_links:
        _assert_safe(link, "context link")

    return result
