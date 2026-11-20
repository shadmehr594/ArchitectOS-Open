"""Controlled architectural knowledge acquisition boundary V1.

This layer is a BOUNDARY, not a learner. It accepts an
ArchitecturalSemanticGraphV1 (already-built semantic understanding) plus a
human-provided architectural example, and returns a transient candidate that
attaches the example to the existing semantic structure.

It does NOT:
  * create Memory,
  * store anything permanently,
  * learn automatically,
  * modify the Semantic Graph,
  * promote knowledge,
  * create an authoritative ontology / design rules / recommendations /
    standards / layout decisions / geometry / CAD / BIM / IFC data.

It is read-only and produces a transient candidate only.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional, Tuple


CONTRACT = "ArchitecturalKnowledgeAcquisitionBoundaryV1"
VERSION = "1.0"

# The only accepted input structure. Anything else is rejected.
SOURCE_CONTRACT = "ArchitecturalSemanticGraphV1"
SOURCE_VERSION = "1.0"

# Allowed acquisition status values (closed vocabulary).
ACQUISITION_STATUSES = (
    "candidate_received",
    "bounded_association",
    "requires_validation",
)

_NON_CLAIMS = {
    "not_memory": True,
    "not_learned_model": True,
    "not_authoritative_knowledge": True,
    "not_design_rule": True,
    "not_recommendation": True,
    "not_design_solution": True,
}

# Required fields of the human-provided example.
EXAMPLE_REQUIRED_FIELDS = (
    "example_id",
    "domain",
    "description",
    "human_explanation",
    "related_concepts",
    "related_patterns",
)

# Contracts that are explicitly NOT accepted as the primary input.
_REJECTED_CONTRACTS = {
    "ArchitecturalUnderstandingV2",
    "ArchitecturalUnderstandingV1",
    "ArchitecturalKnowledgeCandidateV1",
    "ArchitecturalTeachingRecordV1",
    "ArchitecturalTeachingSessionV1",
    "ArchitecturalDesignReasoningResultV1",
    "ArchitecturalVisionInterpreterV1",
    "VisionObservationV1",
    "ArchitecturalObservationV1",
    "ObservationV1",
    "GeometryV1",
    "CADModelV1",
    "BIMModelV1",
    "IFCProjectV1",
}

# Non-graph raw payloads / providers / geometry that must never be accepted.
_REJECTED_TYPE_NAMES = {
    "str",
    "bytes",
    "bytearray",
    "int",
    "float",
    "bool",
}

# Forbidden language. The check runs over the STRUCTURAL candidate payload
# (never over the raw human narrative and never over the boundary's own
# non-claim flags). Matching is word-bounded so that ordinary words such as
# "mustard" or "bestow" do not trip it.
_FORBIDDEN_TERMS = (
    "should",
    "must",
    "required",
    "optimal",
    "best",
    "recommended",
    "design rule",
    "design solution",
    "layout rule",
    "placement",
    "geometry",
)

_NORMATIVE_STEMS = (
    "should",
    "must",
    "requir",
    "optimal",
    "best",
    "recommend",
)


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _list(value: Any) -> List[Any]:
    """Coerce an optional scalar/list/tuple/None into a copied list."""
    if isinstance(value, list):
        return deepcopy(value)
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    return [deepcopy(value)]


def _text_list(value: Any) -> List[str]:
    """Coerce into a list of strings, dropping empties, preserving order."""
    result: List[str] = []
    for item in _list(value):
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return result


def _unique(values: Iterable[Any]) -> List[Any]:
    result: List[Any] = []
    for value in values:
        if value not in result:
            result.append(deepcopy(value))
    return result


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _tokenize(text: str) -> List[str]:
    """Word tokens, treating any non-alphanumeric run as a separator.

    A hyphenated term therefore decomposes into its words, which is what makes
    the forbidden-language scan operate on whole words.
    """
    tokens: List[str] = []
    current: List[str] = []
    for char in text.lower():
        if char.isalnum():
            current.append(char)
        else:
            if current:
                tokens.append("".join(current))
                current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _matched_terms(text: str) -> List[str]:
    """Return the forbidden terms present in *text*.

    Multi-word terms are matched as consecutive token runs; single-word terms
    are matched exactly. This is deliberately stronger than ``in`` so that
    "mustard"/"bestow"/"unbestowed" cannot produce a false positive.
    """
    if not isinstance(text, str) or not text:
        return []
    tokens = _tokenize(text)
    token_set = set(tokens)
    hits: List[str] = []
    for term in _FORBIDDEN_TERMS:
        parts = _tokenize(term)
        if not parts:
            continue
        if len(parts) == 1:
            if parts[0] in token_set:
                hits.append(term)
            continue
        for index in range(len(tokens) - len(parts) + 1):
            if tokens[index : index + len(parts)] == parts:
                hits.append(term)
                break
    return _unique(hits)


def _has_normative_stem(text: str) -> bool:
    """Word-START matching over the normative stems (Persian suffixes aside,
    this catches English inflections such as recommended/recommendation)."""
    if not isinstance(text, str):
        return False
    lowered = text.lower()
    for token in _tokenize(lowered):
        for stem in _NORMATIVE_STEMS:
            if token.startswith(stem):
                return True
    return False


def _is_free_text(value: Any) -> bool:
    """White-space-delimited prose of reasonable length.

    Human explanations are narratives. A short identifier produced by a script
    is not, and must be treated as a machine value.
    """
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped:
        return False
    if len(stripped) < 16:
        return False
    return any(char.isspace() for char in stripped)


def _assert_safe(text: Any, label: str) -> None:
    hits = _matched_terms(str(text))
    if hits:
        raise AssertionError(
            "ArchitecturalKnowledgeAcquisitionBoundaryV1 emitted forbidden "
            "term(s) in " + label + ": " + ", ".join(hits)
        )


# --------------------------------------------------------------------------- #
# input validation
# --------------------------------------------------------------------------- #
def _validate_graph(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalKnowledgeAcquisitionBoundaryV1 requires an "
            "ArchitecturalSemanticGraphV1 dict. Raw image input, provider "
            "payloads, Vision/Observation output, ArchitecturalUnderstandingV2, "
            "KnowledgeCandidate, TeachingRecord, TeachingSession, "
            "DesignReasoningResult, Geometry, CAD, BIM and IFC are not accepted."
        )
    contract = value.get("contract")
    if contract != SOURCE_CONTRACT:
        if contract in _REJECTED_CONTRACTS:
            raise ValueError(
                "ArchitecturalKnowledgeAcquisitionBoundaryV1 accepts only "
                "ArchitecturalSemanticGraphV1; rejected input contract: "
                + str(contract)
            )
        raise ValueError(
            "ArchitecturalKnowledgeAcquisitionBoundaryV1 accepts only "
            "ArchitecturalSemanticGraphV1 (got: " + str(contract) + ")"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalKnowledgeAcquisitionBoundaryV1 requires semantic "
            "graph version " + SOURCE_VERSION
        )
    return value


def _validate_example(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "architectural_example must be a human-provided example dict"
        )
    missing = [field for field in EXAMPLE_REQUIRED_FIELDS if _is_blank(value.get(field))]
    if missing:
        raise ValueError(
            "architectural_example is missing required field(s): "
            + ", ".join(missing)
        )
    return value


# --------------------------------------------------------------------------- #
# candidate construction
# --------------------------------------------------------------------------- #
def _source_graph_reference(graph: Dict[str, Any]) -> Dict[str, Any]:
    """A reference to the graph — never a copy that could diverge from it."""
    nodes = [node for node in _list(graph.get("nodes")) if isinstance(node, dict)]
    edges = [edge for edge in _list(graph.get("edges")) if isinstance(edge, dict)]
    return {
        "contract": graph.get("contract"),
        "version": graph.get("version"),
        "reference_only": True,
        "node_references": [node.get("node_id") for node in nodes],
        "edge_references": [
            {
                "edge_type": edge.get("edge_type"),
                "source_node": edge.get("source_node"),
                "target_node": edge.get("target_node"),
            }
            for edge in edges
        ],
        "read_only": True,
    }


def _link_concepts(
    graph: Dict[str, Any],
    example: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Associate the example's concepts with graph nodes.

    Association is literal (id or semantic label). No interpretation, no
    inference, no ranking.
    """
    requested = _text_list(example.get("related_concepts"))
    nodes = [node for node in _list(graph.get("nodes")) if isinstance(node, dict)]
    index: Dict[str, Dict[str, Any]] = {}
    for node in nodes:
        for key in (node.get("node_id"), node.get("semantic_label")):
            if isinstance(key, str) and key.strip():
                index.setdefault(key.strip(), node)

    links: List[Dict[str, Any]] = []
    unresolved: List[str] = []
    for concept in requested:
        node = index.get(concept)
        if node is None:
            unresolved.append(concept)
            continue
        links.append(
            {
                "concept_id": node.get("node_id"),
                "semantic_label": node.get("semantic_label"),
                "matched_example_reference": deepcopy(concept),
                "source_patterns": _list(node.get("source_patterns")),
                "evidence_reference": _list(node.get("evidence_reference")),
                "uncertainty": deepcopy(node.get("uncertainty") or {}),
                "status": "bounded_concept_link",
            }
        )
    return links, unresolved


def _link_patterns(
    graph: Dict[str, Any],
    example: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Associate the example's patterns with the graph's pattern vocabulary."""
    requested = _text_list(example.get("related_patterns"))
    nodes = [node for node in _list(graph.get("nodes")) if isinstance(node, dict)]
    index: Dict[str, Dict[str, Any]] = {}
    for node in nodes:
        for pattern in _list(node.get("source_patterns")):
            if isinstance(pattern, str) and pattern.strip():
                index.setdefault(pattern.strip(), node)

    links: List[Dict[str, Any]] = []
    unresolved: List[str] = []
    for pattern in requested:
        node = index.get(pattern)
        if node is None:
            unresolved.append(pattern)
            continue
        links.append(
            {
                "pattern_id": pattern,
                "concept_id": node.get("node_id"),
                "semantic_label": node.get("semantic_label"),
                "evidence_reference": _list(node.get("evidence_reference")),
                "uncertainty": deepcopy(node.get("uncertainty") or {}),
                "status": "bounded_pattern_link",
            }
        )
    return links, unresolved


def _evidence_basis(
    graph: Dict[str, Any],
    example: Dict[str, Any],
    linked_concepts: List[Dict[str, Any]],
    linked_patterns: List[Dict[str, Any]],
    unresolved_concepts: List[str],
    unresolved_patterns: List[str],
) -> List[Dict[str, Any]]:
    basis: List[Dict[str, Any]] = [
        {
            "evidence_type": "source_semantic_graph",
            "reference": {
                "contract": graph.get("contract"),
                "version": graph.get("version"),
            },
            "basis": deepcopy(graph.get("evidence_basis") or []),
        },
        {
            "evidence_type": "human_provided_example",
            "reference": {
                "example_id": example.get("example_id"),
                "domain": example.get("domain"),
            },
            "basis": deepcopy(example.get("description")),
        },
    ]
    if linked_concepts:
        basis.append(
            {
                "evidence_type": "linked_concepts",
                "reference": [link.get("concept_id") for link in linked_concepts],
                "basis": "graph node association (literal)",
            }
        )
    if linked_patterns:
        basis.append(
            {
                "evidence_type": "linked_patterns",
                "reference": [link.get("pattern_id") for link in linked_patterns],
                "basis": "graph pattern association (literal)",
            }
        )
    if unresolved_concepts or unresolved_patterns:
        basis.append(
            {
                "evidence_type": "unresolved_example_references",
                "reference": {
                    "concepts": deepcopy(unresolved_concepts),
                    "patterns": deepcopy(unresolved_patterns),
                },
                "basis": "no matching graph node or pattern (no inference made)",
            }
        )
    return basis


def _uncertainty(
    graph: Dict[str, Any],
    example: Dict[str, Any],
    linked_concepts: List[Dict[str, Any]],
    linked_patterns: List[Dict[str, Any]],
    unresolved_concepts: List[str],
    unresolved_patterns: List[str],
    status: str,
) -> Dict[str, Any]:
    node_uncertainty = [
        {
            "node_id": link.get("concept_id"),
            "uncertainty": deepcopy(link.get("uncertainty") or {}),
        }
        for link in linked_concepts
        if link.get("uncertainty")
    ]
    return {
        "acquisition_status": status,
        "graph_uncertainty": deepcopy(graph.get("uncertainty") or {}),
        "node_uncertainty": node_uncertainty,
        "unresolved_example_references": {
            "concepts": deepcopy(unresolved_concepts),
            "patterns": deepcopy(unresolved_patterns),
        },
        "unresolved_count": len(unresolved_concepts) + len(unresolved_patterns),
        "explanation_interpreted": False,
        "example_interpretation_generated": False,
        "validated": False,
        "unknowns": [
            "human_provided_example is not independently validated",
            "explanation is preserved verbatim and not interpreted",
        ],
    }


def _acquisition_status(
    linked_concepts: List[Dict[str, Any]],
    linked_patterns: List[Dict[str, Any]],
    unresolved: List[str],
) -> str:
    if unresolved:
        return "requires_validation"
    if linked_concepts or linked_patterns:
        return "bounded_association"
    return "candidate_received"


def _structural_payload(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Everything the boundary itself authored.

    Excludes the pass-through human narrative fields (``architectural_example``
    and the evidence basis) and the ``non_claims`` flags: those are not
    statements the boundary is making, and ``not_design_rule`` would otherwise
    trip the very scan that enforces the rule.
    """
    return {
        key: deepcopy(value)
        for key, value in candidate.items()
        if key
        not in (
            "non_claims",
            "architectural_example",
            "evidence_basis",
            "source_graph_reference",
        )
    }


# --------------------------------------------------------------------------- #
# public function
# --------------------------------------------------------------------------- #
def build_architectural_knowledge_acquisition_candidate_v1(
    semantic_graph: Any,
    architectural_example: Any,
) -> Dict[str, Any]:
    """Attach a human-provided example to an existing semantic graph.

    Read-only. Returns a transient candidate. Creates no Memory, stores
    nothing permanently, learns nothing.
    """
    print("=" * 78)
    print("ARCHITECTURAL KNOWLEDGE ACQUISITION BOUNDARY V1")
    print("contract: " + CONTRACT + " version: " + VERSION)
    print("=" * 78)

    graph = _validate_graph(semantic_graph)
    example = _validate_example(architectural_example)

    linked_concepts, unresolved_concepts = _link_concepts(graph, example)
    linked_patterns, unresolved_patterns = _link_patterns(graph, example)
    unresolved = unresolved_concepts + unresolved_patterns

    status = _acquisition_status(linked_concepts, linked_patterns, unresolved)
    if status not in ACQUISITION_STATUSES:
        raise AssertionError("unreachable acquisition status: " + str(status))

    candidate: Dict[str, Any] = {
        "contract": CONTRACT,
        "version": VERSION,
        "source_graph_reference": _source_graph_reference(graph),
        "architectural_example": deepcopy(example),
        "linked_concepts": linked_concepts,
        "linked_patterns": linked_patterns,
        "evidence_basis": _evidence_basis(
            graph,
            example,
            linked_concepts,
            linked_patterns,
            unresolved_concepts,
            unresolved_patterns,
        ),
        "uncertainty": _uncertainty(
            graph,
            example,
            linked_concepts,
            linked_patterns,
            unresolved_concepts,
            unresolved_patterns,
            status,
        ),
        "acquisition_status": status,
        "non_claims": deepcopy(_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }

    # FORBIDDEN LANGUAGE CHECK — over the boundary's own statements only.
    _forbidden_language_check(candidate)

    if _is_free_text(example.get("human_explanation")):
        if _has_normative_stem(str(example.get("human_explanation"))):
            print(
                "[acquisition] NOTE: the human explanation carries normative "
                "phrasing. It is preserved verbatim, flagged, never interpreted."
            )

    print(
        "[acquisition] status=" + status
        + " linked_concepts=" + str(len(linked_concepts))
        + " linked_patterns=" + str(len(linked_patterns))
        + " unresolved=" + str(len(unresolved))
        + " persistent=False read_only=True"
    )
    return candidate


def _forbidden_language_check(candidate: Dict[str, Any]) -> None:
    payload = _structural_payload(candidate)
    _assert_safe(payload, "structural candidate payload")
    # The human narrative is preserved verbatim; the boundary flags it and
    # never lets it enter the structural payload.
    example = candidate.get("architectural_example") or {}
    if not isinstance(example, dict):
        return
    for field in ("description", "human_explanation"):
        value = example.get(field)
        if _is_free_text(value):
            continue
        _assert_safe(value, "architectural_example." + field)
