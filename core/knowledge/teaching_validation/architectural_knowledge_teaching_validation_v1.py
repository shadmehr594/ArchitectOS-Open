"""Bounded teaching-and-validation boundary for architectural knowledge.

This module implements the semantic-learning VALIDATION boundary. It answers
exactly one question:

    "Did ArchitectOS understand the architectural concept?"

It deliberately does NOT answer:

    "Can ArchitectOS draw CAD?"

────────────────────────────────────────────────────────────────────────────
WHAT THIS BOUNDARY IS
────────────────────────────────────────────────────────────────────────────

A human supplies a teaching case (a bounded architectural example) and an
architectural query. The boundary:

    1. validates the teaching case against a strict contract;
    2. resolves the query's concepts against the KNOWN semantic vocabulary;
    3. compares that known vocabulary against what the teaching case declares;
    4. reports an understanding status and the questions a human could use to
       probe the gap.

Statusing is therefore a pure set comparison over a closed, declared
vocabulary. Nothing is inferred, ranked, scored or generated.

────────────────────────────────────────────────────────────────────────────
FORBIDDEN INPUT (rejected, not coerced)
────────────────────────────────────────────────────────────────────────────

    raw images · Vision output · Observation output · Geometry · CAD/BIM/IFC ·
    Memory objects · Design solutions · unrelated intent contracts

────────────────────────────────────────────────────────────────────────────
FORBIDDEN BEHAVIOUR
────────────────────────────────────────────────────────────────────────────

    - generating geometry, layouts or spatial placement
    - producing a design solution or recommendation
    - creating architectural rules or standards
    - learning permanently, or writing to Memory
    - persisting anything
    - merging or bypassing any existing contract boundary

This boundary is transient, read-only and deterministic.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalKnowledgeTeachingValidationV1"
VERSION = "1.0"

TEACHING_CASE_CONTRACT = "ArchitecturalTeachingCaseV1"
TEACHING_CASE_VERSION = "1.0"

UNDERSTANDING_STATUSES = (
    "understood",
    "partially_understood",
    "unresolved",
)

_REQUIRED_NON_CLAIMS = {
    "not_design_rule": True,
    "not_recommendation": True,
    "not_authoritative_knowledge": True,
    "not_memory": True,
    "not_learned_model": True,
    "not_design_solution": True,
}

TEACHING_CASE_REQUIRED_FIELDS = (
    "case_id",
    "domain",
    "description",
    "human_explanation",
    "related_concepts",
    "related_patterns",
)

# ---------------------------------------------------------------------------
# The closed semantic vocabulary this boundary resolves against.
#
# This is a declared lookup table, NOT a learned or inferred model. It mirrors
# the vocabulary already in use by the semantic library / curriculum lineage so
# the boundary does not invent a competing one.
# ---------------------------------------------------------------------------

_KNOWN_PATTERNS = {
    "sleeping_storage_relation": "sleeping_space_association",
    "sleeping_sanitary_relation": "sleeping_space_association",
    "circulation_connection_relation": "circulation_association",
    "opening_space_relation": "boundary_association",
    "opening_associated_with_space": "boundary_association",
    "opening_within_facade_plane": "boundary_association",
    "entrance_threshold_in_facade_composition": "boundary_association",
}

_KNOWN_CONCEPT_LABELS = {
    "sleeping_space_with_storage_association": "sleeping_space_association",
    "sleeping_space_with_sanitary_association": "sleeping_space_association",
    "circulation_related_semantic_context": "circulation_association",
    "opening_related_semantic_context": "boundary_association",
}

# Concept / term vocabulary drawn from the curriculum's own space-identity and
# semantic-zone sets. A query naming one of these resolves to a known concept
# context even when no pattern string is supplied.
_KNOWN_TERMS = {
    "bedroom": "sleeping_space_association",
    "master_bedroom": "sleeping_space_association",
    "bathroom": "sanitary_service_association",
    "kitchen": "service_space_association",
    "living_room": "public_space_association",
    "living_space": "public_space_association",
    "corridor": "circulation_association",
    "entrance": "boundary_association",
    "private_space": "private_space_association",
    "service_space": "service_space_association",
    "public_space": "public_space_association",
    "circulation_space": "circulation_association",
}

# The vocabulary expectation each query context carries. Declared, not learned.
_CONTEXT_EXPECTATIONS = {
    "sleeping_space_association": (
        "sleeping_space_with_storage_association",
        "sleeping_space_with_sanitary_association",
    ),
    "sanitary_service_association": (
        "sleeping_space_with_sanitary_association",
    ),
    "service_space_association": (
        "functional_relationship_context",
    ),
    "public_space_association": (
        "functional_relationship_context",
    ),
    "private_space_association": (
        "sleeping_space_with_storage_association",
        "sleeping_space_with_sanitary_association",
    ),
    "circulation_association": (
        "circulation_related_semantic_context",
    ),
    "boundary_association": (
        "boundary_connection_context",
    ),
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

_FORBIDDEN_CONTRACTS = (
    "ArchitecturalUnderstandingV2",
    "ArchitecturalUnderstandingV1",
    "ArchitecturalObservationV1",
    "VisionObservationV1",
    "ArchitecturalVisionReportV1",
    "ImageIntentV1",
    "SiteIntentV1",
    "ArchitecturalGeometryIntentV1",
    "ArchitecturalLayoutIntentResolverV1",
    "ProgramIntentResolutionV1",
    "ArchitecturalDesignReasoningResultV1",
    "ArchitecturalSpatialReasoningCandidateV1",
    "ArchitecturalMemoryRecordV1",
    "MemoryRecordV1",
    "ArchitecturalBIMEntityV1",
    "ArchitecturalIFCEntityV1",
    "ArchitecturalCADDrawingV1",
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


def _tokenize(value: Any) -> List[str]:
    text = str(value or "").lower()
    for character in ("_", "-", ".", ",", ";", ":", "/", "\\", "(", ")", "[", "]"):
        text = text.replace(character, " ")
    return [token for token in text.split() if token]


def _normalise(value: Any) -> str:
    return " ".join(_tokenize(value))


def _validate_teaching_case(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalKnowledgeTeachingValidationV1 requires an "
            "ArchitecturalTeachingCaseV1 dict"
        )
    contract = value.get("contract")
    if contract is None:
        raise ValueError(
            "ArchitecturalTeachingCaseV1 is missing the required 'contract' field"
        )
    if contract in _FORBIDDEN_CONTRACTS:
        raise ValueError(
            "ArchitecturalKnowledgeTeachingValidationV1 rejects forbidden input "
            "contract: " + str(contract)
        )
    if contract != TEACHING_CASE_CONTRACT:
        raise ValueError(
            "ArchitecturalKnowledgeTeachingValidationV1 accepts only "
            "ArchitecturalTeachingCaseV1"
        )
    if value.get("version") != TEACHING_CASE_VERSION:
        raise ValueError(
            "ArchitecturalKnowledgeTeachingValidationV1 requires teaching case "
            "version 1.0"
        )
    return value


def _validate_query(value: Any) -> Dict[str, Any]:
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("architectural_query must not be empty")
        return {"query": value.strip()}
    if not isinstance(value, dict):
        raise TypeError(
            "architectural_query must be a string or a mapping of query terms"
        )
    return value


def _query_terms(query: Dict[str, Any]) -> List[str]:
    values: List[Any] = []
    for key in (
        "query",
        "concept",
        "concepts",
        "space",
        "topic",
        "pattern",
        "patterns",
    ):
        if key in query:
            values.extend(_list(query.get(key)))
    return [str(value) for value in values if str(value or "").strip()]


def _known_patterns_of(terms: List[str]) -> List[str]:
    found = []
    for term in terms:
        normalised = _normalise(term)
        for pattern in _KNOWN_PATTERNS:
            if _normalise(pattern) == normalised and pattern not in found:
                found.append(pattern)
    return found


def _known_concept_labels_of(terms: List[str]) -> List[str]:
    found = []
    for term in terms:
        normalised = _normalise(term)
        for label in _KNOWN_CONCEPT_LABELS:
            if _normalise(label) == normalised and label not in found:
                found.append(label)
    return found


def _known_terms_of(terms: List[str]) -> List[str]:
    """Longest-match resolution of query vocabulary to declared contexts."""
    found = []
    for term in terms:
        normalised = _normalise(term)
        for candidate in sorted(_KNOWN_TERMS, key=len, reverse=True):
            if _normalise(candidate) == normalised:
                if candidate not in found:
                    found.append(candidate)
    return found


def _expected_labels(contexts: List[str]) -> List[str]:
    expected = []
    for context in contexts:
        for label in _CONTEXT_EXPECTATIONS.get(context, ()):
            if label not in expected:
                expected.append(label)
    return expected


def _teaching_case_labels(case: Dict[str, Any]) -> List[str]:
    labels = []
    labels.extend(str(value) for value in _list(case.get("related_concepts")))
    labels.extend(str(value) for value in _list(case.get("related_patterns")))
    return labels


def _understanding_status(
    expected_labels: List[str],
    matched_labels: List[str],
    matched_patterns: List[str],
    query_is_known: bool,
) -> str:
    if not query_is_known:
        return "unresolved"
    if not expected_labels:
        # The query resolved to a known context, but that context declares no
        # expected concept vocabulary. Nothing can be confirmed either way.
        return "unresolved" if not matched_patterns else "partially_understood"
    if set(expected_labels).issubset(set(matched_labels)):
        return "understood"
    if matched_labels or matched_patterns:
        return "partially_understood"
    return "unresolved"


def _validation_questions(
    status: str,
    expected_labels: List[str],
    matched_labels: List[str],
    unmatched_labels: List[str],
    case: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Questions a human could use to probe the understanding gap.

    These are PROMPTS for a human, not instructions to a system. They assert
    nothing and request no action.
    """
    questions = []
    normalised = _normalise(case.get("human_explanation"))

    if status == "understood":
        for label in matched_labels:
            questions.append(
                {
                    "question_type": "confirmation_probe",
                    "target": label,
                    "question": (
                        "Does the explanation cover the relationship named by "
                        + label
                        + "?"
                    ),
                    "rationale": "human_confirmation_requested",
                }
            )
        return questions

    if status == "partially_understood":
        for label in unmatched_labels:
            questions.append(
                {
                    "question_type": "missing_concept_probe",
                    "target": label,
                    "question": (
                        "The explanation does not address " + label
                        + ". Can you describe how that relationship appears in "
                        "this example?"
                    ),
                    "rationale": "declared_concept_not_present_in_explanation",
                }
            )
        for label in matched_labels:
            questions.append(
                {
                    "question_type": "confirmation_probe",
                    "target": label,
                    "question": (
                        "Is the reading of " + label
                        + " consistent with what you intended?"
                    ),
                    "rationale": "human_confirmation_requested",
                }
            )
        return questions

    # unresolved
    questions.append(
        {
            "question_type": "unresolved_concept_probe",
            "target": None,
            "question": (
                "This query does not resolve against the known architectural "
                "vocabulary. Can you restate it using an established concept "
                "or pattern term?"
            ),
            "rationale": "query_outside_declared_vocabulary",
        }
    )
    if not normalised:
        questions.append(
            {
                "question_type": "missing_explanation_probe",
                "target": None,
                "question": (
                    "No human explanation was supplied for this case. Can you "
                    "describe the architectural relationship you have in mind?"
                ),
                "rationale": "human_explanation_absent",
            }
        )
    return questions


def validate_architectural_knowledge_understanding_v1(
    teaching_case: Dict[str, Any],
    architectural_query: Any,
) -> Dict[str, Any]:
    """Validate whether a teaching case supports a claimed understanding.

    Pure function. Deterministic. Reads nothing, writes nothing, learns
    nothing.
    """
    case = _validate_teaching_case(teaching_case)
    query = _validate_query(architectural_query)

    terms = _query_terms(query)
    query_patterns = _known_patterns_of(terms)
    query_labels = _known_concept_labels_of(terms)
    query_terms = _known_terms_of(terms)
    query_contexts = _unique(
        [_KNOWN_TERMS[term] for term in query_terms]
        + [_KNOWN_PATTERNS[pattern] for pattern in query_patterns]
        + [_KNOWN_CONCEPT_LABELS[label] for label in query_labels]
    )
    query_is_known = bool(query_contexts)

    expected_labels = _expected_labels(query_contexts)
    case_labels = _teaching_case_labels(case)

    matched_labels = [
        label for label in expected_labels if label in case_labels
    ]
    unmatched_labels = [
        label for label in expected_labels if label not in case_labels
    ]
    matched_patterns = _unique(
        pattern for pattern in query_patterns if pattern in case_labels
    )
    # Patterns the case declares that the query also names by vocabulary.
    for pattern in query_patterns:
        if pattern in case_labels and pattern not in matched_patterns:
            matched_patterns.append(pattern)

    status = _understanding_status(
        expected_labels, matched_labels, matched_patterns, query_is_known
    )

    preserved_evidence = [
        {
            "case_id": case.get("case_id"),
            "evidence_reference": _list(case.get("evidence_reference")),
            "grounding_status": _list(case.get("grounding_status")),
            "source_claim_ids": _list(case.get("source_claim_ids")),
        }
    ]

    uncertainty = {
        "source_uncertainty": deepcopy(case.get("uncertainty") or {}),
        "unmatched_concepts": unmatched_labels,
        "query_terms_unresolved": [
            term for term in terms if not _normalise(term) == ""
        ]
        if not query_is_known
        else [],
        "validated": False,
    }

    explanation_basis = {
        "human_explanation_present": bool(_normalise(case.get("human_explanation"))),
        "human_explanation_length": len(
            _normalise(case.get("human_explanation"))
        ),
        "declared_concepts": _list(case.get("related_concepts")),
        "declared_patterns": _list(case.get("related_patterns")),
        "resolved_contexts": query_contexts,
        # The explanation text itself is NOT copied forward. It is human
        # narrative, not structural data.
        "restatement_of_explanation": None,
    }

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "understanding_status": status,
        "matched_semantic_patterns": _unique(
            query_patterns + matched_patterns + matched_labels
        ),
        "preserved_evidence": preserved_evidence,
        "uncertainty": uncertainty,
        "explanation_basis": explanation_basis,
        "validation_questions": _validation_questions(
            status, expected_labels, matched_labels, unmatched_labels, case
        ),
        "non_claims": deepcopy(_REQUIRED_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }
    _assert_no_forbidden_language(result)
    return result


def _assert_no_forbidden_language(result: Dict[str, Any]) -> None:
    """Refuse to emit rule-like, physical or promotional vocabulary.

    Only the payload this boundary authored is scanned. `non_claims` is
    excluded because its keys legitimately contain the forbidden terms as
    negations.
    """
    authored = {
        "understanding_status": result.get("understanding_status"),
        "matched_semantic_patterns": result.get("matched_semantic_patterns"),
        "preserved_evidence": result.get("preserved_evidence"),
        "uncertainty": result.get("uncertainty"),
        "validation_questions": result.get("validation_questions"),
    }
    serialized = str(authored).lower()
    for term in _FORBIDDEN_TERMS:
        if term in serialized:
            raise AssertionError(
                "ArchitecturalKnowledgeTeachingValidationV1 emitted forbidden "
                "term: " + term
            )
