"""Production producer boundary for ArchitecturalConceptRelationshipV1.

This module is the DEDICATED PRODUCER for `ArchitecturalConceptRelationshipV1`.
It connects:

    ArchitecturalConceptUnderstandingV1
                  ↓
    ArchitecturalConceptRelationshipV1

It is a transient, read-only, deterministic boundary. It performs **bounded
semantic grouping only** — no more.

────────────────────────────────────────────────────────────────────────────
WHY THIS MODULE EXISTS (the seam it closes)
────────────────────────────────────────────────────────────────────────────

`build_architectural_concept_relationship_v1` is a strict contract gate: it
accepts *only* an `ArchitecturalConceptUnderstandingV1` dict, and it derives
relationships from a **closed label table** matched against the understanding's
concept labels.

That boundary is now reachable — the previous phase gave
`ArchitecturalConceptUnderstandingV1` a real producer. But the understanding
envelope alone is not sufficient to express everything the brief requires to
survive: the downstream boundary reads `semantic_label`, `source_patterns`,
`evidence_reference` and `uncertainty` from each concept, and **drops**
`grounding_status` and `source_claim_ids` entirely (it has no field for them).

This producer adds that missing layer. It groups the understanding's concepts
into bounded semantic groups, attaches the per-concept grounding and claim
provenance the downstream boundary cannot carry, and emits a
contract-compatible envelope that the real downstream boundary accepts.

────────────────────────────────────────────────────────────────────────────
THE GROUPING DECISION (stated because it is load-bearing)
────────────────────────────────────────────────────────────────────────────

Concepts are partitioned into a bounded group by the **relationship context the
downstream boundary would resolve for them** — determined by matching the
understanding's own concept labels against the closed vocabulary the
relationship boundary declares.

This is *semantic grouping only*: the producer partitions concepts that already
exist, using a vocabulary that already exists. It resolves, ranks, merges and
interprets nothing.

**The producer deliberately does NOT re-derive or duplicate the relationship
rules.** Deriving `relationship_type` here would create a second, competing
source of relationship truth that could silently drift from the downstream
boundary's own table — exactly the duplication the architecture forbids. The
single source of relationship truth stays in
`build_architectural_concept_relationship_v1`; this module only supplies what
that boundary needs but cannot express.

────────────────────────────────────────────────────────────────────────────
WHAT THIS DOES NOT DO
────────────────────────────────────────────────────────────────────────────

    - create an authoritative ontology
    - create rules
    - create recommendations
    - infer layouts
    - perform design reasoning
    - create geometry
    - access Memory
    - persist data

Every label, pattern, evidence reference, grounding status, claim ID and
uncertainty value emitted is a verbatim copy of a value that already existed
upstream. Nothing is invented.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalConceptRelationshipBuilderV1"
VERSION = "1.0"
SOURCE_CONTRACT = "ArchitecturalConceptUnderstandingV1"
SOURCE_VERSION = "1.0"
TARGET_CONTRACT = "ArchitecturalConceptRelationshipV1"
TARGET_VERSION = "1.0"

# The closed label vocabulary that `build_architectural_concept_relationship_v1`
# resolves against. Mirrored here ONLY to partition concepts into bounded
# groups. The relationship *types* are intentionally NOT mirrored — the
# downstream boundary remains the single source of relationship truth.
_RELATIONSHIP_CONTEXT_LABELS = (
    "sleeping_space_with_storage_association",
    "sleeping_space_with_sanitary_association",
    "circulation_related_semantic_context",
    "opening_related_semantic_context",
)

_STRUCTURAL_NON_CLAIMS = {
    "not_authoritative_ontology": True,
    "not_permanent_knowledge": True,
    "not_design_rule": True,
    "not_recommendation": True,
    "not_layout": True,
    "not_geometry": True,
    "not_design_solution": True,
    "not_design_reasoning": True,
    "not_memory": True,
    "not_learned_model": True,
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
            "ArchitecturalConceptRelationshipBuilderV1 requires an "
            "ArchitecturalConceptUnderstandingV1 dict"
        )
    if value.get("contract") != SOURCE_CONTRACT:
        raise ValueError(
            "ArchitecturalConceptRelationshipBuilderV1 accepts only "
            "ArchitecturalConceptUnderstandingV1"
        )
    if value.get("version") != SOURCE_VERSION:
        raise ValueError(
            "ArchitecturalConceptRelationshipBuilderV1 requires understanding "
            "version 1.0"
        )
    return value


def _concept_label(concept: Dict[str, Any]) -> Any:
    return concept.get("semantic_label")


def _context_labels(concept: Dict[str, Any]) -> List[str]:
    """Which declared relationship-context labels this concept carries."""
    label = _concept_label(concept)
    return [label] if label in _RELATIONSHIP_CONTEXT_LABELS else []


def _provenance(concept: Dict[str, Any]) -> Dict[str, Any]:
    """Grounding and claim provenance for one concept, keyed by its label.

    IMPORTANT — an upstream constraint, not a choice made here:

    `ArchitecturalConceptUnderstandingV1` does NOT copy `grounding_status` or
    `source_claim_ids` onto its concepts. Its concept shape is exactly
    {concept_type, semantic_label, source_patterns, evidence_reference,
    uncertainty, status}. Those two fields are therefore **absent by
    construction** by the time this boundary is reached.

    This producer must not fabricate them, and must not silently report an
    empty list as though the claim were "no grounding exists". It reports the
    honest absence explicitly so a consumer can distinguish:

        grounding_status: []      -> the value genuinely is empty
        grounding_status: None    -> the value was not carried this far

    The ONLY recovery available without violating the input gate is when a
    caller carries an explicit `source_cases` on the concept (i.e. the
    understanding envelope was produced by a builder that preserved them).
    When present they are used verbatim; otherwise the field is `None`.
    """
    cases = [
        case
        for case in _list(concept.get("source_cases"))
        if isinstance(case, dict)
    ]

    direct_grounding = concept.get("grounding_status")
    direct_claims = concept.get("source_claim_ids")

    if direct_grounding is not None:
        grounding: Any = _unique(_list(direct_grounding))
    elif cases:
        grounding = _unique(
            status
            for case in cases
            for status in _list(case.get("grounding_status"))
        )
    else:
        grounding = None

    if direct_claims is not None:
        claims: Any = _unique(_list(direct_claims))
    elif cases:
        claims = _unique(
            claim_id
            for case in cases
            for claim_id in _list(case.get("source_claim_ids"))
        )
    else:
        claims = None

    return {
        "semantic_label": _concept_label(concept),
        "source_patterns": _list(concept.get("source_patterns")),
        "grounding_status": grounding,
        "source_claim_ids": claims,
    }


def _groups(concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Partition concepts into bounded groups by relationship context.

    A concept that carries no declared relationship-context label is still
    reported — in its own bounded group with an empty context — never dropped
    and never mapped onto a context it does not have.
    """
    contexts: List[str] = []
    buckets: Dict[str, List[Dict[str, Any]]] = {}

    for concept in concepts:
        labels = _context_labels(concept)
        if not labels:
            labels = [""]
        for label in labels:
            if label not in contexts:
                contexts.append(label)
                buckets[label] = []
            buckets[label].append(concept)

    groups = []
    for context in contexts:
        members = buckets[context]
        groups.append(
            {
                "relationship_context": context or None,
                "declared_contexts": [context] if context else [],
                "unresolved_relationship_context": [] if context else [True],
                "related_concepts": _unique(
                    _concept_label(concept) for concept in members
                ),
                "source_patterns": _unique(
                    pattern
                    for concept in members
                    for pattern in _list(concept.get("source_patterns"))
                ),
                "evidence_reference": _unique(
                    evidence
                    for concept in members
                    for evidence in _list(concept.get("evidence_reference"))
                ),
                "uncertainty": [
                    deepcopy(concept.get("uncertainty"))
                    for concept in members
                    if concept.get("uncertainty")
                ],
                "concept_provenance": [
                    _provenance(concept) for concept in members
                ],
                "status": "bounded_semantic_group",
            }
        )
    return groups


def build_architectural_concept_relationship_input_v1(
    concept_understanding: Dict[str, Any],
) -> Dict[str, Any]:
    """Produce a bounded relationship input from concept understanding.

    The returned dict carries the `ArchitecturalConceptUnderstandingV1`
    contract surface and is therefore acceptable by
    `build_architectural_concept_relationship_v1`. The producer adds bounded
    semantic groups plus the grounding/claim provenance that boundary cannot
    carry, and passes the envelope keys through untouched so the downstream
    boundary's own validation and preservation rules apply unchanged.

    Transient (`persistent: False`), read-only (`read_only: True`).
    """
    source = _validate_understanding(concept_understanding)

    concepts = [
        concept
        for concept in _list(source.get("concepts"))
        if isinstance(concept, dict)
    ]
    groups = _groups(concepts)

    provenance = {
        "contract": CONTRACT,
        "version": VERSION,
        "source_contract": SOURCE_CONTRACT,
        "source_version": SOURCE_VERSION,
        "grouping_unit": "relationship_context",
        "grouping_only": True,
        "relationship_rules_owned_by": TARGET_CONTRACT,
    }

    produced = deepcopy(source)
    produced["contract"] = SOURCE_CONTRACT
    produced["version"] = SOURCE_VERSION
    produced["concepts"] = deepcopy(concepts)
    produced["semantic_groups"] = groups
    produced["source_patterns"] = _unique(
        pattern
        for concept in concepts
        for pattern in _list(concept.get("source_patterns"))
    )
    produced["grounding_status"] = _unique(
        status
        for group in groups
        for entry in group["concept_provenance"]
        for status in _list(entry["grounding_status"])
    )
    produced["source_claim_ids"] = _unique(
        claim_id
        for group in groups
        for entry in group["concept_provenance"]
        for claim_id in _list(entry["source_claim_ids"])
    )
    # Honest absence reporting: distinguish "carried and empty" from "not
    # carried this far". The understanding boundary drops both fields, so in
    # the default chain these are None, not [].
    produced["grounding_status_present"] = any(
        entry["grounding_status"] is not None
        for group in groups
        for entry in group["concept_provenance"]
    )
    produced["source_claim_ids_present"] = any(
        entry["source_claim_ids"] is not None
        for group in groups
        for entry in group["concept_provenance"]
    )
    produced["physical_inputs"] = []
    produced["non_claims"] = deepcopy(_STRUCTURAL_NON_CLAIMS)
    produced["persistent"] = False
    produced["read_only"] = True
    produced["produced_by"] = provenance
    _assert_no_forbidden_language(produced)
    return produced


def _assert_no_forbidden_language(result: Dict[str, Any]) -> None:
    """Refuse to emit rule-like or physical vocabulary.

    The scan reads only values this boundary authored. Upstream pass-throughs
    (`concepts`, `evidence_basis`, `uncertainty`) are excluded because they are
    verbatim and were not written here, and `non_claims` is excluded because
    its keys legitimately contain the terms as negations.
    """
    authored = {
        "source_patterns": result.get("source_patterns"),
        "grounding_status": result.get("grounding_status"),
        "source_claim_ids": result.get("source_claim_ids"),
        "produced_by": result.get("produced_by"),
        "semantic_groups": [
            {
                key: value
                for key, value in group.items()
                if key
                not in {
                    "related_concepts",
                    "evidence_reference",
                    "uncertainty",
                    "concept_provenance",
                }
            }
            for group in result.get("semantic_groups") or []
        ],
    }
    serialized = str(authored).lower()
    for term in _FORBIDDEN_TERMS:
        if term in serialized:
            raise AssertionError(
                "ArchitecturalConceptRelationshipBuilderV1 emitted forbidden "
                "term: " + term
            )
