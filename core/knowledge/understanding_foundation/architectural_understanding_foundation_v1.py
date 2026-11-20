"""Bounded ArchitecturalUnderstandingFoundationV1 extraction boundary.

This module implements the ARCHITECTURAL UNDERSTANDING FOUNDATION stage. It
answers exactly one question:

    "What ARCHITECTURAL MEANING does this human-taught example carry?"

It deliberately does NOT answer:

    "What shape / drawing / plan does this example imply?"

────────────────────────────────────────────────────────────────────────────
WHAT THIS BOUNDARY IS
────────────────────────────────────────────────────────────────────────────

A human supplies a TEACHING EXAMPLE — an observed architectural situation and
the human's own explanation of what it means. The boundary:

    1. validates the example against a strict, named contract;
    2. detects the OBSERVABLE ELEMENTS the human actually described;
    3. reads the SPATIAL RELATIONS the human actually asserted;
    4. extracts the CONCEPT behind the example, but ONLY where the human's
       explanation provides conceptual evidence;
    5. keeps the human's REASON and CONTEXT for the concept, so the meaning is
       never detached from why it was claimed;
    6. preserves UNCERTAINTY, alternative interpretations and context
       dependencies.

Concept extraction is therefore EVIDENCE-GATED, not word-gated. An example
that merely names the physical pieces of a master bedroom — bedroom, bathroom,
closet — does NOT yield the concept of privacy. The concept requires the human
to have said something about what those pieces MEAN: retreat, separation from
shared activity, control over one's own territory.

────────────────────────────────────────────────────────────────────────────
WHAT THIS BOUNDARY MUST NOT DO
────────────────────────────────────────────────────────────────────────────

    - build fixed rules
    - produce design formulas
    - present definitive patterns
    - claim there is always one correct way

Consequently this module never emits a rule, a preference, a ranking or a
"solution". Every concept it reports is framed as an INTERPRETATION supported
by human evidence, carries `alternative_interpretations` and `context_
dependencies`, and defaults to `open`.

────────────────────────────────────────────────────────────────────────────
FORBIDDEN INPUT (rejected, not coerced)
────────────────────────────────────────────────────────────────────────────

    raw images · Vision output · geometry · CAD · DWG · DXF · BIM · IFC ·
    rendering output · Memory objects · design solutions · layout intents ·
    unrelated intent / reasoning contracts

────────────────────────────────────────────────────────────────────────────
FORBIDDEN BEHAVIOUR
────────────────────────────────────────────────────────────────────────────

    - generating geometry, layouts or spatial placement
    - producing a design solution or recommendation
    - creating architectural rules or standards
    - learning permanently, or writing to Memory
    - persisting anything
    - bypassing, merging or replacing any existing contract boundary
    - silently resolving a conceptual conflict

This boundary is transient, read-only and deterministic.
"""

from __future__ import annotations

import re

from copy import deepcopy
from typing import Any, Dict, Iterable, List


CONTRACT = "ArchitecturalUnderstandingFoundationV1"
VERSION = "1.0"

# The human-taught example this boundary accepts.
TEACHING_EXAMPLE_CONTRACT = "ArchitecturalHumanTeachingExampleV1"
TEACHING_EXAMPLE_VERSION = "1.0"

# Interpretation status vocabulary. A concept is never reported as settled.
INTERPRETATION_STATUSES = (
    "supported",
    "weakly_supported",
    "unresolved",
)

# Contracts that must never be accepted in place of the declared example.
_FORBIDDEN_CONTRACTS = (
    # vision / observation
    "ArchitecturalUnderstandingV2",
    "ArchitecturalUnderstandingV1",
    "ArchitecturalObservationV1",
    "VisionObservationV1",
    "ArchitecturalVisionReportV1",
    "ImageIntentV1",
    "SiteIntentV1",
    # geometry / drawing / modelling / rendering
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
    # downstream design artefacts
    "ArchitecturalDesignReasoningInputV1",
    "ArchitecturalDesignReasoningResultV1",
    "ArchitecturalSpatialReasoningCandidateV1",
    "ArchitecturalDesignReasoningContextV1",
    # other knowledge lineages (this boundary must not act as their adapter)
    "ArchitecturalKnowledgeCurriculumV1",
    "ArchitecturalFoundationKnowledgeSetV1",
    "ArchitecturalFoundationKnowledgeAccessV1",
    "ArchitecturalConceptUnderstandingV1",
    "ArchitecturalConceptRelationshipV1",
    "ArchitecturalConceptOntologyV1",
    "ArchitecturalSemanticGraphV1",
    "ArchitecturalTeachingCaseV1",
    "ArchitecturalKnowledgeTeachingValidationV1",
    "ArchitecturalDesignUnderstandingValidationV1",
)

_REQUIRED_NON_CLAIMS = {
    "not_design_rule": True,
    "not_recommendation": True,
    "not_authoritative_knowledge": True,
    "not_memory": True,
    "not_learned_model": True,
    "not_design_solution": True,
    "not_fixed_truth": True,
    "not_single_correct_way": True,
}


# --------------------------------------------------------------------------- #
# STARTING SEMANTIC INDEX — NOT A SOURCE OF TRUTH.
#
# Nothing in this table is a rule, a required property, a mandatory
# arrangement, a dimension, or a universal truth. It is a STARTING INDEX that
# helps recognise concepts already encountered. It is deliberately incomplete
# and permanently extensible.
#
# A teaching case is NOT required to select from this index, and a concept
# here does NOT automatically apply to a case that happens to mention it.
# The authority for what a case means is the case itself: its architectural
# evidence, the human's reasoning, and the stated context.
#
# Each teaching case may therefore:
#   * INTRODUCE a concept absent from this index,
#   * ENRICH an indexed concept with new meaning, evidence, alternatives or
#     context dependencies,
#   * ADD EVIDENCE for an indexed concept,
#   * or declare an indexed concept NOT APPLICABLE in that context.
#
# For each indexed seed the table records:
#   seed_meaning     — a provisional gloss, openly provisional;
#   evidence_terms   — vocabulary that MIGHT indicate the meaning was
#                      communicated. A hint, never a test;
#   component_terms  — physical pieces loosely associated with the idea, used
#                      ONLY to notice when a case names pieces without
#                      explaining meaning;
#   seed_alternatives     — known other readings, deliberately non-exhaustive;
#   seed_dependencies     — known context the reading depends on.
#
# The `seed_` prefix is intentional: these are starting points contributed by
# a human, not findings about architecture.
# --------------------------------------------------------------------------- #
_CONCEPT_INDEX = {
    "privacy": {
        "seed_meaning": "The condition of being withdrawn from observation and from shared activity.",
        "evidence_terms": (
            "privacy",
            "private",
            "withdrawn",
            "not overlooked",
            "screened",
            "sheltered from",
            "away from others",
            "secluded",
            "concealed",
        ),
        "component_terms": ("bathroom", "toilet", "closet", "wardrobe"),
        "seed_alternatives": (
            "privacy expressed by depth and distance rather than by enclosure",
            "privacy expressed by sequence and control of approach",
        ),
        "seed_dependencies": (
            "cultural expectations of modesty",
            "household composition",
        ),
    },
    "personal_territory": {
        "seed_meaning": "A domain the occupant governs, where their own order and possessions hold.",
        "evidence_terms": (
            "territory",
            "personal",
            "own space",
            "belongs to",
            "governs",
            "control over",
            "domain",
            "mine",
        ),
        "component_terms": ("closet", "wardrobe", "storage", "shelf"),
        "seed_alternatives": (
            "territory marked by ownership of storage rather than by boundary",
            "territory shared between two occupants and negotiated",
        ),
        "seed_dependencies": ("number of occupants", "length of stay"),
    },
    "retreat": {
        "seed_meaning": "A place to withdraw to in order to recover, rest or be unobserved.",
        "evidence_terms": (
            "retreat",
            "withdraw",
            "recover",
            "unwind",
            "refuge",
            "escape",
            "reset",
        ),
        "component_terms": ("bedroom", "bed", "chair"),
        "seed_alternatives": (
            "retreat expressed outdoors rather than indoors",
            "retreat expressed as a view rather than as enclosure",
        ),
        "seed_dependencies": ("daily rhythm of the household",),
    },
    "separation_from_public_activity": {
        "seed_meaning": "Distinction between the domain of guests and shared life and the domain of the occupant.",
        "evidence_terms": (
            "separation",
            "separated",
            "away from guests",
            "distinct from",
            "segregated",
            "far from",
            "different from the public",
        ),
        "component_terms": ("corridor", "hall", "living_room", "living"),
        "seed_alternatives": (
            "separation achieved by level change rather than by distance",
            "separation achieved by a threshold rather than by a corridor",
        ),
        "seed_dependencies": (
            "whether guests are received in the home",
            "size of the dwelling",
        ),
    },
    "personal_control": {
        "seed_meaning": "The occupant decides what happens in the space, when, and to whom it is open.",
        "evidence_terms": (
            "control",
            "controls",
            "controlled",
            "decide",
            "decides",
            "choose",
            "chooses",
            "regulate",
            "regulates",
            "when to",
            "at will",
            "discretion",
        ),
        "component_terms": ("door", "opening", "curtain", "shutter"),
        "seed_alternatives": (
            "control exercised by scheduling rather than by a physical element",
            "control shared and negotiated with an occupant",
        ),
        "seed_dependencies": ("household hierarchy", "cultural norms of authority"),
    },
    "sleeping_rest_experience": {
        "seed_meaning": "The qualities of the experience of sleeping and resting in this place.",
        "evidence_terms": (
            "quiet",
            "calm",
            "restful",
            "sleep",
            "dark",
            "still",
            "undisturbed",
            "settled",
        ),
        "component_terms": ("bed", "mattress", "window"),
        "seed_alternatives": (
            "rest achieved by isolation from sound",
            "rest achieved by orientation to light and air",
        ),
        "seed_dependencies": ("noise sources nearby", "sleeping habits"),
    },
    "relation_to_intimate_functions": {
        "seed_meaning": "How washing, dressing and bodily care relate to the act of sleeping.",
        "evidence_terms": (
            "washing",
            "dressing",
            "bodily",
            "intimate",
            "adjoining",
            "next to the bed",
            "without leaving",
            "in sequence",
        ),
        "component_terms": ("bathroom", "toilet", "basin", "shower", "closet"),
        "seed_alternatives": (
            "intimate functions kept separate from the sleeping place",
            "intimate functions shared with the rest of the household",
        ),
        "seed_dependencies": (
            "whether the household shares sanitary facilities",
            "cultural attitudes to bodily privacy",
        ),
    },
    "movement_and_access": {
        "seed_meaning": "How the occupant arrives, moves through and leaves this place.",
        "evidence_terms": (
            "arrive",
            "arrival",
            "approach",
            "movement",
            "route",
            "reach",
            "access",
            "passage",
            "sequence",
        ),
        "component_terms": ("corridor", "hall", "door", "entrance", "stairs"),
        "seed_alternatives": (
            "arrival direct from shared space",
            "arrival after passing through an intermediate room",
        ),
        "seed_dependencies": ("position of the room within the dwelling",),
    },
    "contrast_with_public_space": {
        "seed_meaning": "The way this place is deliberately unlike the area of shared and guest life.",
        "evidence_terms": (
            "contrast",
            "unlike",
            "opposite of",
            "in contrast",
            "different from",
            "rather than the shared",
        ),
        "component_terms": ("living_room", "living", "guest"),
        "seed_alternatives": (
            "contrast expressed by material and light rather than by enclosure",
            "contrast expressed by scale rather than by location",
        ),
        "seed_dependencies": ("how the shared area is used",),
    },
}

# The CASE OPERATIONS a human teaching case may perform on the index.
# These are declared so the boundary can report, per concept, WHAT the case
# did — rather than assuming every mentioned concept simply "applies".
CASE_OPERATIONS = (
    "introduced",       # a concept absent from the index
    "enriched",         # an indexed concept given new meaning/evidence/context
    "evidence_added",   # extra evidence supplied for an indexed concept
    "not_applicable",   # the case shows the concept does not apply here
    "grounded",         # an indexed concept fully supported by the case
    "index_listed_only",# recognised from the index but NOT grounded by the case
    "component_mentioned_only",  # pieces named, no meaning explained
)

# Backwards-compatible alias. The name is retained so existing importers do not
# break, but the object is no longer authoritative and is referenced internally
# as the semantic index.
_DECLARED_CONCEPTS = _CONCEPT_INDEX

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
        "'",
        '"',
    ):
        text = text.replace(character, " ")
    return [token for token in text.split() if token]


def _normalise(value: Any) -> str:
    return " ".join(_tokenize(value))


def _contains_term(haystack: str, term: str) -> bool:
    """Word-boundary containment.

    A substring test would match ``must`` inside ``mustard`` and ``door``
    inside ``outdoor``. Word boundaries keep the check honest without
    muting it.
    """
    pattern = r"(?<![a-z0-9_])" + re.escape(term.lower()) + r"(?![a-z0-9_])"
    return re.search(pattern, haystack) is not None


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #
def _validate_example(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalUnderstandingFoundationV1 requires an "
            "ArchitecturalHumanTeachingExampleV1 dict"
        )
    contract = value.get("contract")
    if contract is None:
        raise ValueError(
            "ArchitecturalHumanTeachingExampleV1 is missing the required "
            "'contract' field"
        )
    if contract in _FORBIDDEN_CONTRACTS:
        raise ValueError(
            "ArchitecturalUnderstandingFoundationV1 rejects forbidden input "
            "contract: " + str(contract)
        )
    if contract != TEACHING_EXAMPLE_CONTRACT:
        raise ValueError(
            "ArchitecturalUnderstandingFoundationV1 accepts only "
            "ArchitecturalHumanTeachingExampleV1 (got: " + str(contract) + ")"
        )
    if value.get("version") != TEACHING_EXAMPLE_VERSION:
        raise ValueError(
            "ArchitecturalUnderstandingFoundationV1 requires teaching example "
            "version " + TEACHING_EXAMPLE_VERSION
        )
    return value


# --------------------------------------------------------------------------- #
# Reading the human example
# --------------------------------------------------------------------------- #
def _observation_text(example: Dict[str, Any]) -> str:
    """The observable part of the example: what the human SAW.

    Only declared observation fields are read. No images, no measurements.
    """
    parts: List[str] = []
    for key in (
        "observation",
        "observed_elements",
        "description",
        "what_is_present",
    ):
        value = example.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
    return " ".join(parts)


def _explanation_text(example: Dict[str, Any]) -> str:
    """The meaning-bearing part of the example: what the human SAYS it means.

    This is the ONLY source of conceptual evidence. Observation alone can
    never establish a concept.
    """
    parts: List[str] = []
    for key in (
        "human_explanation",
        "meaning",
        "why",
        "reason",
        "context",
        "user_experience",
        "spatial_logic",
    ):
        value = example.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
    return " ".join(parts)


def _all_text(example: Dict[str, Any]) -> str:
    return (_observation_text(example) + " " + _explanation_text(example)).lower()


def _observed_elements(example: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect the observable elements the human actually described.

    An element is reported only when the human named it. Nothing is detected
    from imagery, because no imagery is accepted.
    """
    observed: List[Dict[str, Any]] = []
    seen: List[str] = []
    text = _observation_text(example).lower()

    for concept, definition in _DECLARED_CONCEPTS.items():
        for term in definition.get("component_terms", ()):
            if _contains_term(text, term) and term not in seen:
                seen.append(term)
                observed.append(
                    {
                        "element": term,
                        "associated_concept": concept,
                        "evidence_reference": term,
                        "status": "observed",
                    }
                )
    return observed


def _spatial_relations(example: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Read the spatial relations the human actually asserted.

    A relation is reported only when the human's OWN words assert it. The
    relation names meaning, never a position or a measurement.
    """
    text = _all_text(example)
    relations: List[Dict[str, Any]] = []

    relation_vocabulary = {
        "withdrawn_within": ("withdrawn", "within", "enclosed", "inside"),
        "separated_from": ("separated", "segregated", "distinct from"),
        "adjacent_to": ("adjacent", "next to", "beside", "adjoining"),
        "reached_through": ("reached through", "passing through", "via", "through"),
        "opens_toward": ("opens toward", "opening to", "facing"),
        "layered_by_distance": ("further", "deeper", "distance", "away from"),
    }
    relations_terms_read = _relation_terms(example)

    for relation, cues in relation_vocabulary.items():
        if any(_contains_term(text, cue) for cue in cues):
            relations.append(
                {
                    "relation": relation,
                    "asserted_by_human": True,
                    "evidence_reference": [
                        cue for cue in cues if _contains_term(text, cue)
                    ],
                    "uncertainty": {},
                }
            )

    # An explicitly declared relation list is honoured verbatim.
    for declared in relations_terms_read:
        if not any(item.get("relation") == declared for item in relations):
            relations.append(
                {
                    "relation": declared,
                    "asserted_by_human": True,
                    "evidence_reference": [declared],
                    "uncertainty": {},
                }
            )
    return relations


def _relation_terms(example: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    for key in ("stated_relations", "spatial_relations", "relations"):
        value = example.get(key)
        if isinstance(value, str):
            normalised = _normalise(value)
            if normalised:
                terms.append(normalised.replace(" ", "_"))
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str) and item.strip():
                    terms.append(_normalise(item).replace(" ", "_"))
    return _unique(terms)


# --------------------------------------------------------------------------- #
# Concept extraction — EVIDENCE-GATED
# --------------------------------------------------------------------------- #
def _conceptual_evidence(example: Dict[str, Any], terms: Iterable[str]) -> List[str]:
    """Return the human's own words that express this concept's MEANING."""
    text = _explanation_text(example).lower()
    return [term for term in terms if _contains_term(text, term)]


def _component_mention(example: Dict[str, Any], terms: Iterable[str]) -> List[str]:
    """Return physical pieces the human named WITHOUT explaining the meaning.

    This is the discriminator between understanding the concept and only
    listing its components.
    """
    text = _all_text(example)
    return [term for term in terms if _contains_term(text, term)]


def _case_concept_directives(example: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Per-concept operations the human explicitly performed in this case.

    The human may, for any concept:
      * introduce it    (`concepts_introduced`)
      * enrich it       (`concepts_enriched`)
      * add evidence    (`concepts_evidence`)
      * mark it         not applicable (`concepts_not_applicable`)

    Everything is keyed by the concept's normalised name so the four
    operations compose without the boundary inventing an ordering.
    """
    directives: Dict[str, Dict[str, Any]] = {}

    def slot(name: Any) -> Dict[str, Any]:
        key = _normalise(name).replace(" ", "_")
        return directives.setdefault(
            key,
            {
                "concept": key,
                "raw_name": name if isinstance(name, str) else key,
                "meaning": None,
                "meaning_kind": None,
                "evidence": [],
                "alternatives": [],
                "dependencies": [],
                "reason": None,
                "context": None,
                "not_applicable": False,
                "introduced": False,
                "enriched": False,
                "evidence_added": False,
            },
        )

    def entries(value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]

    def absorb(item: Any) -> None:
        if isinstance(item, str):
            if item.strip():
                entry = slot(item)
                entry["introduced"] = True
            return
        if not isinstance(item, dict):
            return
        name = item.get("concept") or item.get("name") or item.get("concept_name")
        if not isinstance(name, str) or not name.strip():
            return
        entry = slot(name)
        # Distinguish a REPLACEMENT meaning from an EXTENSION of the indexed
        # meaning. The origin reported downstream must reflect what the human
        # actually did, not silently collapse both into "the case provided it".
        supplied_meaning = item.get("meaning") or item.get("definition")
        supplied_extension = item.get(
            "meaning_extension"
        ) or item.get("meaning_extended") or item.get("extends_meaning")
        if supplied_meaning:
            entry["meaning"] = supplied_meaning
            entry["meaning_kind"] = "replacement"
            entry["enriched"] = True
        elif supplied_extension:
            entry["meaning"] = supplied_extension
            entry["meaning_kind"] = "extension"
            entry["enriched"] = True
        entry["evidence"].extend(
            str(v)
            for v in _list(item.get("evidence") or item.get("evidence_reference"))
            if str(v or "").strip()
        )
        entry["alternatives"].extend(
            str(v)
            for v in _list(item.get("alternatives") or item.get("alternative_interpretations"))
            if str(v or "").strip()
        )
        entry["dependencies"].extend(
            str(v)
            for v in _list(item.get("dependencies") or item.get("context_dependencies"))
            if str(v or "").strip()
        )
        if isinstance(item.get("reason"), str):
            entry["reason"] = item["reason"]
        if isinstance(item.get("context"), str):
            entry["context"] = item["context"]
        if entry["evidence"] or entry["alternatives"] or entry["dependencies"]:
            if entry["meaning"] is None:
                entry["evidence_added"] = True

    for key in ("additional_concepts", "new_concepts", "taught_concepts", "concepts_introduced"):
        for item in entries(example.get(key)):
            absorb(item)

    def item_name(item: Any) -> str | None:
        """Resolve the concept name from any declared item shape.

        Accepts a bare string or a mapping using ``concept``, ``name`` or
        ``concept_name``. Returns ``None`` when no usable name is present.
        """
        if isinstance(item, str):
            return item.strip() or None
        if isinstance(item, dict):
            name = (
                item.get("concept")
                or item.get("name")
                or item.get("concept_name")
            )
            if isinstance(name, str) and name.strip():
                return name.strip()
        return None

    for key in ("concepts_enriched", "concept_enrichments", "concepts_extended"):
        for item in entries(example.get(key)):
            absorb(item)
            name = item_name(item)
            if name:
                slot(name)["enriched"] = True

    for key in ("concepts_evidence", "concept_evidence", "evidence_for_concepts"):
        for item in entries(example.get(key)):
            absorb(item)
            name = item_name(item)
            if name:
                slot(name)["evidence_added"] = True

    for key in ("concepts_not_applicable", "not_applicable_concepts", "concepts_absent"):
        for item in entries(example.get(key)):
            if isinstance(item, str) and item.strip():
                entry = slot(item)
                entry["not_applicable"] = True
                entry["not_applicable_reason"] = None
            elif isinstance(item, dict):
                name = item.get("concept") or item.get("name")
                if isinstance(name, str) and name.strip():
                    entry = slot(name)
                    entry["not_applicable"] = True
                    entry["not_applicable_reason"] = (
                        item.get("reason") or item.get("why")
                    )

    return directives


def _extract_concepts(example: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract the concepts this case actually carries.

    IMPORTANT: this is NOT a selection from the index. The index is consulted
    only to RECOGNISE a concept already encountered; authority for what the
    case means rests with the case — its architectural evidence, the human's
    reasoning, and the stated context.

    A concept appears in the output only if the case GROUNDS it: either the
    human's explanation supplies meaning evidence, or the human explicitly
    performed one of the four case operations. A concept merely listed by the
    index but never grounded is reported as `index_listed_only` and is
    explicitly NOT counted as understood.
    """
    concepts: List[Dict[str, Any]] = []
    directives = _case_concept_directives(example)

    def build(
        name: str,
        seed: Dict[str, Any] | None,
        directive: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        directive = directive or {}
        evidence = (
            _conceptual_evidence(example, (seed or {}).get("evidence_terms", ()))
            if seed
            else []
        )
        components = (
            _component_mention(example, (seed or {}).get("component_terms", ()))
            if seed
            else []
        )
        case_evidence = [str(v) for v in directive.get("evidence") or []]
        evidence = _unique(evidence + case_evidence)

        # --- decide what this case DID with the concept ---------------------
        #
        # A concept ABSENT from the index that the case supplies anything at
        # all about (a name, a meaning, evidence, a reason) was INTRODUCED by
        # this case. That is the strongest grounding available — it is the
        # human's own concept, not a selection from the index.
        #
        # A concept the case marks NOT APPLICABLE is never treated as
        # introduced: the case is explicitly declining to carry it, so it must
        # not be re-anchored as something the case brought in.
        case_introduced = seed is None and not directive.get("not_applicable") and bool(
            directive.get("introduced")
            or directive.get("meaning")
            or directive.get("evidence")
            or directive.get("reason")
            or directive.get("context")
        )

        if directive.get("not_applicable"):
            status = "not_applicable"
        elif case_introduced:
            status = "introduced"
        elif directive.get("enriched"):
            status = "enriched"
        elif directive.get("evidence_added"):
            status = "evidence_added"
        elif evidence:
            status = "grounded"
        elif components:
            status = "component_mentioned_only"
        else:
            status = "index_listed_only"

        # A concept the case performed NO operation on AND that supplies no
        # meaning evidence is not carried at all — it is only an index entry.
        if status == "index_listed_only" and not directive.get("raw_name"):
            return {}

        # --- meaning: the case may override or extend the seed --------------
        seed_meaning = (seed or {}).get("seed_meaning")
        case_meaning = directive.get("meaning")
        meaning_kind = directive.get("meaning_kind")
        if case_meaning and meaning_kind == "extension" and seed_meaning:
            # The human extended the indexed meaning rather than replacing it.
            meaning = case_meaning
            meaning_origin = "case_extended"
        elif case_meaning and seed_meaning and case_meaning != seed_meaning:
            meaning = case_meaning
            meaning_origin = "case_extended"
        elif case_meaning:
            meaning = case_meaning
            meaning_origin = "case_provided"
        elif seed_meaning and status != "introduced":
            meaning = seed_meaning
            meaning_origin = "index_seed"
        else:
            meaning = None
            meaning_origin = "not_stated"

        alternatives = _unique(
            _list((seed or {}).get("seed_alternatives"))
            + [str(v) for v in directive.get("alternatives") or []]
        )
        dependencies = _unique(
            _list((seed or {}).get("seed_dependencies"))
            + [str(v) for v in directive.get("dependencies") or []]
        )

        grounded = status in ("grounded", "enriched", "evidence_added", "introduced")

        if seed is not None:
            anchor = "semantic_index"
        elif status == "not_applicable":
            # The case named this concept only to set it aside. It was neither
            # introduced nor grounded, so it gets its own truthful anchor.
            anchor = "case_excluded"
        else:
            anchor = "case_introduced"

        return {
            "concept": name,
            "meaning": meaning,
            "meaning_origin": meaning_origin,
            "anchor": anchor,
            "case_operation": status,
            "extraction_status": (
                "supported"
                if grounded
                else "not_applicable"
                if status == "not_applicable"
                else "component_mentioned_only"
                if status == "component_mentioned_only"
                else "index_listed_only"
            ),
            "grounded_in_case": grounded,
            "evidence_reference": evidence,
            "component_mention": components,
            "interpretation_status": (
                "supported"
                if grounded
                else "closed_for_this_context"
                if status == "not_applicable"
                else "open"
            ),
            "not_applicable_in_this_context": status == "not_applicable",
            "not_applicable_reason": directive.get("not_applicable_reason"),
            "reason_and_context": _reason_and_context(
                example, name, directive
            ),
            "alternative_interpretations": alternatives,
            "context_dependencies": dependencies,
            "uncertainty": {
                "evidence_present": bool(evidence),
                "components_only": status == "component_mentioned_only",
                "grounded_in_case": grounded,
                "resolved": False,
            },
        }

    # 1. Index-recognised concepts the case did something with.
    for name, seed in _CONCEPT_INDEX.items():
        directive = directives.get(name)
        item = build(name, seed, directive)
        if item:
            concepts.append(item)

    # 2. Operations on concepts the index does not contain.
    for name, directive in directives.items():
        if name in _CONCEPT_INDEX:
            continue
        item = build(name, None, directive)
        if item:
            concepts.append(item)

    return concepts


def _reason_and_context(
    example: Dict[str, Any],
    concept: str,
    directive: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Keep the human's reason and context for this concept.

    Meaning must never be detached from why the human claimed it. A per-concept
    reason supplied inside a case operation takes precedence over the
    example-level reason.
    """
    directive = directive or {}
    example_reason = example.get("reason") or example.get("why")
    example_context = example.get("context")
    if isinstance(example_reason, dict):
        example_reason = example_reason.get(concept) or example_reason.get("default")
    if isinstance(example_context, dict):
        example_context = example_context.get(concept) or example_context.get("default")

    reason = directive.get("reason") or example_reason
    context = directive.get("context") or example_context
    return {
        "reason": reason if isinstance(reason, str) and reason.strip() else None,
        "context": context if isinstance(context, str) and context.strip() else None,
        "reason_present": bool(isinstance(reason, str) and reason.strip()),
        "context_present": bool(isinstance(context, str) and context.strip()),
    }


# --------------------------------------------------------------------------- #
# Public function
# --------------------------------------------------------------------------- #
def understand_architectural_example_v1(
    teaching_example: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract architectural meaning from a human-taught example.

    Pure function. Deterministic. Reads nothing, writes nothing, learns
    nothing, draws nothing.

    The returned contracts are INTERPRETATIONS supported by human evidence.
    They are never rules and never a single correct answer.
    """
    example = _validate_example(teaching_example)

    elements = _observed_elements(example)
    relations = _spatial_relations(example)
    concepts = _extract_concepts(example)

    grounded = [c for c in concepts if c.get("grounded_in_case")]
    introduced = [
        c for c in concepts if c.get("case_operation") == "introduced"
    ]
    enriched = [c for c in concepts if c.get("case_operation") == "enriched"]
    evidence_added = [
        c for c in concepts if c.get("case_operation") == "evidence_added"
    ]
    not_applicable = [
        c for c in concepts if c.get("case_operation") == "not_applicable"
    ]
    components_only = [
        c for c in concepts if c.get("case_operation") == "component_mentioned_only"
    ]
    index_only = [
        c for c in concepts if c.get("case_operation") == "index_listed_only"
    ]

    def case_operation_summary(name: str) -> List[str]:
        return [c["concept"] for c in concepts if c.get("case_operation") == name]

    concept_understanding = {
        "teaching_topic": example.get("teaching_topic"),
        "extracted_concepts": concepts,
        "concept_count": len(concepts),
        "supported_concept_count": len(grounded),
        "component_only_concept_count": len(components_only),
        "meaning_extracted": bool(grounded),
        "components_alone_do_not_establish_meaning": bool(grounded)
        or bool(components_only),
        # The index is a semantic starting point, never the source of truth.
        "index_role": "starting_semantic_index",
        "index_is_source_of_truth": False,
        "index_is_rule_set": False,
        "index_entry_count": len(_CONCEPT_INDEX),
        "grounded_in_case_count": len(grounded),
        "index_listed_only_count": len(index_only),
        "case_operations": {
            "introduced": case_operation_summary("introduced"),
            "enriched": case_operation_summary("enriched"),
            "evidence_added": case_operation_summary("evidence_added"),
            "not_applicable": case_operation_summary("not_applicable"),
            "grounded_in_case": case_operation_summary("grounded"),
        },
    }

    uncertainty = {
        # A concept whose pieces were named but whose meaning was never
        # explained is reported as UNRESOLVED, not silently filled in.
        "concepts_without_meaning_evidence": [
            c["concept"] for c in components_only
        ],
        # Concepts the index knows but the case did not ground. They are NOT
        # understood for this case, and they are NOT properties of it.
        "concepts_index_listed_but_not_grounded": [
            c["concept"] for c in index_only
        ],
        "concepts_not_applicable_in_this_context": [
            c["concept"] for c in not_applicable
        ],
        "concepts_introduced_by_case": [c["concept"] for c in introduced],
        "concepts_enriched_by_case": [c["concept"] for c in enriched],
        "evidence_added_by_case": [c["concept"] for c in evidence_added],
        "alternative_interpretations_preserved": True,
        "context_dependencies_preserved": True,
        "multiple_valid_solutions_possible": True,
        "human_uncertainty": deepcopy(example.get("uncertainty") or {}),
        "single_correct_interpretation": False,
        "resolved": False,
        "learned": False,
    }

    rationale_basis = {
        "example_reference": {
            "contract": example.get("contract"),
            "version": example.get("version"),
            "example_id": example.get("example_id"),
        },
        "observation_present": bool(_observation_text(example).strip()),
        "explanation_present": bool(_explanation_text(example).strip()),
        # The authority for meaning is the case itself.
        "grounding_authority": "human_teaching_case",
        "index_consulted_for": "recognition_only",
        # The human narrative itself is NOT copied forward. It is human prose,
        # not structural data. What is carried is the evidence TERMS and the
        # human's own reason/context where supplied.
        "restatement_of_explanation": None,
    }

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "concept_understanding": concept_understanding,
        "observed_elements": elements,
        "spatial_relations": relations,
        "concept_rationale_and_context": [
            {
                "concept": c["concept"],
                "reason_and_context": deepcopy(c["reason_and_context"]),
            }
            for c in concepts
        ],
        "uncertainty": uncertainty,
        "rationale_basis": rationale_basis,
        "non_claims": deepcopy(_REQUIRED_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }
    _assert_no_forbidden_language(result)
    return result


def _assert_no_forbidden_language(result: Dict[str, Any]) -> None:
    """Refuse to emit rule-like, physical or drawing-system vocabulary.

    Only the payload this boundary authored is scanned. ``non_claims`` is
    excluded because its keys legitimately contain the forbidden terms as
    negations.
    """
    authored = {
        "concept_understanding": result.get("concept_understanding"),
        "observed_elements": result.get("observed_elements"),
        "spatial_relations": result.get("spatial_relations"),
        "concept_rationale_and_context": result.get("concept_rationale_and_context"),
        "uncertainty": result.get("uncertainty"),
    }
    serialized = str(authored).lower()
    for term in _FORBIDDEN_TERMS:
        if _contains_term(serialized, term):
            raise AssertionError(
                "ArchitecturalUnderstandingFoundationV1 emitted forbidden "
                "term: " + term
            )
