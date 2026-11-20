"""Bounded ArchitecturalUnderstandingValidationV1 boundary.

This module implements the ARCHITECTURAL CONCEPT-UNDERSTANDING VALIDATION
stage. It answers exactly one question:

    "Did ArchitectOS UNDERSTAND the architectural concept behind this new
     space — or did it only match the words?"

It deliberately does NOT answer:

    "What should this space look like?"

────────────────────────────────────────────────────────────────────────────
WHAT THIS BOUNDARY IS
────────────────────────────────────────────────────────────────────────────

A human supplies:

    understood_concepts  — the concepts extracted by the understanding
                           foundation boundary, each with the EVIDENCE that
                           supported it.
    new_space            — a NEW architectural situation to analyse.

The boundary:

    1. validates both inputs against strict, named contracts;
    2. reads the new space as declared architectural signals;
    3. for each known concept, looks for ARCHITECTURAL EVIDENCE in the new
       space — reasoning about meaning, not string overlap;
    4. issues a verdict of `understood`, `word_matching_only`, or
       `not_addressed`;
    5. reports what it did NOT understand, and asks the human to explain.

────────────────────────────────────────────────────────────────────────────
THE CENTRAL DISCRIMINATION
────────────────────────────────────────────────────────────────────────────

`word_matching_only` is the verdict this stage exists to produce.

An analysis that merely finds the word "private" in a description has NOT
understood the concept of privacy. Understanding requires the new space to
present evidence of the MEANING: a spatial, experiential or contextual reason
for the condition — not merely a label naming it.

Therefore:
    naming the label alone                  -> word_matching_only  (NOT understood)
    label + architectural reasoning         -> understood
    insufficient material to evaluate       -> not_addressed

`not_addressed` is deliberately not a failure verdict. It means exactly one
thing: the teaching case did not provide enough information to evaluate that
concept. It explicitly does NOT mean failure, lack of understanding,
contradiction, or absence of the concept. The concept may apply perfectly well;
this material simply does not say. Reporting it as anything stronger would
convert the concept index into a mandatory checklist, which this boundary must
never do.

Every verdict is established by ARCHITECTURAL EVIDENCE
(`architectural_evidence`), never by word overlap
(`vocabulary_matches`) alone.

────────────────────────────────────────────────────────────────────────────
WHAT THIS BOUNDARY MUST NOT DO
────────────────────────────────────────────────────────────────────────────

    - design anything
    - propose a plan (پلان)
    - build fixed rules or design formulas
    - present definitive patterns
    - claim there is always one correct way

The output is purely ANALYTICAL: it describes what was and was not understood.
It proposes no arrangement, no dimension and no solution.

────────────────────────────────────────────────────────────────────────────
FORBIDDEN INPUT (rejected, not coerced)
────────────────────────────────────────────────────────────────────────────

    raw images · Vision output · geometry · CAD · DWG · DXF · BIM · IFC ·
    rendering output · Memory objects · design solutions · layout intents ·
    unrelated intent / reasoning contracts

────────────────────────────────────────────────────────────────────────────
FORBIDDEN BEHAVIOUR
────────────────────────────────────────────────────────────────────────────

    - designing, proposing plans or arrangements
    - generating geometry or spatial placement
    - producing a design solution or recommendation
    - creating architectural rules or standards
    - learning permanently, or writing to Memory
    - persisting anything
    - bypassing, merging or replacing any existing contract boundary

This boundary is transient, read-only and deterministic.
"""

from __future__ import annotations

import re

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Tuple


CONTRACT = "ArchitecturalUnderstandingValidationV1"
VERSION = "1.0"

# The known concepts, as produced by the understanding foundation boundary.
UNDERSTOOD_CONCEPTS_CONTRACT = "ArchitecturalUnderstandingFoundationV1"
UNDERSTOOD_CONCEPTS_VERSION = "1.0"

# The new architectural situation to analyse.
NEW_SPACE_CONTRACT = "ArchitecturalNewSpaceV1"
NEW_SPACE_VERSION = "1.0"

# Verdict vocabulary. `word_matching_only` means NOT understood.
# `not_addressed` means the material gave INSUFFICIENT INFORMATION to evaluate
# the concept. It is NOT a failure, NOT a lack of understanding, and NOT a
# statement that the concept is absent.
VALIDATION_STATUSES = (
    "understood",
    "word_matching_only",
    "not_addressed",
)

ANALYSIS_METHOD = "architectural_evidence"

_CONTRADICTION_MARKERS = (
    "not",
    "no",
    "never",
    "without",
    "less",
    "fewer",
    "unlike",
    "rather than",
    "instead of",
)

_RELATION_CUES = (
    "within",
    "inside",
    "between",
    "through",
    "toward",
    "away",
    "beyond",
    "after",
    "before",
    "across",
    "along",
    "fronting",
    "facing",
    "beneath",
    "above",
    "around",
)

_QUALITY_CUES = (
    "quiet",
    "calm",
    "restful",
    "still",
    "dark",
    "bright",
    "soft",
    "hard",
    "warm",
    "cool",
    "undisturbed",
    "sheltered",
    "open",
    "enclosed",
    "narrow",
    "deep",
    "higher",
    "lower",
)

_EXPERIENCE_CUES = (
    "experience",
    "felt",
    "sense of",
    "feels",
    "arriving",
    "arrival",
    "greeted",
    "greeting",
    "welcome",
    "hesitation",
    "threshold",
    "transition",
    "journey",
    "procession",
    "dwell",
    "linger",
    "breathe",
    "gather",
    "gathering",
    "observe",
    "observed",
    "overlooked",
    "seen",
    "hidden",
    "concealed",
)

_ELEMENT_CUES = (
    "door",
    "wall",
    "opening",
    "threshold",
    "screen",
    "partition",
    "courtyard",
    "garden",
    "yard",
    "roof",
    "ceiling",
    "floor",
    "stair",
    "corridor",
    "passage",
    "window",
    "niche",
    "bench",
    "seat",
)

# Contracts that must never be accepted in place of the declared inputs.
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
    # downstream design artefacts (this boundary validates BEFORE them)
    "ArchitecturalDesignReasoningInputV1",
    "ArchitecturalDesignReasoningResultV1",
    "ArchitecturalSpatialReasoningCandidateV1",
    "ArchitecturalDesignReasoningContextV1",
    # other knowledge lineages
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
    "ArchitecturalHumanTeachingExampleV1",
)

_REQUIRED_NON_CLAIMS = {
    "not_design_rule": True,
    "not_recommendation": True,
    "not_authoritative_knowledge": True,
    "not_memory": True,
    "not_learned_model": True,
    "not_design_solution": True,
    "not_plan_proposal": True,
    "not_fixed_truth": True,
    "not_single_correct_way": True,
}

# --------------------------------------------------------------------------- #
# Architectural evidence vocabulary, per concept.
#
# This is how the boundary REASONS rather than matching strings. For a concept
# to be evidence-supported in the new space, the space must present at least
# one of these ARCHITECTURAL conditions — a spatial, experiential or
# contextual reason for the meaning to hold.
#
# Crucially, ``label_terms`` (the concept's own name) is tracked SEPARATELY.
# Naming the label is vocabulary matching; presenting a condition is evidence.
# --------------------------------------------------------------------------- #
_EVIDENCE_CONDITIONS = {
    "privacy": (
        "screened",
        "not overlooked",
        "kept from view",
        "withdrawn",
        "away from the street",
        "around a corner",
        "behind",
        "secluded",
    ),
    "personal_territory": (
        "occupant controls",
        "their own",
        "belongs to the occupant",
        "set aside for",
        "reserved for",
        "chosen by the occupant",
    ),
    "retreat": (
        "withdraw to",
        "recover",
        "unwind",
        "escape",
        "protected from",
        "sheltered from",
    ),
    "separation_from_public_activity": (
        "away from guests",
        "guests do not enter",
        "distinct from the shared",
        "separated from",
        "beyond the shared",
    ),
    "personal_control": (
        "occupant decides",
        "when to open",
        "at will",
        "can close",
        "can admit",
        "regulates",
    ),
    "sleeping_rest_experience": (
        "quiet",
        "undisturbed",
        "dark and still",
        "calm",
        "restful",
        "away from noise",
    ),
    "relation_to_intimate_functions": (
        "washing nearby",
        "dressing without leaving",
        "adjoining the sleeping",
        "in sequence",
        "steps away",
    ),
    "movement_and_access": (
        "reached through",
        "approached through",
        "after passing",
        "route from",
        "arrival sequence",
        "approach",
    ),
    "contrast_with_public_space": (
        "unlike the shared",
        "in contrast to",
        "opposite of the public",
        "rather than the guest",
        "different from the shared",
    ),
}

# The concept's own LABEL. Naming these is vocabulary matching, never evidence.
#
# LANGUAGE NEUTRALITY: this table holds no translation and no per-language key.
# It is NOT an English->Persian dictionary, and it must not become one. Real
# Persian support is to be designed later as genuine human teaching IN Persian
# (a Persian teaching example whose explanation carries the concept's meaning),
# not as a keyword table bolted onto the English path. A machine-translated
# label would recreate exactly the word-matching this boundary exists to catch.
_LABEL_TERMS = {
    "privacy": ("privacy", "private"),
    "personal_territory": ("territory", "personal", "territorial"),
    "retreat": ("retreat",),
    "separation_from_public_activity": (
        "separation",
        "separated",
        "segregation",
    ),
    "personal_control": ("control", "controlled"),
    "sleeping_rest_experience": ("rest", "restful", "comfort"),
    "relation_to_intimate_functions": ("intimate", "sanitary"),
    "movement_and_access": ("access", "movement", "circulation"),
    "contrast_with_public_space": ("contrast",),
}

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
    """Word-boundary containment — never a bare substring test."""
    pattern = r"(?<![a-z0-9_])" + re.escape(term.lower()) + r"(?![a-z0-9_])"
    return re.search(pattern, haystack) is not None


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #
def _validate_understood_concepts(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalUnderstandingValidationV1 requires an "
            "ArchitecturalUnderstandingFoundationV1 dict as its first argument"
        )
    contract = value.get("contract")
    if contract is None:
        raise ValueError(
            "ArchitecturalUnderstandingFoundationV1 is missing the required "
            "'contract' field"
        )
    if contract in _FORBIDDEN_CONTRACTS:
        raise ValueError(
            "ArchitecturalUnderstandingValidationV1 rejects forbidden "
            "first-argument contract: " + str(contract)
        )
    if contract != UNDERSTOOD_CONCEPTS_CONTRACT:
        raise ValueError(
            "ArchitecturalUnderstandingValidationV1 accepts only "
            "ArchitecturalUnderstandingFoundationV1 (got: " + str(contract) + ")"
        )
    if value.get("version") != UNDERSTOOD_CONCEPTS_VERSION:
        raise ValueError(
            "ArchitecturalUnderstandingValidationV1 requires understanding "
            "foundation version " + UNDERSTOOD_CONCEPTS_VERSION
        )
    return value


def _validate_new_space(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalUnderstandingValidationV1 requires an "
            "ArchitecturalNewSpaceV1 dict as its second argument"
        )
    contract = value.get("contract")
    if contract is None:
        raise ValueError(
            "ArchitecturalNewSpaceV1 is missing the required 'contract' field"
        )
    if contract in _FORBIDDEN_CONTRACTS:
        raise ValueError(
            "ArchitecturalUnderstandingValidationV1 rejects forbidden "
            "second-argument contract: " + str(contract)
        )
    if contract != NEW_SPACE_CONTRACT:
        raise ValueError(
            "ArchitecturalUnderstandingValidationV1 accepts only "
            "ArchitecturalNewSpaceV1 (got: " + str(contract) + ")"
        )
    if value.get("version") != NEW_SPACE_VERSION:
        raise ValueError(
            "ArchitecturalUnderstandingValidationV1 requires new space "
            "version " + NEW_SPACE_VERSION
        )
    return value


# --------------------------------------------------------------------------- #
# Reading the new space
# --------------------------------------------------------------------------- #
def _space_text(space: Dict[str, Any]) -> str:
    """All declared text of the new space, as one lowercased haystack.

    Only declared text fields are read. No imagery, no measurements.
    """
    parts: List[str] = []
    for key in (
        "space_name",
        "description",
        "observed_conditions",
        "spatial_conditions",
        "experience",
        "context",
        "why",
        "reason",
        "stated_qualities",
    ):
        value = space.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
    return " ".join(parts).lower()


def _known_concepts(understood: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The concepts the foundation boundary extracted, with their evidence."""
    concepts = []
    for item in _list(
        (understood.get("concept_understanding") or {}).get("extracted_concepts")
    ):
        if isinstance(item, dict) and item.get("concept"):
            concepts.append(item)
    return concepts


def _clauses(text: str) -> List[str]:
    """Split the description into clauses for within-clause reasoning.

    A negation applies only to the clause it appears in, so "the room is not
    private; it is visible from the street" must not read as support, while a
    genuine negation in one part of a description must not poison an unrelated
    part.

    Sentence terminators and coordinating conjunctions separate clauses. A
    comma separates too, but commas inside a short phrase are common, so a
    comma is treated as a boundary only when the resulting pieces are
    substantial. This keeps clause scope tight without shredding meaning.
    """
    normalised = text
    for separator in (
        ";",
        ".",
        "!",
        "?",
        "\n",
        # Unicode punctuation that scripts other than Latin also use to end a
        # clause. This is STRUCTURAL, not vocabulary: it makes no claim about
        # Persian wording and adds no translation. It only lets the splitter
        # recognise a clause boundary in any script.
        "،",
        "؛",
        " but ",
        " however ",
        " yet ",
        " whereas ",
        " while ",
    ):
        normalised = normalised.replace(separator, "|")

    clauses: List[str] = []
    for chunk in normalised.split("|"):
        chunk = chunk.strip()
        if not chunk:
            continue
        # Split on commas only when each side carries real content, so
        # "quiet, still and dark" stays one clause but "away from the street,
        # it is quiet" becomes two.
        parts = [part.strip() for part in chunk.split(",")]
        substantial = [part for part in parts if len(part.split()) >= 4]
        if len(substantial) >= 2:
            clauses.extend(substantial)
        else:
            clauses.append(chunk)
    return clauses


def _is_negated(clause: str, term: str) -> bool:
    """Is ``term`` negated within its own clause?

    Care is needed because some evidence phrases are THEMSELVES negative in
    form while being positive in meaning: "not overlooked" and "not seen from
    the street" DESCRIBE privacy. Those declared phrases are therefore exempt
    from the negation test — otherwise the boundary would read the clearest
    possible statement of privacy as a denial of it.
    """
    if not _contains_term(clause, term):
        return False

    # A declared evidence condition that is phrased negatively is positive in
    # meaning and must never be read as a negation.
    if _is_positive_negative_phrase(term):
        return False

    pattern = r"(?<![a-z0-9_])" + re.escape(term.lower()) + r"(?![a-z0-9_])"
    match = re.search(pattern, clause)
    if match is None:
        return False
    window = clause[max(0, match.start() - 30) : match.start()]
    return any(
        _contains_term(window, marker) for marker in _CONTRADICTION_MARKERS
    )


def _is_positive_negative_phrase(term: str) -> bool:
    """Is this phrase negatively worded but positively meant?

    "not overlooked" asserts being screened from view. Treating the leading
    "not" as a negation would invert the meaning. A condition the human
    supplied in negative form ("without crossing", "never entering") carries
    its negation as part of its meaning and is exempt for the same reason.
    """
    lowered = term.lower()
    return any(
        lowered.startswith(marker + " ")
        for marker in (
            "not",
            "no",
            "without",
            "never",
            "rather than",
            "instead of",
        )
    )


def _architectural_evidence(
    concept: str,
    space: Dict[str, Any],
    taught: Dict[str, Any] | None = None,
) -> Tuple[List[str], List[str], bool]:
    """Look for ARCHITECTURAL evidence of ``concept`` in the new space.

    Returns ``(evidence, negations, label_named)``.

    Evidence must GROUND the meaning. Generic architectural cues (a quiet
    quality, a relation word) cannot by themselves establish every concept at
    once — that would be a looser form of the very word-matching this boundary
    exists to catch. The rule is therefore:

      * a concept WITH declared conditions is supported only by those
        conditions;
      * a concept introduced by the human is supported by the meaning terms the
        human themselves supplied for it;
      * general architectural cues may additionally be reported, but a concept
        is never carried by generic cues alone.

    The concept's own label is tracked separately and is never evidence.
    """
    taught = taught or {}
    text = _space_text(space)
    clauses = _clauses(text)

    evidence: List[str] = []
    negations: List[str] = []

    # 0. A concept INTRODUCED by the human has no entry in the condition table.
    #    Its ground is the meaning the human supplied for it. Without this, a
    #    case-introduced concept could only ever be matched by its own name —
    #    which is exactly the word-matching this boundary must not do.
    introduced_conditions = _introduced_conditions(taught)
    if introduced_conditions:
        for condition in introduced_conditions:
            for clause in clauses:
                if _contains_term(clause, condition):
                    if _is_negated(clause, condition):
                        negations.append(condition)
                    else:
                        evidence.append(condition)

    # 1. Concept-specific architectural conditions. These are the ground.
    has_declared_conditions = (
        concept in _EVIDENCE_CONDITIONS or bool(introduced_conditions)
    )
    for condition in _EVIDENCE_CONDITIONS.get(concept, ()):
        for clause in clauses:
            if _contains_term(clause, condition):
                if _is_negated(clause, condition):
                    negations.append(condition)
                else:
                    evidence.append(condition)

    # 2. General architectural reasoning cues. These are grounds for meaning
    #    too, but they only COUNT when the concept has no declared condition of
    #    its own. Otherwise a single quality word would appear to support every
    #    concept in the table at once.
    #
    #    An incidental negation on a generic cue is NOT recorded as a
    #    contradiction. "without dressing in front of anyone" negates nothing
    #    the concept rests on, and treating it as a contradiction would raise a
    #    false alarm. Only negations of the concept's OWN conditions (above) or
    #    of its LABEL (below) are material.
    supporting_cues: List[str] = []
    for cue in _QUALITY_CUES + _EXPERIENCE_CUES + _ELEMENT_CUES + _RELATION_CUES:
        for clause in clauses:
            if _contains_term(clause, cue) and not _is_negated(clause, cue):
                supporting_cues.append(cue)

    if not has_declared_conditions and supporting_cues:
        evidence.extend(supporting_cues)

    # 3. The concept's own LABEL. This is vocabulary matching, tracked
    #    separately and never treated as evidence.
    label_named = False
    label_terms = list(_LABEL_TERMS.get(concept, ()))
    if not label_terms:
        # A case-introduced concept has no declared label table; its own name
        # IS its label. Tracked as vocabulary only, never as evidence.
        label_terms = [concept.replace("_", " ")]
    for term in label_terms:
        for clause in clauses:
            if _contains_term(clause, term):
                label_named = True
                if _is_negated(clause, term):
                    negations.append(term)

    # 4. The concept's own name tokens are tracked as vocabulary, never as
    #    evidence. A new space that merely repeats the concept's name has NOT
    #    expressed its meaning.
    if concept not in _LABEL_TERMS:
        for token in _tokenize(concept):
            if token in {"the", "and", "of", "a", "an", "with"}:
                continue
            for clause in clauses:
                if _contains_term(clause, token):
                    label_named = True

    return _unique(evidence), _unique(negations), label_named


def _introduced_conditions(taught: Dict[str, Any]) -> List[str]:
    """Evidence conditions for a concept the human introduced.

    The human supplied the meaning and (optionally) the evidence in their own
    teaching example. Those are the ONLY grounds a case-introduced concept can
    stand on, because the boundary holds no pre-declared conditions for it.

    Short generic stop words are discarded so a single common word cannot act
    as evidence for everything.
    """
    if taught.get("anchor") != "case_introduced":
        return []
    sources: List[str] = []
    for key in ("meaning", "case_evidence", "evidence_reference"):
        value = taught.get(key)
        if isinstance(value, str):
            sources.append(value)
        elif isinstance(value, (list, tuple)):
            sources.extend(str(v) for v in value if isinstance(v, (str,)))
    return _candidate_conditions(" ".join(sources))


def _candidate_conditions(text: str) -> List[str]:
    """Extract meaningful conditions from a human-supplied meaning sentence.

    A concept introduced by the human is analysed against the meaning THEY
    gave. Two shapes are extracted, and both matter:

      * negatively-phrased PHRASES ("without crossing", "never entering").
        These are positive in meaning — a visitor who reaches the space
        without crossing the private domain IS expressing the concept. They
        must survive as whole phrases, because splitting them would let the
        leading negation read as a contradiction.
      * standalone long words. These survive paraphrase better than common
        stop words and are unlikely to match by accident.

    Stop words and short words are discarded so a single common word cannot act
    as evidence for everything.
    """
    if not text:
        return []
    lowered = text.lower()

    conditions: List[str] = []

    # 1. Negatively-phrased phrases are captured whole, so they are later
    #    recognised as positive-in-meaning rather than as negations.
    for marker in ("without", "never", "rather than", "instead of"):
        pattern = r"(?<![a-z0-9_])" + re.escape(marker) + r"\s+([a-z]{6,})"
        for match in re.finditer(pattern, lowered):
            phrase = marker + " " + match.group(1)
            conditions.append(phrase)

    # 2. Standalone long words as paraphrase-resistant conditions.
    for token in _tokenize(lowered):
        if token in _MEANING_STOP_WORDS or len(token) < 6:
            continue
        conditions.append(token)

    return _unique(conditions)


_MEANING_STOP_WORDS = {
    "the", "and", "of", "a", "an", "with", "without", "for", "to", "in",
    "on", "at", "by", "is", "are", "was", "were", "be", "being", "been",
    "that", "this", "these", "those", "it", "its", "their", "there",
    "which", "who", "whom", "where", "when", "how", "why", "what", "not",
    "no", "or", "as", "from", "into", "than", "then", "so", "such",
    "can", "may", "might", "must", "should", "would", "could", "will",
    "space", "place", "position", "positioned", "sized", "kept",
    "deliberately", "visitors", "visitor", "guests", "guest", "user",
    "without", "never", "rather", "instead",
}


def _evidence_basis(evidence: List[str], negations: List[str]) -> Dict[str, Any]:
    """Classify the ground of each piece of evidence, so the verdict is
    auditable rather than a bare yes/no.

    `reason_grounded` mirrors the verdict rule exactly: evidence grounds the
    reading even when an incidental negation is also present. A negation only
    removes the ground when it has left no evidence standing — having the two
    functions disagree about the same situation would make the audit trail
    untrustworthy.
    """
    kinds: List[str] = []
    for item in evidence:
        if item in _RELATION_CUES:
            kinds.append("spatial_relation")
        elif item in _QUALITY_CUES:
            kinds.append("experiential_quality")
        elif item in _EXPERIENCE_CUES:
            kinds.append("user_experience")
        elif item in _ELEMENT_CUES:
            kinds.append("architectural_element")
        else:
            kinds.append("concept_condition")
    return {
        "evidence_kinds": _unique(kinds),
        "negation_present": bool(negations),
        "reason_grounded": bool(evidence),
        "label_only": not evidence and not negations,
    }


def _verdict(evidence: List[str], negations: List[str], label_named: bool) -> str:
    """The central discrimination.

    Evidence (a reason) outranks the label. A label with no reason is exactly
    `word_matching_only` — reported as NOT understanding.

    Negation is scoped, not global. A description may legitimately negate one
    incidental quality while still presenting solid architectural evidence for
    the concept. Negation therefore only forces `not_addressed` when it leaves
    the concept with NO surviving evidence. When evidence and a stray negation
    coexist, the evidence is reported and the contradiction is raised as an
    open question for the human rather than silently discarding the reading.

    A concept the space neither grounds nor contradicts is `not_addressed`.
    This is NOT a failure, NOT a lack of understanding, NOT a contradiction,
    and NOT a statement that the concept is absent. It means exactly one thing:
    the teaching case did not provide enough information to evaluate that
    concept. The concept may apply perfectly well; this material simply does
    not say. Only a concept that is NAMED-but-unreasoned, or explicitly
    CONTRADICTED, is a real finding.
    """
    if evidence:
        return "understood"
    if negations:
        return "not_addressed"
    if label_named:
        return "word_matching_only"
    return "not_addressed"


def _walkthrough(
    concepts: List[Dict[str, Any]],
    space: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Reason concept by concept against the new space."""
    walkthrough: List[Dict[str, Any]] = []

    for item in concepts:
        concept = item.get("concept")
        if not concept:
            continue

        evidence, negations, label_named = _architectural_evidence(
            concept, space, item
        )
        status = _verdict(evidence, negations, label_named)
        vocab_matches = _unique([concept] if label_named else [])

        walkthrough.append(
            {
                "concept": concept,
                "meaning": item.get("meaning"),
                "meaning_origin": item.get("meaning_origin"),
                "anchor": item.get("anchor"),
                "case_operation": item.get("case_operation"),
                "analysis_status": status,
                "architectural_evidence": evidence,
                "vocabulary_matches": vocab_matches,
                "negations": negations,
                "evidence_basis": _evidence_basis(evidence, negations),
                "reason_and_context": deepcopy(
                    item.get("reason_and_context") or {}
                ),
                "alternative_interpretations": _list(
                    item.get("alternative_interpretations")
                ),
                "context_dependencies": _list(item.get("context_dependencies")),
                "uncertainty": {
                    "understood": status == "understood",
                    "word_matching_only": status == "word_matching_only",
                    "not_addressed": status == "not_addressed",
                    # `not_addressed` is NEVER a failure and NEVER asserts the
                    # concept is absent. It means the material does not provide
                    # enough information to evaluate the concept.
                    "insufficient_information_to_evaluate": (
                        status == "not_addressed"
                    ),
                    "not_a_failure": status == "not_addressed",
                    "not_a_contradiction": True,
                    "not_absence_of_concept": True,
                    "resolved": False,
                },
            }
        )
    return walkthrough


def _open_questions(walkthrough: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Questions a human could use to close the understanding gap.

    These are PROMPTS for a human. They assert nothing and request no action.
    """
    questions: List[Dict[str, Any]] = []

    for item in walkthrough:
        concept = item.get("concept")
        status = item.get("analysis_status")
        if status == "word_matching_only":
            questions.append(
                {
                    "question_type": "meaning_gap_probe",
                    "target": concept,
                    "question": (
                        "The description names " + str(concept) + " but gives "
                        "no architectural reason for it. What in the spatial "
                        "situation produces it, and how would the user feel it?"
                    ),
                    "rationale": "label_named_without_architectural_evidence",
                }
            )
        elif status == "not_addressed":
            questions.append(
                {
                    "question_type": "not_addressed_probe",
                    "target": concept,
                    "question": (
                        "This material does not provide enough information to "
                        "evaluate " + str(concept) + ". Does the concept apply "
                        "here, and if so, which architectural conditions carry "
                        "it? No answer is treated as failure — this only means "
                        "the material does not yet say."
                    ),
                    "rationale": "insufficient_information_to_evaluate",
                }
            )

    if any(
        item.get("evidence_basis", {}).get("negation_present")
        for item in walkthrough
    ):
        questions.append(
            {
                "question_type": "contradiction_probe",
                "target": None,
                "question": (
                    "The description appears to contradict a pattern taught "
                    "earlier. Can you explain why it differs, or whether the "
                    "earlier interpretation needs revising?"
                ),
                "rationale": "taught_interpretation_may_not_transfer",
            }
        )
    if questions:
        questions.append(
            {
                "question_type": "human_confirmation_probe",
                "target": None,
                "question": (
                    "Is this analysis of what was and was not understood "
                    "consistent with your own reading of the space?"
                ),
                "rationale": "human_confirmation_requested",
            }
        )
    return questions


# --------------------------------------------------------------------------- #
# Public function
# --------------------------------------------------------------------------- #
def validate_architectural_understanding_v1(
    understood_concepts: Dict[str, Any],
    new_space: Dict[str, Any],
) -> Dict[str, Any]:
    """Analyse whether ArchitectOS understood the concepts, or only the words.

    Pure function. Deterministic. Reads nothing, writes nothing, learns
    nothing, designs nothing, proposes no plan.
    """
    understood = _validate_understood_concepts(understood_concepts)
    space = _validate_new_space(new_space)

    concepts = _known_concepts(understood)
    walkthrough = _walkthrough(concepts, space)

    understood_items = [w for w in walkthrough if w["analysis_status"] == "understood"]
    word_only_items = [
        w for w in walkthrough if w["analysis_status"] == "word_matching_only"
    ]
    not_addressed_items = [
        w for w in walkthrough if w["analysis_status"] == "not_addressed"
    ]

    concept_understanding_analysis = [
        {
            "concept": w["concept"],
            "meaning": w["meaning"],
            "meaning_origin": w.get("meaning_origin"),
            "anchor": w.get("anchor"),
            "case_operation": w.get("case_operation"),
            "analysis_status": w["analysis_status"],
            "architectural_evidence": deepcopy(w["architectural_evidence"]),
            "vocabulary_matches": deepcopy(w["vocabulary_matches"]),
            "evidence_basis": deepcopy(w["evidence_basis"]),
        }
        for w in walkthrough
    ]

    # `concept_understood` asks whether every concept the material actually
    # RAISED was understood. A concept the material gives insufficient
    # information to evaluate is `not_addressed` and is excluded: it is not a
    # failure, not a lack of understanding, not a contradiction, and not a
    # statement that the concept is absent.
    addressed = understood_items + word_only_items
    concept_understood = bool(addressed) and not word_only_items

    uncertainty = {
        # Only concepts the material actually RAISED and that failed to be
        # understood. A concept with insufficient material to evaluate is NOT
        # failure and is NOT listed here.
        "concepts_not_understood": [
            w["concept"] for w in word_only_items
        ],
        "words_matched_without_understanding": [
            w["concept"] for w in word_only_items
        ],
        # Not a finding about the concept. Reported so nothing is hidden, and
        # explicitly meaning "insufficient information to evaluate" — never
        # failure, lack of understanding, contradiction, or absence.
        "concepts_not_addressed_by_space": [
            w["concept"] for w in not_addressed_items
        ],
        "not_addressed_meaning": (
            "insufficient_information_to_evaluate_not_absence"
        ),
        "concepts_are_not_mandatory": True,
        "concepts_carried_from_case": [
            w["concept"]
            for w in walkthrough
            if w.get("anchor") == "case_introduced"
        ],
        "concepts_excluded_by_case": [
            w["concept"]
            for w in walkthrough
            if w.get("anchor") == "case_excluded"
        ],
        "concepts_carried_from_index": [
            w["concept"]
            for w in walkthrough
            if w.get("anchor") == "semantic_index"
        ],
        "meaning_origin_breakdown": [
            {
                "concept": w["concept"],
                "meaning_origin": w.get("meaning_origin"),
                "case_operation": w.get("case_operation"),
            }
            for w in walkthrough
        ],
        "alternative_interpretations_preserved": True,
        "context_dependencies_preserved": True,
        "multiple_valid_solutions_possible": True,
        "human_uncertainty": deepcopy(space.get("uncertainty") or {}),
        "single_correct_interpretation": False,
        "resolved": False,
        "designed": False,
        "plan_proposed": False,
    }

    analysis_basis = {
        "concepts_reference": {
            "contract": understood.get("contract"),
            "version": understood.get("version"),
            "concept_count": len(concepts),
        },
        "space_reference": {
            "contract": space.get("contract"),
            "version": space.get("version"),
            "space_id": space.get("space_id"),
            "space_name": space.get("space_name"),
        },
        "analysis_method": ANALYSIS_METHOD,
        "evidence_required_beyond_vocabulary": True,
        # The spatial narrative itself is NOT copied forward.
        "restatement_of_description": None,
    }

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "concept_understanding_analysis": concept_understanding_analysis,
        "understanding_summary": {
            "total_concepts": len(walkthrough),
            "understood_count": len(understood_items),
            "word_matching_only_count": len(word_only_items),
            # Not a failure count: a space is allowed not to raise a concept.
            "not_addressed_count": len(not_addressed_items),
            "addressed_count": len(addressed),
            "concept_understood": concept_understood,
            "any_understanding": bool(understood_items),
            "only_words_matched": bool(word_only_items)
            and not understood_items,
            "concepts_are_not_mandatory": True,
        },
        "concept_walkthrough": walkthrough,
        "evidence_basis": {
            "analysis_method": ANALYSIS_METHOD,
            "concepts_with_architectural_evidence": [
                w["concept"] for w in understood_items
            ],
            "concepts_with_vocabulary_only": [
                w["concept"] for w in word_only_items
            ],
        },
        "uncertainty": uncertainty,
        "open_questions": _open_questions(walkthrough),
        "analysis_basis": analysis_basis,
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
        "concept_understanding_analysis": result.get(
            "concept_understanding_analysis"
        ),
        "understanding_summary": result.get("understanding_summary"),
        "concept_walkthrough": result.get("concept_walkthrough"),
        "evidence_basis": result.get("evidence_basis"),
        "uncertainty": result.get("uncertainty"),
        "open_questions": result.get("open_questions"),
        "analysis_basis": result.get("analysis_basis"),
    }
    serialized = str(authored).lower()
    for term in _FORBIDDEN_TERMS:
        if _contains_term(serialized, term):
            raise AssertionError(
                "ArchitecturalUnderstandingValidationV1 emitted forbidden "
                "term: " + term
            )
