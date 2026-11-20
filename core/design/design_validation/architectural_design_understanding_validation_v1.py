"""Bounded architectural DESIGN UNDERSTANDING validation boundary.

This module implements the semantic design-validation boundary. It answers
exactly one question:

    "Can ArchitectOS reason about a NEW architectural problem using the
     concepts it has already learned?"

It deliberately does NOT answer:

    "Can ArchitectOS draw / model / render the design?"

────────────────────────────────────────────────────────────────────────────
WHAT THIS BOUNDARY IS
────────────────────────────────────────────────────────────────────────────

A human supplies:

    architectural_case   — a bounded description of a NEW architectural
                           problem (a brief-style statement, not a drawing).
    knowledge_context    — the SEMANTIC knowledge ArchitectOS already holds
                           (space-identity cases, functional relationship
                           cases, semantic-zone cases, known concept and
                           pattern vocabulary).

The boundary:

    1. validates both inputs against strict, named contracts;
    2. reads the case as a bag of declared space/function tokens;
    3. resolves those tokens against the DECLARED knowledge vocabulary only;
    4. reports what was understood, which known concepts were actually reused,
       which relationships were identified, what remained UNKNOWN, and the
       questions a human could ask to close the gap.

────────────────────────────────────────────────────────────────────────────
WHY THIS IS NOT A DRAWING SYSTEM
────────────────────────────────────────────────────────────────────────────

The output vocabulary is deliberately semantic:

    space identity · functional relationship · privacy relationship ·
    circulation concept · opening relationship · unknowns

There is NO dimension, NO coordinate, NO wall location, NO door swing, NO
structural member, NO CAD entity, NO BIM/IFC object and NO construction
decision anywhere in this module's authored output. Those are physically
absent from the code, not merely discouraged by prose.

────────────────────────────────────────────────────────────────────────────
FORBIDDEN INPUT (rejected, not coerced)
────────────────────────────────────────────────────────────────────────────

    raw images · Vision output · geometry · CAD · DWG · DXF · BIM · IFC ·
    rendering output · Memory objects · design solutions ·
    unrelated intent / reasoning contracts

────────────────────────────────────────────────────────────────────────────
FORBIDDEN BEHAVIOUR
────────────────────────────────────────────────────────────────────────────

    - generating geometry, layouts, dimensions or spatial placement
    - producing a design solution or recommendation
    - creating architectural rules or standards
    - learning permanently, or writing to Memory
    - persisting anything
    - bypassing, merging or replacing any existing contract boundary
    - creating hidden adapters between isolated intent lineages

This boundary is transient, read-only and deterministic.
"""

from __future__ import annotations

import re

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalDesignUnderstandingValidationV1"
VERSION = "1.0"


# --------------------------------------------------------------------------- #
# Input contracts
# --------------------------------------------------------------------------- #
# The architectural case is a NEW problem statement. It is declared here so the
# boundary owns the shape of what it accepts rather than accepting free text.
ARCHITECTURAL_CASE_CONTRACT = "ArchitecturalDesignProblemCaseV1"
ARCHITECTURAL_CASE_VERSION = "1.0"

# The knowledge context is the SEMANTIC knowledge already acquired. This is the
# upstream structure-spine surface produced by the foundation knowledge set.
KNOWLEDGE_CONTEXT_CONTRACT = "ArchitecturalFoundationKnowledgeSetV1"
KNOWLEDGE_CONTEXT_VERSION = "1.0"

# Contracts that must never be accepted in place of the two declared inputs.
# These are rejected explicitly so that no hidden adapter can smuggle a
# downstream artefact back in as "knowledge".
_FORBIDDEN_CONTRACTS = (
    # vision / observation
    "ArchitecturalUnderstandingV2",
    "ArchitecturalUnderstandingV1",
    "ArchitecturalObservationV1",
    "VisionObservationV1",
    "ArchitecturalVisionReportV1",
    "ImageIntentV1",
    "SiteIntentV1",
    # geometry / drawing / modelling
    "ArchitecturalGeometryIntentV1",
    "ArchitecturalLayoutIntentResolverV1",
    "ProgramIntentResolutionV1",
    "ArchitecturalCADDrawingV1",
    "ArchitecturalDXFDrawingV1",
    "ArchitecturalDWGDrawingV1",
    "ArchitecturalBIMEntityV1",
    "ArchitecturalIFCEntityV1",
    "ArchitecturalRenderingOutputV1",
    # memory
    "ArchitecturalMemoryRecordV1",
    "MemoryRecordV1",
    # downstream design artefacts (this boundary validates BEFORE them)
    "ArchitecturalDesignReasoningInputV1",
    "ArchitecturalDesignReasoningResultV1",
    "ArchitecturalSpatialReasoningCandidateV1",
    "ArchitecturalDesignReasoningContextV1",
    # unrelated intent lineages
    "ArchitecturalIntentResolutionV1",
    "ArchitecturalIntentCandidateV1",
    "ArchitecturalSemanticGraphV1",
    "ArchitecturalConceptOntologyV1",
    # the sibling validation boundary is NOT the accepted knowledge context
    "ArchitecturalKnowledgeTeachingValidationV1",
    "ArchitecturalTeachingCaseV1",
    "ArchitecturalTeachingSessionV1",
)


# --------------------------------------------------------------------------- #
# Required non-claims — every key is True and every key negates a capability
# this boundary does NOT have.
# --------------------------------------------------------------------------- #
_REQUIRED_NON_CLAIMS = {
    "not_design_rule": True,
    "not_recommendation": True,
    "not_authoritative_knowledge": True,
    "not_memory": True,
    "not_learned_model": True,
    "not_design_solution": True,
}


# --------------------------------------------------------------------------- #
# The closed semantic vocabulary this boundary resolves against.
#
# These are DECLARED lookup tables, not a learned or inferred model. The space
# identity and semantic-zone terms mirror the vocabulary already in use by the
# foundation knowledge set / curriculum lineage, so this boundary never invents
# a competing one.
# --------------------------------------------------------------------------- #

# space token -> declared space identity concept
_SPACE_IDENTITY = {
    "entrance": "entrance_transition_space",
    "entry": "entrance_transition_space",
    "foyer": "entrance_transition_space",
    "threshold": "entrance_transition_space",
    "living_room": "public_living_space",
    "living_space": "public_living_space",
    "living": "public_living_space",
    "guest_space": "public_living_space",
    "bedroom": "private_sleeping_space",
    "master_bedroom": "private_sleeping_space",
    "sleeping_space": "private_sleeping_space",
    "bathroom": "sanitary_service_space",
    "toilet": "sanitary_service_space",
    "sanitary": "sanitary_service_space",
    "kitchen": "service_space",
    "service": "service_space",
    "utility": "service_space",
    "corridor": "circulation_space",
    "hallway": "circulation_space",
    "passage": "circulation_space",
    "stairs": "circulation_space",
    "stair": "circulation_space",
    "storage": "storage_space",
    "closet": "storage_space",
    "wardrobe": "storage_space",
    "outdoor": "outdoor_connection_space",
    "garden": "outdoor_connection_space",
    "yard": "outdoor_connection_space",
    "courtyard": "outdoor_connection_space",
    "terrace": "outdoor_connection_space",
    "balcony": "outdoor_connection_space",
}

# Declared space classes. Every SpaceIdentityEntry carries all of these so the
# downstream consumer never infers a missing class from an absent key.
_SPACE_CLASS_KEYS = (
    "public",
    "private",
    "service",
    "circulation",
    "outdoor",
    "storage",
)

# Privacy relationship vocabulary.
# A declared token may establish a PRIVACY class. Relationship *types* stay
# owned by the relationship structure; this boundary only reports the privacy
# relationship as an observation over two identified spaces.
_PRIVACY_BY_TOKEN = {
    "private_space": "private",
    "private": "private",
    "privacy": "private",
    "public_space": "public",
    "public": "public",
    "shared_space": "public",
    "service_space": "service",
}

# Relationship vocabulary. The relationship types are DECLARED and stable:
# they describe semantic association only, never geometry.
_RELATIONSHIP_TYPES = (
    "private_sleeping_zone_containment",
    "sleeping_space_with_sanitary_association",
    "sleeping_space_with_storage_association",
    "functional_service_association",
    "public_circulation_association",
    "circulation_connection_association",
    "entrance_threshold_relationship",
    "outdoor_connection_association",
    "privacy_separation_relationship",
)


# --------------------------------------------------------------------------- #
# Forbidden language. These terms describe rules, physical form, or drawing
# systems. They must never appear in the payload this boundary authors.
# --------------------------------------------------------------------------- #
_FORBIDDEN_TERMS = (
    "should",
    "must",
    "optimal",
    "best",
    "recommended",
    "design_solution",
    "design_rule",
    "layout",
    "placement",
    "adjacent",
    "geometry",
    "dimension",
    "dimensions",
    "coordinate",
    "wall",
    "door",
    "window_position",
    "cad",
    "dwg",
    "dxf",
    "bim",
    "ifc",
    "render",
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
    result: List[Any] = []
    for value in values:
        if value not in result:
            result.append(deepcopy(value))
    return result


def _tokenize(value: Any) -> List[str]:
    text = str(value or "").lower()
    for character in (
        "_",
        "-",
        ".",
        ",",
        ";",
        ":",
        "/",
        "\\",
        "(",
        ")",
        "[",
        "]",
        "\n",
        "\t",
    ):
        text = text.replace(character, " ")
    return [token for token in text.split() if token]


def _normalise(value: Any) -> str:
    return " ".join(_tokenize(value))


def _phrases(value: Any) -> List[str]:
    """Return both whole phrases and single tokens, longest phrase first.

    A declared multi-word key such as ``master_bedroom`` must be matchable.
    Single-token matching alone would silently drop it — the exact
    "declare a rule, never apply it" failure this project forbids.
    """
    normalised = _normalise(value)
    if not normalised:
        return []
    tokens = normalised.split()
    phrases: List[str] = [normalised]
    # Every contiguous n-gram, longest first, so a two-word key wins over its
    # own one-word components.
    for size in range(len(tokens), 0, -1):
        for start in range(0, len(tokens) - size + 1):
            candidate = " ".join(tokens[start : start + size])
            if candidate not in phrases:
                phrases.append(candidate)
    return phrases


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #
def _validate_architectural_case(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalDesignUnderstandingValidationV1 requires an "
            "ArchitecturalDesignProblemCaseV1 dict as its first argument"
        )
    contract = value.get("contract")
    if contract is None:
        raise ValueError(
            "ArchitecturalDesignProblemCaseV1 is missing the required "
            "'contract' field"
        )
    if contract in _FORBIDDEN_CONTRACTS:
        raise ValueError(
            "ArchitecturalDesignUnderstandingValidationV1 rejects forbidden "
            "first-argument contract: " + str(contract)
        )
    if contract != ARCHITECTURAL_CASE_CONTRACT:
        raise ValueError(
            "ArchitecturalDesignUnderstandingValidationV1 accepts only "
            "ArchitecturalDesignProblemCaseV1 (got: " + str(contract) + ")"
        )
    if value.get("version") != ARCHITECTURAL_CASE_VERSION:
        raise ValueError(
            "ArchitecturalDesignUnderstandingValidationV1 requires "
            "architectural case version " + ARCHITECTURAL_CASE_VERSION
        )
    return value


def _validate_knowledge_context(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalDesignUnderstandingValidationV1 requires an "
            "ArchitecturalFoundationKnowledgeSetV1 dict as its second argument"
        )
    contract = value.get("contract")
    if contract is None:
        raise ValueError(
            "ArchitecturalFoundationKnowledgeSetV1 is missing the required "
            "'contract' field"
        )
    if contract in _FORBIDDEN_CONTRACTS:
        raise ValueError(
            "ArchitecturalDesignUnderstandingValidationV1 rejects forbidden "
            "second-argument contract: " + str(contract)
        )
    if contract != KNOWLEDGE_CONTEXT_CONTRACT:
        raise ValueError(
            "ArchitecturalDesignUnderstandingValidationV1 accepts only "
            "ArchitecturalFoundationKnowledgeSetV1 (got: "
            + str(contract)
            + ")"
        )
    if value.get("version") != KNOWLEDGE_CONTEXT_VERSION:
        raise ValueError(
            "ArchitecturalDesignUnderstandingValidationV1 requires knowledge "
            "context version " + KNOWLEDGE_CONTEXT_VERSION
        )
    return value


# --------------------------------------------------------------------------- #
# Case reading — the case is read as tokens, never parsed for geometry.
# --------------------------------------------------------------------------- #
def _case_tokens(case: Dict[str, Any]) -> List[str]:
    """Return every declared token of the problem statement, normalised.

    Only declared text fields are read: the description, the stated space
    programme, the stated functions and the stated relationships. No imagery,
    no measurements, no coordinates.
    """
    tokens: List[str] = []
    for key in (
        "description",
        "problem_statement",
        "stated_spaces",
        "stated_functions",
        "stated_relationships",
        "user_requirements",
    ):
        value = case.get(key)
        if isinstance(value, str):
            tokens.extend(_tokenize(value))
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str):
                    tokens.extend(_tokenize(item))
        elif isinstance(value, dict):
            for item in value.values():
                if isinstance(item, str):
                    tokens.extend(_tokenize(item))
    return tokens


def _case_space_entries(case: Dict[str, Any]) -> List[str]:
    """The declared SPACE programme, each entry kept WHOLE.

    Entries are preserved as declared (``master_bedroom`` stays one entry) so
    multi-word keys can be matched. Pre-tokenising here would destroy the
    phrase and turn a declared rule into an inert one.
    """
    explicit = case.get("stated_spaces")
    if isinstance(explicit, (list, tuple)) and explicit:
        entries: List[str] = []
        for item in explicit:
            if isinstance(item, str) and item.strip():
                entries.append(item.strip())
            elif isinstance(item, dict):
                for value in item.values():
                    if isinstance(value, str) and value.strip():
                        entries.append(value.strip())
        if entries:
            return entries
    if isinstance(explicit, str) and explicit.strip():
        return [explicit.strip()]
    # Fall back to the declared prose fields, again kept whole per field.
    entries = []
    for key in (
        "description",
        "problem_statement",
        "stated_functions",
        "stated_relationships",
        "user_requirements",
    ):
        value = case.get(key)
        if isinstance(value, str) and value.strip():
            entries.append(value.strip())
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str) and item.strip():
                    entries.append(item.strip())
    return entries


def _case_space_tokens(case: Dict[str, Any]) -> List[str]:
    """Single tokens of the declared space programme.

    Used ONLY for reporting unknown vocabulary. Identity matching uses the
    whole ``_case_space_entries`` so phrases survive.
    """
    tokens: List[str] = []
    for entry in _case_space_entries(case):
        tokens.extend(_tokenize(entry))
    return tokens


def _declared_vocabulary(knowledge_context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the declared vocabulary from the knowledge context.

    The knowledge context is read, never mutated. Anything the context does not
    declare is simply absent — this boundary never invents knowledge.
    """
    concepts: List[str] = []
    patterns: List[str] = []
    dimensions: List[str] = []
    areas: List[str] = []

    for key in (
        "concepts",
        "known_concepts",
        "concept_labels",
        "related_concepts",
    ):
        for item in _list(knowledge_context.get(key)):
            if isinstance(item, str) and item.strip():
                concepts.append(item.strip())

    for key in ("patterns", "known_patterns", "related_patterns"):
        for item in _list(knowledge_context.get(key)):
            if isinstance(item, str) and item.strip():
                patterns.append(item.strip())

    # The foundation knowledge set groups cases by declared semantic area. Read
    # those groups so an area name alone can ground a relationship.
    for key in (
        "space_identity_cases",
        "functional_relationship_cases",
        "semantic_zone_cases",
    ):
        for item in _list(knowledge_context.get(key)):
            if isinstance(item, dict):
                areas.append(str(key))
                for label_key in ("concept", "concept_label", "semantic_label"):
                    value = item.get(label_key)
                    if isinstance(value, str) and value.strip():
                        concepts.append(value.strip())
                for pattern_key in ("pattern", "semantic_pattern"):
                    value = item.get(pattern_key)
                    if isinstance(value, str) and value.strip():
                        patterns.append(value.strip())
                for concept_key in ("related_concepts", "concepts"):
                    for value in _list(item.get(concept_key)):
                        if isinstance(value, str) and value.strip():
                            concepts.append(value.strip())
                for pattern_key in ("related_patterns", "patterns"):
                    for value in _list(item.get(pattern_key)):
                        if isinstance(value, str) and value.strip():
                            patterns.append(value.strip())

    for case in _list(knowledge_context.get("source_curriculum")):
        if isinstance(case, dict):
            area = case.get("semantic_area")
            if isinstance(area, str) and area.strip():
                dimensions.append(area.strip())
            for concept_key in ("related_concepts", "concepts"):
                for value in _list(case.get(concept_key)):
                    if isinstance(value, str) and value.strip():
                        concepts.append(value.strip())

    return {
        "concepts": _unique(concepts),
        "patterns": _unique(patterns),
        "areas": _unique(areas),
        "semantic_areas": _unique(dimensions),
        "declares_space_identity": bool(
            _list(knowledge_context.get("space_identity_cases"))
            or "space_identity" in dimensions
        ),
        "declares_functional_relationship": bool(
            _list(knowledge_context.get("functional_relationship_cases"))
            or "functional_association" in dimensions
        ),
        "declares_semantic_zone": bool(
            _list(knowledge_context.get("semantic_zone_cases"))
            or "semantic_zone" in dimensions
        ),
    }


def _vocabulary_has(vocabulary: Dict[str, Any], label: str) -> bool:
    """Is ``label`` declared by the knowledge context?

    Comparison is on the normalised form so ``sleeping-space`` and
    ``sleeping_space`` match without the boundary guessing a semantics.
    """
    target = _normalise(label)
    if not target:
        return False
    for key in ("concepts", "patterns"):
        for declared in vocabulary.get(key) or []:
            if _normalise(declared) == target:
                return True
    return False


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #
def _identified_spaces(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Identify space identity for each declared space token.

    Multi-word declared keys (``master_bedroom``) are matched as phrases, so a
    declared rule is actually applied rather than sitting inert. A token that
    resolves to no declared identity is reported as an unknown — never
    guessed.
    """
    # Normalised key -> canonical key. Sorted longest-first so ``master
    # bedroom`` wins over the bare ``bedroom``.
    lookup = {
        _normalise(key): key
        for key in sorted(_SPACE_IDENTITY, key=len, reverse=True)
    }

    spaces: List[Dict[str, Any]] = []
    seen: List[str] = []
    for entry in _case_space_entries(case):
        identity = None
        declared_token = None
        for phrase in _phrases(entry):
            key = lookup.get(phrase)
            if key:
                identity = _SPACE_IDENTITY[key]
                declared_token = key
                break
        if identity is None:
            continue
        if identity in seen:
            continue
        seen.append(identity)
        klass = _class_of(identity)
        classes = {key: (key == klass) for key in _SPACE_CLASS_KEYS}
        spaces.append(
            {
                "space_identity": identity,
                "declared_token": declared_token,
                "status": "identified",
                "space_classes": classes,
                "evidence_reference": [],
                "uncertainty": {},
            }
        )
    return spaces


def _class_of(identity: str) -> str:
    """Map a declared space identity to its declared space class.

    Order matters: ``sanitary_service_space`` is a SERVICE space, and must be
    classified before the broader ``service_`` check that would otherwise be
    reached only by prefix accident.
    """
    if identity.startswith("private_"):
        return "private"
    if identity.startswith("public_"):
        return "public"
    if identity.startswith("sanitary_"):
        return "service"
    if identity.startswith("service_"):
        return "service"
    if identity.startswith("circulation_"):
        return "circulation"
    if identity.startswith("outdoor_"):
        return "outdoor"
    if identity.startswith("storage_"):
        return "storage"
    return "unclassified"


def _declared_relationship_tokens(case: Dict[str, Any]) -> List[str]:
    """The tokens the case explicitly declares as RELATIONSHIPS.

    Privacy is a declared relationship, not an inference from a space name.
    Only the explicit relationship fields are read — never the free prose.
    """
    tokens: List[str] = []
    for key in ("stated_relationships", "stated_privacy", "privacy_requirements"):
        value = case.get(key)
        if isinstance(value, str):
            tokens.extend(_tokenize(value))
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str):
                    tokens.extend(_tokenize(item))
    return tokens


def _privacy_context(case: Dict[str, Any]) -> Dict[str, Any]:
    """Report the privacy class the case itself DECLARES, if any.

    No privacy class is inferred from a space identity alone. If the case does
    not declare one, the value is honestly empty.
    """
    declared: List[str] = []
    for token in _declared_relationship_tokens(case):
        privacy = _PRIVACY_BY_TOKEN.get(token)
        if privacy and privacy not in declared:
            declared.append(privacy)
    return {
        "declared_privacy_classes": declared,
        "privacy_class_present": bool(declared),
        "inferred": False,
    }


def _has_any(spaces: List[Dict[str, Any]], identity: str) -> bool:
    return any(space.get("space_identity") == identity for space in spaces)


def _has_class(spaces: List[Dict[str, Any]], klass: str) -> bool:
    return any(
        (space.get("space_classes") or {}).get(klass) for space in spaces
    )


def _relationship_evidence(
    spaces: List[Dict[str, Any]],
    vocabulary: Dict[str, Any],
    relationship_type: str,
    involved: List[str],
) -> List[str]:
    """Assemble the evidence basis for one relationship.

    Evidence is drawn only from what is genuinely available: the identified
    space identities and the knowledge-context vocabulary that names the
    relationship. Nothing else is invented.
    """
    evidence: List[str] = []
    for identity in involved:
        if identity:
            evidence.append(identity)
    if _vocabulary_has(vocabulary, relationship_type):
        evidence.append(relationship_type)
    return _unique(evidence)


def _semantic_relationships(
    case: Dict[str, Any],
    spaces: List[Dict[str, Any]],
    vocabulary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Identify semantic relationships supported by the declared spaces.

    Each relationship is emitted ONLY when the identified spaces genuinely
    support it. Nothing is manufactured to fill the list.
    """
    relationships: List[Dict[str, Any]] = []
    tokens = _declared_relationship_tokens(case)
    privacy = _privacy_context(case)

    def add(
        relationship_type: str,
        involved: List[str],
        status: str = "identified",
    ) -> None:
        if not any(item.get("relationship_type") == relationship_type for item in relationships):
            relationships.append(
                {
                    "relationship_type": relationship_type,
                    "involved_spaces": _unique([i for i in involved if i]),
                    "status": status,
                    "evidence_reference": _relationship_evidence(
                        spaces, vocabulary, relationship_type, involved
                    ),
                    "uncertainty": {},
                }
            )

    has_sleeping = _has_any(spaces, "private_sleeping_space")
    has_sanitary = _has_any(spaces, "sanitary_service_space")
    has_storage = _has_any(spaces, "storage_space")
    has_circulation = _has_any(spaces, "circulation_space")
    has_service = _has_any(spaces, "service_space")
    has_public = _has_any(spaces, "public_living_space")
    has_entrance = _has_any(spaces, "entrance_transition_space")
    has_outdoor = _has_any(spaces, "outdoor_connection_space")

    if has_sleeping and (has_sanitary or has_storage or has_circulation):
        add(
            "private_sleeping_zone_containment",
            ["private_sleeping_space"],
        )
    if has_sleeping and has_sanitary:
        add(
            "sleeping_space_with_sanitary_association",
            ["private_sleeping_space", "sanitary_service_space"],
        )
    if has_sleeping and has_storage:
        add(
            "sleeping_space_with_storage_association",
            ["private_sleeping_space", "storage_space"],
        )
    if has_service and (has_public or has_sleeping):
        add(
            "functional_service_association",
            ["service_space", "public_living_space" if has_public else "private_sleeping_space"],
        )
    if has_public and has_circulation:
        add(
            "public_circulation_association",
            ["public_living_space", "circulation_space"],
        )
    if has_circulation and (has_sleeping or has_service):
        add(
            "circulation_connection_association",
            ["circulation_space", "private_sleeping_space" if has_sleeping else "service_space"],
        )
    if has_entrance and (has_public or has_circulation):
        add(
            "entrance_threshold_relationship",
            ["entrance_transition_space", "public_living_space" if has_public else "circulation_space"],
        )
    if has_outdoor and (has_public or has_sleeping):
        add(
            "outdoor_connection_association",
            ["outdoor_connection_space", "public_living_space" if has_public else "private_sleeping_space"],
        )

    # Privacy separation is reported ONLY when the case itself declares more
    # than one privacy class. It is never inferred from space identity.
    classes = privacy.get("declared_privacy_classes") or []
    if len(classes) > 1:
        add(
            "privacy_separation_relationship",
            ["private_sleeping_space" if has_sleeping else "private_space"],
            status="identified",
        )

    # Any explicit relationship the human named that resolves to a declared
    # relationship type is carried forward as an observation — this is the
    # evidence that learned knowledge was REUSED rather than rederived.
    normalised_relationship_tokens = {
        _normalise(relationship_type): relationship_type
        for relationship_type in _RELATIONSHIP_TYPES
    }
    for token in tokens:
        match = normalised_relationship_tokens.get(_normalise(token))
        if match and not any(
            item.get("relationship_type") == match for item in relationships
        ):
            relationships.append(
                {
                    "relationship_type": match,
                    "involved_spaces": [],
                    "status": "identified",
                    "evidence_reference": _relationship_evidence(
                        spaces, vocabulary, match, []
                    ),
                    "uncertainty": {},
                }
            )

    return relationships


def _concepts_used(
    spaces: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    vocabulary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Which KNOWN concepts were actually put to work for this case.

    A concept counts as used only when the knowledge context declares it AND
    the case genuinely exercises it. New concepts are never claimed.
    """
    used: List[Dict[str, Any]] = []
    candidate_labels: List[str] = []
    candidate_labels.extend(
        space.get("space_identity") for space in spaces
    )
    candidate_labels.extend(
        item.get("relationship_type") for item in relationships
    )
    for label in candidate_labels:
        if not label:
            continue
        declared = _vocabulary_has(vocabulary, label)
        entry = {
            "concept": label,
            "declared_by_knowledge_context": declared,
            "status": "reused" if declared else "used_without_declaration",
            "evidence_reference": [],
        }
        if not any(item.get("concept") == label for item in used):
            used.append(entry)
    return used


def _open_questions(
    case: Dict[str, Any],
    spaces: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    unknown_tokens: List[str],
    vocabulary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Questions a human could ask to close the understanding gap.

    These are PROMPTS for a human. They assert nothing and request no action.
    """
    questions: List[Dict[str, Any]] = []

    for token in unknown_tokens:
        questions.append(
            {
                "question_type": "unknown_concept_probe",
                "target": token,
                "question": (
                    "The term '" + token + "' does not resolve against the "
                    "known architectural vocabulary. Can you describe what "
                    "architectural meaning it carries in this case?"
                ),
                "rationale": "token_outside_declared_vocabulary",
            }
        )

    if _has_class(spaces, "private") and not any(
        item.get("relationship_type") == "privacy_separation_relationship"
        for item in relationships
    ):
        questions.append(
            {
                "question_type": "privacy_relationship_probe",
                "target": "privacy_separation_relationship",
                "question": (
                    "This case involves private space, but no separation "
                    "between private and shared space is declared. Is such a "
                    "separation part of the problem, or is privacy expressed "
                    "another way here?"
                ),
                "rationale": "privacy_separation_not_declared",
            }
        )

    if not spaces:
        questions.append(
            {
                "question_type": "problem_statement_probe",
                "target": None,
                "question": (
                    "No recognised space was named in this case. Can you state "
                    "which spaces the problem involves using established terms?"
                ),
                "rationale": "no_recognised_space_declared",
            }
        )

    if not relationships and spaces:
        questions.append(
            {
                "question_type": "relationship_probe",
                "target": None,
                "question": (
                    "The spaces are identified, but no semantic relationship "
                    "between them is supported by the case. Can you describe "
                    "how they relate architecturally?"
                ),
                "rationale": "no_relationship_supported_by_case",
            }
        )

    if unknown_tokens or questions:
        questions.append(
            {
                "question_type": "human_confirmation_probe",
                "target": None,
                "question": (
                    "Is this reading of the problem consistent with the "
                    "architectural intent you have in mind?"
                ),
                "rationale": "human_confirmation_requested",
            }
        )

    return questions


# --------------------------------------------------------------------------- #
# Public function
# --------------------------------------------------------------------------- #
def validate_architectural_design_understanding_v1(
    architectural_case: Dict[str, Any],
    knowledge_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate whether a NEW architectural problem can be understood using
    knowledge ArchitectOS has ALREADY learned.

    Pure function. Deterministic. Reads nothing, writes nothing, learns
    nothing, draws nothing.
    """
    case = _validate_architectural_case(architectural_case)
    context = _validate_knowledge_context(knowledge_context)

    vocabulary = _declared_vocabulary(context)
    spaces = _identified_spaces(case)
    relationships = _semantic_relationships(case, spaces, vocabulary)
    concepts_used = _concepts_used(spaces, relationships, vocabulary)
    privacy = _privacy_context(case)

    # A token counts as KNOWN when it either appears in a declared key directly
    # or was consumed as part of a successfully matched multi-word key. Without
    # this second clause, `master` and `room` would be reported as unknown even
    # though `master_bedroom` resolved cleanly — a misleading unknown.
    known_tokens = set(_tokenize(" ".join(_SPACE_IDENTITY)))
    known_tokens.update(_tokenize(" ".join(_PRIVACY_BY_TOKEN)))
    for space in spaces:
        known_tokens.update(_tokenize(space.get("declared_token")))
    for relationship_type in _RELATIONSHIP_TYPES:
        known_tokens.update(_tokenize(relationship_type))
    unknown_tokens = _unique(
        token
        for token in _case_space_tokens(case)
        if token not in known_tokens
        and token not in {"with", "and", "the", "a", "an", "of", "for", "to"}
    )

    problem_understanding = {
        "understood": bool(spaces) and bool(relationships),
        "identified_space_count": len(spaces),
        "identified_relationship_count": len(relationships),
        "unknown_token_count": len(unknown_tokens),
        "knowledge_context_areas": {
            "space_identity": vocabulary.get("declares_space_identity"),
            "functional_relationship": vocabulary.get(
                "declares_functional_relationship"
            ),
            "semantic_zone": vocabulary.get("declares_semantic_zone"),
        },
    }

    reasoning_basis = {
        "case_reference": {
            "contract": case.get("contract"),
            "version": case.get("version"),
            "case_id": case.get("case_id"),
        },
        "knowledge_reference": {
            "contract": context.get("contract"),
            "version": context.get("version"),
            "knowledge_domain": context.get("knowledge_domain"),
        },
        "declared_vocabulary": {
            "concept_count": len(vocabulary.get("concepts") or []),
            "pattern_count": len(vocabulary.get("patterns") or []),
            "semantic_areas": deepcopy(vocabulary.get("semantic_areas") or []),
        },
        # The case narrative itself is NOT copied forward. It is human prose,
        # not structural data.
        "restatement_of_problem": None,
    }

    uncertainty = {
        "unknown_tokens": unknown_tokens,
        "privacy_context": privacy,
        "unresolved_relationships": [
            item.get("relationship_type")
            for item in relationships
            if item.get("status") != "identified"
        ],
        "understood": bool(spaces) and bool(relationships),
        "reasoned": False,
        "generated": False,
    }

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "problem_understanding": problem_understanding,
        "identified_spaces": spaces,
        "semantic_relationships": relationships,
        "architectural_concepts_used": concepts_used,
        "reasoning_basis": reasoning_basis,
        "uncertainty": uncertainty,
        "open_questions": _open_questions(
            case, spaces, relationships, unknown_tokens, vocabulary
        ),
        # This boundary validates SEMANTIC UNDERSTANDING only. It never asks
        # for, produces, or stores a visual artefact.
        "visual_validation_request": None,
        "non_claims": deepcopy(_REQUIRED_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }
    _assert_no_forbidden_language(result)
    return result


def _assert_no_forbidden_language(result: Dict[str, Any]) -> None:
    """Refuse to emit rule-like, physical, or drawing-system vocabulary.

    Only the payload this boundary authored is scanned. ``non_claims`` is
    excluded because its keys legitimately contain the forbidden terms as
    negations (``not_design_solution``, ``not_recommendation``).

    Matching is on WORD BOUNDARIES. A substring scan would produce false
    positives on legitimate domain vocabulary (``outdoor`` contains
    ``door``; ``must`` appears inside ``mustard``). Word-boundary matching
    keeps the check honest without muting it.
    """
    authored = {
        "problem_understanding": result.get("problem_understanding"),
        "identified_spaces": result.get("identified_spaces"),
        "semantic_relationships": result.get("semantic_relationships"),
        "architectural_concepts_used": result.get("architectural_concepts_used"),
        "reasoning_basis": result.get("reasoning_basis"),
        "uncertainty": result.get("uncertainty"),
        "open_questions": result.get("open_questions"),
    }
    serialized = str(authored).lower()
    for term in _FORBIDDEN_TERMS:
        if re.search(r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])", serialized):
            raise AssertionError(
                "ArchitecturalDesignUnderstandingValidationV1 emitted "
                "forbidden term: " + term
            )
