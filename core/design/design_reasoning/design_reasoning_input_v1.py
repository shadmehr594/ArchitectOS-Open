"""Transient Design Reasoning Input Boundary V1.

This module prepares semantic context for a future reasoning consumer. It does
not perform design reasoning or generate solutions.

INPUT CHANGED (V1 context integration): it now consumes the ALREADY JOINED
semantic context — ``ArchitecturalDesignReasoningContextV1`` — instead of
consuming ``ArchitecturalIntentResolutionV1`` directly. The join between the
meaning spine and the structure spine happens upstream, in
``architectural_design_reasoning_context_v1``; this boundary only prepares that
joined context for reasoning.

The boundary remains transient, read-only, and purely preparative.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalDesignReasoningInputV1"
VERSION = "1.0"

# The boundary now consumes the joined context only.
SOURCE_CONTRACT = "ArchitecturalDesignReasoningContextV1"
SOURCE_VERSION = "1.0"

# Contracts explicitly rejected in the primary position.
_REJECTED_CONTRACTS = {
    "ArchitecturalIntentResolutionV1",
    "ArchitecturalIntentCandidateV1",
    "ArchitecturalSemanticRetrievalResultV1",
    "ArchitecturalSemanticGraphV1",
    "ArchitecturalKnowledgeCandidateV1",
    "ArchitecturalDesignReasoningResultV1",
    "ArchitecturalSpatialReasoningCandidateV1",
    "ArchitecturalKnowledgeAcquisitionBoundaryV1",
    "SiteIntentV1",
    "ImageIntentV1",
}

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
    "adjacent",
    "layout",
    "placement",
    "spatial decision",
    "geometry",
    "dimension",
    "cad",
    "bim",
    "ifc",
    "memory",
    "design solution",
    "design_solution",
    "design rule",
    "design_rule",
)


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


def _validate_context(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalDesignReasoningInputV1 requires an "
            "ArchitecturalDesignReasoningContextV1 dict"
        )
    contract = value.get("contract")
    if contract != SOURCE_CONTRACT:
        if contract in _REJECTED_CONTRACTS:
            raise ValueError(
                "ArchitecturalDesignReasoningInputV1 accepts only "
                "ArchitecturalDesignReasoningContextV1; rejected input "
                "contract: " + str(contract)
            )
        raise ValueError(
            "ArchitecturalDesignReasoningInputV1 accepts only "
            "ArchitecturalDesignReasoningContextV1 (got: "
            + str(contract) + ")"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalDesignReasoningInputV1 requires context version "
            + SOURCE_VERSION
        )
    return value


def _assert_safe(value: Any, label: str) -> None:
    """Scan a payload this boundary authored. ``non_claims`` is excluded by the
    caller because its keys literally contain the forbidden terms."""
    text = str(value).lower()
    for term in _FORBIDDEN_TERMS:
        if term in text:
            raise AssertionError(
                "ArchitecturalDesignReasoningInputV1 emitted forbidden term in "
                + label + ": " + term
            )


# --------------------------------------------------------------------------- #
# context projection
# --------------------------------------------------------------------------- #
def _intent_context(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Preserve the intent context shape the reasoning consumer reads."""
    projects = []
    for group in _list(context.get("intent_groups")):
        if not isinstance(group, dict):
            continue
        projects.append(
            {
                "intent_group": group.get("intent_group"),
                "source_intents": _list(group.get("source_intents")),
                "status": group.get("status"),
            }
        )
    return projects


def _semantic_graph_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Carry the joined graph context forward, unmodified in substance."""
    return {
        "canonical_key": context.get("canonical_key"),
        "canonical_patterns": _list(context.get("canonical_patterns")),
        "context_links": deepcopy(_list(context.get("context_links"))),
        "nodes": deepcopy(_list(context.get("semantic_graph_nodes"))),
        "edges": deepcopy(_list(context.get("semantic_graph_edges"))),
    }


def _source_evidence(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Rebuild the per-group evidence view the reasoning consumer reads."""
    evidence = []
    for group in _list(context.get("intent_groups")):
        if not isinstance(group, dict):
            continue
        evidence.append(
            {
                "intent_group": group.get("intent_group"),
                "source_intents": _list(group.get("source_intents")),
                "source_patterns": _list(group.get("source_patterns")),
                "evidence_reference": _list(group.get("evidence_reference")),
            }
        )
    return evidence


def _semantic_context(
    context: Dict[str, Any],
    intent_context: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Per-group semantic component view, paired with its canonical patterns."""
    patterns_by_group: Dict[Any, List[str]] = {}
    for group in _list(context.get("intent_groups")):
        if isinstance(group, dict):
            patterns_by_group[group.get("intent_group")] = _list(
                group.get("source_patterns")
            )
    return [
        {
            "component": item.get("intent_group"),
            "source_patterns": patterns_by_group.get(item.get("intent_group"), []),
            "status": item.get("status"),
        }
        for item in intent_context
    ]


def build_design_reasoning_input_v1(
    design_reasoning_context: Any,
) -> Dict[str, Any]:
    """Prepare reasoning context from ArchitecturalDesignReasoningContextV1 only."""
    context = _validate_context(design_reasoning_context)

    intent_context = _intent_context(context)
    semantic_context = _semantic_context(context, intent_context)
    semantic_graph_context = _semantic_graph_context(context)
    source_evidence = _source_evidence(context)

    source_patterns = _unique(
        pattern
        for group in _list(context.get("intent_groups"))
        if isinstance(group, dict)
        for pattern in _strings(group.get("source_patterns"))
    )

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "intent_context": intent_context,
        "semantic_context": semantic_context,
        "semantic_graph_context": semantic_graph_context,
        "source_patterns": source_patterns,
        "source_evidence": source_evidence,
        "uncertainty": deepcopy(context.get("uncertainty") or {}),
        "open_questions": [],
        "non_claims": deepcopy(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }

    _assert_safe(
        {
            key: value
            for key, value in result.items()
            if key not in ("non_claims", "semantic_graph_context", "source_evidence")
        },
        "input payload",
    )
    return result
