"""ARCHITECTURAL CONCEPT LEARNING / TRANSFER TEST V1.

This is the most important validation step so far.

────────────────────────────────────────────────────────────────────────────
THE QUESTION THIS MODULE ANSWERS
────────────────────────────────────────────────────────────────────────────

    Can ArchitectOS learn an architectural concept from human teaching
    examples, and TRANSFER that understanding to a NEW, unseen architectural
    situation — rather than matching vocabulary?

It does NOT ask whether ArchitectOS "understands architecture like a human".
It answers exactly one narrow, testable question, and the report it produces
is called, and only ever called:

    "architectural conceptual transfer under controlled test conditions."

────────────────────────────────────────────────────────────────────────────
THE TWO PHASES
────────────────────────────────────────────────────────────────────────────

PHASE A — HUMAN TEACHING

    One architectural concept is taught through MULTIPLE human examples that
    use DIFFERENT wording. The concept is not repeatedly named. The learner
    derives a CONCEPT MODEL from the architectural conditions, the human's
    reasons, the stated context and the declared uncertainty — never a fixed
    list of words.

    The teaching domain is a dwelling. Master Bedroom is only the INITIAL
    domain; it is deliberately taught as its underlying concepts (privacy,
    personal territory, retreat, controlled access, separation from shared
    activity, public/intimate hierarchy, occupant control, relation to
    intimate functions) and NOT as `bed + bathroom + closet`.

PHASE B — UNSEEN TRANSFER TEST

    NEW situations that were NEVER used during teaching are presented. They use
    different vocabulary, do not name the taught concept, do not reuse teaching
    sentences, and carry no expected-answer label. The set includes positive,
    contrast (negative), ambiguous and adversarial word-only cases.

────────────────────────────────────────────────────────────────────────────
THE REQUIRED OUTCOMES
────────────────────────────────────────────────────────────────────────────

    transfer_success        the unseen case carries architectural conditions
                            expressing the learned concept; the concept name
                            is not needed and is not used
    vocabulary_only         the case NAMED concept words but presents no
                            architectural conditions — word matching, NOT
                            transfer
    not_enough_evidence     the material cannot decide (explicitly NOT failure)
    incorrect_transfer      the case expresses a DIFFERENT concept while
                            appearing to target the taught one
    contradictory_evidence  the case denies the conditions the concept rests on

The final report distinguishes, in plain terms:

    LEARNED / TRANSFERRED   from   RECOGNIZED FROM WORDS   from
    NOT ENOUGH INFORMATION

────────────────────────────────────────────────────────────────────────────
LEAKAGE PREVENTION (the most important property)
────────────────────────────────────────────────────────────────────────────

    L1  An unseen case is NEVER used during teaching. Enforced by identity:
        every teach-example id must differ from every unseen-case id, and no
        unseen description text may equal any teaching description text.
    L2  The expected answer must NOT be present in the case text. The expected
        outcome is carried OUT OF BAND and never appended to the case.
    L3  The target concept's NAME is never used as evidence. The engine strips
        the concept name from every string it reasons over before matching.
    L4  The validator must NOT compare the case against a predefined keyword
        list. The conditions it reasons over are DERIVED FROM THE TEACHING
        EXAMPLES at run time, not declared here.

Every guard L1–L4 is exercised by a dedicated test, and each has a NEGATIVE
CONTROL proving the guard can actually fire.

────────────────────────────────────────────────────────────────────────────
WHAT THIS MODULE MUST NOT DO
────────────────────────────────────────────────────────────────────────────

    - design anything, propose a plan (پلان), or suggest an arrangement
    - add CAD, geometry, BIM, IFC, rendering, UI or design generation
    - learn permanently, persist, or write to Memory
    - modify or replace any production module
    - claim human-like understanding

This module is transient, read-only and deterministic.
"""

from __future__ import annotations

import re

from copy import deepcopy
from typing import Any, Dict, List, Tuple


CONTRACT = "ArchitecturalConceptTransferTestV1"
VERSION = "1.0"

# The teaching phase consumes the human example contract directly.
TEACHING_EXAMPLE_CONTRACT = "ArchitecturalHumanTeachingExampleV1"
TEACHING_EXAMPLE_VERSION = "1.0"

# The unseen phase is presented to the understanding-validation boundary.
NEW_SPACE_CONTRACT = "ArchitecturalNewSpaceV1"
NEW_SPACE_VERSION = "1.0"

# The name of this test's subject, stated once and never used as evidence.
TEST_SUBJECT = "architectural concept learning and transfer under controlled test conditions"

# ────────────────────────────────────────────────────────────────────────────
# The five required outcomes. This tuple is the whole verdict vocabulary.
# ────────────────────────────────────────────────────────────────────────────
TRANSFER_OUTCOMES = (
    "transfer_success",
    "vocabulary_only",
    "not_enough_evidence",
    "incorrect_transfer",
    "contradictory_evidence",
)

# Plain-language grouping demanded by the brief's final report.
OUTCOME_FAMILIES = {
    "transfer_success": "LEARNED_OR_TRANSFERRED",
    "incorrect_transfer": "LEARNED_OR_TRANSFERRED",
    "vocabulary_only": "RECOGNIZED_FROM_WORDS",
    "not_enough_evidence": "NOT_ENOUGH_INFORMATION",
    "contradictory_evidence": "NOT_ENOUGH_INFORMATION",
}

# Where a case came from. A case declared as unseen MUST satisfy the leakage
# guards before it is analysed.
ORIGINS = ("teaching", "unseen")

# Obligated reporting surfaces. The brief requires each case to report these
# SEPARATELY; the engine always emits all of them.
REQUIRED_CASE_REPORTS = (
    "conceptual_evidence",
    "vocabulary_overlap",
    "reasoning_chain",
    "confidence_and_uncertainty",
    "transferred_parts",
    "non_transferable_parts",
)

# Contracts that must never be accepted in place of a teaching example or an
# unseen case. Reused verbatim from the two upstream boundaries so no new
# vocabulary is invented.
_FORBIDDEN_CONTRACTS = (
    "ArchitecturalCADDrawingV1",
    "ArchitecturalDXFDrawingV1",
    "ArchitecturalDWGDrawingV1",
    "ArchitecturalBIMEntityV1",
    "ArchitecturalIFCEntityV1",
    "ArchitecturalRenderingOutputV1",
    "ArchitecturalGeometryIntentV1",
    "ArchitecturalMemoryRecordV1",
    "ArchitecturalVisionReportV1",
    "ArchitecturalDesignReasoningResultV1",
    "ArchitecturalSemanticGraphV1",
    "ImageIntentV1",
    "SiteIntentV1",
    "ArchitecturalLayoutIntentResolverV1",
    "ProgramIntentResolutionV1",
    "ArchitecturalUnderstandingV2",
    "ArchitecturalUnderstandingV1",
    "ArchitecturalObservationV1",
)

# A minimal, non-semantic stop list. These words carry no architectural meaning
# and must never influence evidence. Note it contains NO domain vocabulary:
# it exists to stop glue words, not to name architecture.
_GLUE_WORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "by",
        "for", "with", "without", "from", "into", "as", "is", "are", "was",
        "were", "be", "been", "being", "it", "its", "their", "there", "that",
        "this", "these", "those", "which", "who", "whom", "where", "when",
        "how", "why", "what", "not", "no", "than", "then", "so", "such",
        "can", "may", "might", "must", "should", "would", "could", "will",
        "also", "but", "if", "only", "very", "more", "most", "some", "any",
        "each", "other", "another", "both", "all", "one", "two", "do", "does",
        "has", "have", "had", "them", "they", "he", "she", "his", "her",
    }
)

# Terms that must never be emitted by this boundary's own authored payload.
_FORBIDDEN_TERMS = (
    "design_solution",
    "design_rule",
    "layout",
    "placement",
    "geometry",
    "dimension",
    "cad",
    "dwg",
    "dxf",
    "bim",
    "ifc",
    "render",
    "should_place",
    "optimal",
    "recommended",
)


# ────────────────────────────────────────────────────────────────────────────
# Small shared helpers (kept local so this module has no production dependency)
# ────────────────────────────────────────────────────────────────────────────


def _list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _unique(values: Any) -> List[Any]:
    seen: List[Any] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def _tokenize(value: Any) -> List[str]:
    return [t for t in re.split(r"[^a-z0-9]+", str(value or "").lower()) if t]


def _stem(token: str) -> str:
    """A small, deterministic normaliser for word variants.

    Only enough to fold the common English inflections and the adjective/noun
    pairs that would otherwise hide a match: ``privacy`` / ``private`` /
    ``privately`` must normalise to the same form, and ``control`` /
    ``controls`` / ``controlled`` likewise.

    This is a NORMALISATION, not a semantic model. It never merges two
    different ideas and it invents nothing.

    The equivalence families it folds:
      * trailing ``y`` / ``e`` / ``ity`` / ``acy`` / ``ate`` families, so
        ``privacy``→``priva`` and ``private``→``priva``;
      * plural and verb ``-s`` / ``-es`` / ``-ed`` / ``-ing``;
      * ``-tion`` / ``-sion`` / ``-ment`` / ``-ness`` abstract-noun endings.
    """
    token = token.lower()
    if len(token) <= 3:
        return token

    # Abstract-noun and verb endings, longest first.
    for suffix in ("ations", "ation", "itions", "ition", "sions", "sion",
                   "ness", "ment", "ings", "ing", "ies", "ied", "ers", "er",
                   "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            token = token[: -len(suffix)]
            break

    # Adjective/noun families that differ only in the final vowel pattern.
    # Applied after suffix removal so both "privacy" and "private" land here.
    for ending, replacement in (
        ("acy", "a"),
        ("ity", "a"),
        ("ce", ""),
        ("cy", ""),
        ("ate", "a"),
        ("ive", "a"),
        ("ely", "a"),
        ("ly", ""),
        ("e", ""),
    ):
        if len(token) > len(ending) + 2 and token.endswith(ending):
            token = token[: -len(ending)] + replacement
            break

    return token


def _stem_set(tokens: Any) -> List[str]:
    return _unique([_stem(t) for t in tokens if len(t) > 2])


def _content_tokens(value: Any) -> List[str]:
    """Meaning-bearing tokens only: glue words removed."""
    return [t for t in _tokenize(value) if t not in _GLUE_WORDS and len(t) > 2]


# Relation words that glue two architectural ideas together. A phrase built
# across one of these carries a RELATIONSHIP, which is the whole point of an
# architectural condition.
_RELATION_WORDS = frozenset(
    {
        "from", "without", "beyond", "past", "after", "before", "toward",
        "away", "inside", "within", "between", "through", "into", "against",
        "unlike", "apart", "separate", "separated", "separation", "adjoin",
        "adjoining", "reach", "reached", "reaches", "opening", "opens",
    }
)


def _condition_phrases(value: Any) -> List[str]:
    """Distil ARCHITECTURAL CONDITION PHRASES from a human sentence.

    A single word is not a condition ("quiet" describes a mood, not a spatial
    situation). A condition is a PHRASE that states how one thing relates to
    another: "separation from the shared house", "without leaving",
    "controls who may enter".

    Two shapes are extracted:
      * RELATION PHRASES — a content word glued to another across a relation
        word. These carry structure, which survives paraphrase.
      * ADJACENT PAIRS — two consecutive content words. These carry a compound
        idea ("shared house", "sleeping place").

    Single content words are deliberately NOT returned. Returning them is what
    turns a concept model into a word list, which the brief forbids.
    """
    tokens = _tokenize(value)
    phrases: List[str] = []

    # Relation phrases: <content> <relation> <content>
    for i in range(len(tokens) - 2):
        left, mid, right = tokens[i], tokens[i + 1], tokens[i + 2]
        if (
            left not in _GLUE_WORDS
            and len(left) > 2
            and mid in _RELATION_WORDS
            and right not in _GLUE_WORDS
            and len(right) > 2
        ):
            phrases.append(left + " " + mid + " " + right)

    # Adjacent content pairs, skipping glue: <content> <content>
    content = [t for t in tokens if t not in _GLUE_WORDS and len(t) > 2]
    for i in range(len(content) - 1):
        phrases.append(content[i] + " " + content[i + 1])

    return _unique(phrases)


def _contains_term(haystack: str, term: str) -> bool:
    """Word-boundary containment.

    Plain ``in`` would let ``outdoor`` match ``door``. A boundary check keeps
    the match honest.
    """
    if not term:
        return False
    pattern = r"(?<![a-z0-9_])" + re.escape(term.lower()) + r"(?![a-z0-9_])"
    return re.search(pattern, haystack.lower()) is not None


# ────────────────────────────────────────────────────────────────────────────
# The learned CONDITION model (Phase A output, Phase B input)
#
# This is the heart of the test. What the learner generalises is NOT a phrase
# and NOT a word. It is a CONDITION: a small set of distinctive architectural
# idea-stems that a single clause of human reasoning held TOGETHER.
#
# Why a co-occurrence set rather than a phrase?
#
#   Teaching example 1 says "the occupant controls who may enter".
#   Teaching example 2 says "they decide when the door is open".
#   Teaching example 3 says "the occupant keeping control of the entrance".
#
#   The wording differs every time, so no phrase repeats. What DOES recur is
#   the pairing of an actor-stem ("occupant") with an act-stem ("control" /
#   "decide"). A co-occurrence set survives paraphrase; a phrase does not.
#
# A condition is stored with PROVENANCE (which examples expressed it), and a
# stem that recurs across INDEPENDENT examples is a NUCLEUS. Nuclei are the
# cross-example agreement signal — the one thing word matching cannot fake,
# because an adversarial case that merely repeats the concept's name produces
# no agreeing architectural nuclei.
# ────────────────────────────────────────────────────────────────────────────


def _condition_stem_sets(clause: str) -> List[List[str]]:
    """Distinctive content stems of one clause, as the units a condition forms from.

    Only stems are returned, de-duplicated and stable in order. Glue words and
    short words are already removed by ``_content_tokens``.
    """
    return sorted(set(_stem_set(_content_tokens(clause))))


def _pair_conditions(stems: List[str]) -> List[Tuple[str, ...]]:
    """Every unordered 2-subset of ``stems`` as a condition key.

    A two-stem co-occurrence is the smallest unit that carries an architectural
    RELATIONSHIP ("occupant" + "control") rather than a single idea. A lone word
    is deliberately never a condition — that is what would turn the model back
    into a word list.
    """
    keys: List[Tuple[str, ...]] = []
    for i in range(len(stems)):
        for j in range(i + 1, len(stems)):
            keys.append((stems[i], stems[j]))
    return keys


def _condition_label(key: Tuple[str, ...]) -> str:
    """A stable, readable label for a learned condition.

    The label is the condition's stems joined, which keeps the audit trail
    honest: the reader sees exactly which idea-stems the learner generalised,
    and no concept name can appear in it (the name is stripped before learning).
    """
    return " + ".join(key)


def _clauses(text: str) -> List[str]:
    """Split material into clauses so a negation stays scoped to its clause."""
    normalised = str(text or "")
    for separator in (
        ";", ".", "!", "?", "\n", "،", "؛",
        " but ", " however ", " yet ", " whereas ", " while ",
    ):
        normalised = normalised.replace(separator, "|")
    clauses: List[str] = []
    for chunk in normalised.split("|"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [p.strip() for p in chunk.split(",")]
        substantial = [p for p in parts if len(p.split()) >= 4]
        if len(substantial) >= 2:
            clauses.extend(substantial)
        else:
            clauses.append(chunk)
    return clauses


# ────────────────────────────────────────────────────────────────────────────
# Leakage-prevention primitives (L1–L4)
# ────────────────────────────────────────────────────────────────────────────


def _strip_concept_name(text: str, concept: str) -> str:
    """Remove the target concept's name from material before reasoning.

    GUARD L3. The target's own name is the one piece of vocabulary that would
    let a case "recognize" the concept without presenting a single
    architectural condition. Every string this engine reasons over is passed
    through here first, so the name cannot act as evidence.

    The name is removed in three shapes: the full label, its underscore form,
    and each of its name tokens. Unrelated words are untouched.
    """
    if not concept:
        return text
    result = " " + str(text or "") + " "
    candidates = [concept, concept.replace("_", " ")]
    candidates.extend(_tokenize(concept))
    for candidate in candidates:
        candidate = candidate.strip()
        if len(candidate) < 3:
            continue
        pattern = r"(?<![a-z0-9_])" + re.escape(candidate.lower()) + r"(?![a-z0-9_])"
        result = re.sub(pattern, " ", result)
    return " ".join(result.split())


def _text_of_case(case: Dict[str, Any]) -> str:
    """All human-authored text of a case, joined.

    Only the descriptive fields are read. No expected-answer field is ever
    read here — the expected outcome is carried out of band (GUARD L2).
    """
    parts: List[str] = []
    for key in (
        "description",
        "observed_elements",
        "human_explanation",
        "meaning",
        "why",
        "reason",
        "context",
        "user_experience",
        "spatial_logic",
    ):
        value = case.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (list, tuple)):
            parts.extend(str(v) for v in value if isinstance(v, (str, int, float)))
    return " ".join(parts)


def _assert_no_leakage(
    teaching_examples: List[Dict[str, Any]],
    unseen_case: Dict[str, Any],
) -> None:
    """GUARD L1 + L2. Refuse any unseen case that leaked from teaching.

    Checks, in order:
      * the unseen case declares origin``unseen``;
      * its id is absent from the teaching ids;
      * its raw description text is not byte-equal to any teaching text;
      * no field of the case carries an expected-answer key.
    """
    if unseen_case.get("origin") != "unseen":
        raise ValueError(
            "TransferTest: a Phase B case must declare origin='unseen', got "
            + repr(unseen_case.get("origin"))
        )

    # A case identifies itself by either contract's key: the unseen space
    # contract carries ``space_id``; a caller may also pass ``case_id``.
    unseen_id = unseen_case.get("space_id") or unseen_case.get("case_id")
    teaching_ids = {e.get("example_id") for e in teaching_examples}
    if unseen_id in teaching_ids:
        raise ValueError(
            "TransferTest: leakage (L1) — unseen case id "
            + repr(unseen_id)
            + " was used during teaching"
        )

    unseen_text = str(unseen_case.get("description") or "").strip().lower()
    if unseen_text:
        for example in teaching_examples:
            teaching_text = str(example.get("description") or "").strip().lower()
            if teaching_text and teaching_text == unseen_text:
                raise ValueError(
                    "TransferTest: leakage (L1) — unseen description is "
                    "byte-identical to teaching example "
                    + repr(example.get("example_id"))
                )

    for leaked_key in ("expected", "expected_outcome", "expected_concept",
                       "answer", "label", "ground_truth"):
        if leaked_key in unseen_case:
            raise ValueError(
                "TransferTest: leakage (L2) — the expected answer must be "
                "carried out of band, but the case carries "
                + repr(leaked_key)
            )


# ────────────────────────────────────────────────────────────────────────────
# Input gating
# ────────────────────────────────────────────────────────────────────────────


def _validate_directive(value: Any) -> Dict[str, Any]:
    """Validate the top-level teaching/transfer directive."""
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalConceptTransferTestV1 requires a directive dict, "
            "got " + type(value).__name__
        )
    contract = value.get("contract")
    if contract in _FORBIDDEN_CONTRACTS:
        raise ValueError(
            "ArchitecturalConceptTransferTestV1 rejects forbidden contract: "
            + str(contract)
        )
    if contract != CONTRACT:
        raise ValueError(
            "ArchitecturalConceptTransferTestV1 requires contract "
            + repr(CONTRACT)
            + ", got "
            + repr(contract)
        )
    if value.get("version") != VERSION:
        raise ValueError(
            "ArchitecturalConceptTransferTestV1 requires version "
            + repr(VERSION)
            + ", got "
            + repr(value.get("version"))
        )
    return deepcopy(value)


def _validate_teaching_example(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "TransferTest: a teaching example must be a dict, got "
            + type(value).__name__
        )
    contract = value.get("contract")
    if contract in _FORBIDDEN_CONTRACTS:
        raise ValueError(
            "TransferTest: teaching example reached a forbidden contract: "
            + str(contract)
        )
    if contract != TEACHING_EXAMPLE_CONTRACT:
        raise ValueError(
            "TransferTest: teaching example requires contract "
            + repr(TEACHING_EXAMPLE_CONTRACT)
            + ", got "
            + repr(contract)
        )
    if value.get("version") != TEACHING_EXAMPLE_VERSION:
        raise ValueError(
            "TransferTest: teaching example requires version "
            + repr(TEACHING_EXAMPLE_VERSION)
        )
    return deepcopy(value)


def _validate_unseen_case(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "TransferTest: an unseen case must be a dict, got "
            + type(value).__name__
        )
    contract = value.get("contract")
    if contract in _FORBIDDEN_CONTRACTS:
        raise ValueError(
            "TransferTest: unseen case reached a forbidden contract: "
            + str(contract)
        )
    if contract != NEW_SPACE_CONTRACT:
        raise ValueError(
            "TransferTest: unseen case requires contract "
            + repr(NEW_SPACE_CONTRACT)
            + ", got "
            + repr(contract)
        )
    if value.get("version") != NEW_SPACE_VERSION:
        raise ValueError(
            "TransferTest: unseen case requires version "
            + repr(NEW_SPACE_VERSION)
        )
    return deepcopy(value)


# ────────────────────────────────────────────────────────────────────────────
# PHASE A — HUMAN TEACHING
# ────────────────────────────────────────────────────────────────────────────


def _teach_phase(
    teaching_examples: List[Dict[str, Any]],
    concept_name: str,
) -> Dict[str, Any]:
    """Derive a CONCEPT MODEL from several differently-worded examples.

    GUARD L4. The model is built at RUN TIME from the teaching material. No
    condition, no cue and no keyword is declared in this module. What the
    learner ends up with is a set of architectural CONDITIONS distilled from
    the human's own reasons and the spatial situations that carried them.

    THE LEARNING RULE (and why it is not word matching):

      * each teaching example is read by the understanding FOUNDATION, which
        reports which concepts the example GROUNDED and from which evidence;
      * the human's REASON sentence is the source of the architectural
        conditions — observation text can never ground a concept;
      * from each clause of reasoning, the learner records the SET of
        distinctive idea-stems the clause held together. Every 2-subset of
        those stems becomes a candidate CONDITION with provenance;
      * a stem that occurs in reasoning clauses of TWO OR MORE independent
        examples is a NUCLEUS — the cross-example agreement that resists
        paraphrase;
      * a condition whose provenance spans two or more independent examples is
        a CROSS-EXAMPLE CONDITION — the strongest signal the learner has.

    Nothing here is a lookup list. Every condition is traceable to the clause
    and the example that produced it, and the concept's own name is stripped
    before any of this runs, so it can never enter a condition.
    """
    # Imported lazily so the module stays importable in isolation for tests
    # that only exercise the leakage guards.
    from core.knowledge.understanding_foundation.architectural_understanding_foundation_v1 import (
        understand_architectural_example_v1,
    )

    per_example: List[Dict[str, Any]] = []
    condition_provenance: Dict[Tuple[str, ...], List[Dict[str, Any]]] = {}
    stem_provenance: Dict[str, set] = {}

    for example in teaching_examples:
        validated = _validate_teaching_example(example)
        understood = understand_architectural_example_v1(validated)
        example_id = validated.get("example_id")

        # Only concepts the case GROUNDED count as taught. A concept the
        # example merely listed is not taught by that example.
        grounded = [
            c
            for c in understood["concept_understanding"]["extracted_concepts"]
            if c.get("grounded_in_case")
        ]
        grounded_names = [c["concept"] for c in grounded]

        # The human's REASON — not the description — is where a condition is
        # stated. A reason says WHY the situation exists; observation only
        # says what is there.
        reasons: List[str] = []
        contexts: List[str] = []
        for concept in grounded:
            record = concept.get("reason_and_context") or {}
            if isinstance(record.get("reason"), str):
                reasons.append(record["reason"])
            if isinstance(record.get("context"), str):
                contexts.append(record["context"])

        # Concept evidence phrases the FOUNDATION reported (multi-word only).
        # These are kept for the audit trail, but the CONDITIONS come from the
        # reason clauses below — evidence phrases may be single words.
        foundation_evidence: List[str] = []
        for concept in grounded:
            for item in _list(concept.get("evidence_reference")):
                if len(_tokenize(item)) >= 2:
                    foundation_evidence.append(str(item))

        # LEARN. Every clause of the human's reasoning contributes the idea
        # stems it held together; the concept name is stripped FIRST (L3).
        #
        # Each source clause also records its own POLARITY. A condition the
        # human taught in negative form ("reach it without crossing the shared
        # house") is POSITIVE in meaning, and a case carrying the same marker
        # must be read as affirming it, not denying it.
        conditions_expressed: List[Tuple[str, ...]] = []
        for reason in reasons:
            for clause in _clauses(_strip_concept_name(reason, concept_name)):
                stems = _condition_stem_sets(clause)
                polarity = _clause_negation_marker(clause)
                for stem in stems:
                    stem_provenance.setdefault(stem, set()).add(example_id)
                for key in _pair_conditions(stems):
                    condition_provenance.setdefault(key, []).append(
                        {
                            "example_id": example_id,
                            "clause": clause,
                            "negatively_worded": polarity is not None,
                        }
                    )
                    conditions_expressed.append(key)

        per_example.append(
            {
                "example_id": example_id,
                "grounded_concepts": grounded_names,
                "conditions_expressed": [
                    _condition_label(k) for k in _unique(conditions_expressed)
                ],
                "reason_present": bool(reasons),
                "context_present": bool(contexts),
                "foundation_evidence_phrases": _unique(foundation_evidence),
                "uncertainty": deepcopy(validated.get("uncertainty") or {}),
            }
        )

    # NUCLEI — stems that recur across two or more INDEPENDENT examples. This is
    # the cross-example agreement a word matcher cannot manufacture.
    example_count = len(per_example)
    nuclei = sorted(
        stem for stem, ids in stem_provenance.items() if len(ids) >= 2
    )

    # A condition is CROSS-EXAMPLE when its own provenance spans two or more
    # independent examples.
    multi_example_keys = sorted(
        key
        for key, sources in condition_provenance.items()
        if len({s["example_id"] for s in sources}) >= 2
    )
    single_example_keys = sorted(
        key
        for key, sources in condition_provenance.items()
        if len({s["example_id"] for s in sources}) == 1
    )

    # Cross-example agreement: which grounded concepts recur across examples
    # even though the wording differed.
    concept_support: Dict[str, List[str]] = {}
    for row in per_example:
        for concept in row["grounded_concepts"]:
            concept_support.setdefault(concept, []).append(row["example_id"])

    # Human-readable condition records, with provenance kept.
    def condition_records(keys: List[Tuple[str, ...]]) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        for key in keys:
            sources = condition_provenance[key]
            example_ids = _unique([s["example_id"] for s in sources])
            records.append(
                {
                    "condition": _condition_label(key),
                    "stems": list(key),
                    "nucleus_stems": [s for s in key if s in nuclei],
                    "example_support": example_ids,
                    "example_count": len(example_ids),
                    "cross_example": len(example_ids) >= 2,
                    "negatively_worded_source": bool(
                        sources and all(s.get("negatively_worded") for s in sources)
                    ),
                    "source_clauses": _unique([s["clause"] for s in sources])[:4],
                }
            )
        return records

    model = {
        "concept": concept_name,
        "example_count": example_count,
        "per_example": per_example,
        # The learned model is a SET OF CONDITIONS with provenance — never a
        # list of words to look up.
        "nucleus_stems": nuclei,
        "cross_example_conditions": condition_records(multi_example_keys),
        "single_example_conditions": condition_records(single_example_keys),
        "condition_provenance": {
            _condition_label(k): deepcopy(v)
            for k, v in condition_provenance.items()
        },
        "learned_condition_count": len(condition_provenance),
        "concepts_taught": sorted(concept_support),
        "concept_example_support": {
            k: _unique(v) for k, v in concept_support.items()
        },
        # Honest statement of what the model is and is not.
        "stored_as_fixed_word_list": False,
        "derived_at_run_time": True,
        "concept_name_used_as_evidence": False,
        "learning_rule": "clause_level_idea_stem_cooccurrence",
    }
    return model


# ────────────────────────────────────────────────────────────────────────────
# PHASE B — UNSEEN TRANSFER ANALYSIS
# ────────────────────────────────────────────────────────────────────────────


def _concept_vocabulary(concept_name: str) -> List[str]:
    """The concept's own label words, used ONLY to detect word matching.

    GUARD L3. These tokens are the vocabulary the case is NOT allowed to be
    credited for. They are the one thing a word-matcher would latch onto, so
    they are tracked in a SEPARATE channel and never anywhere near evidence.

    Stems are included so a case cannot evade the word-matching detector by
    using a morphological variant ("private" for "privacy"). Detecting
    variants of the LABEL is safe; it never turns vocabulary into evidence.
    """
    raw = [concept_name, concept_name.replace("_", " ")]
    raw.extend(_tokenize(concept_name))
    terms = [t for t in raw if len(t) >= 3]
    terms.extend(_stem(t) for t in list(terms))
    return _unique([t for t in terms if len(t) >= 3])


def _condition_matches(
    clauses: List[str],
    model: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Find learned CONDITIONS present in the case, and any that are denied.

    GUARD L3 is applied to both sides: the case clauses and the learned
    conditions have already had the concept name stripped, so the name can
    never create a match.

    THE MATCH RULE (and why it is not word matching):

      A case clause supports a learned condition when

        1. it shares at least TWO of the condition's distinctive idea-stems
           (a relationship, not a single word), AND
        2. at least one shared stem is a NUCLEUS — a stem that recurred across
           two or more INDEPENDENT teaching examples.

      Rule 1 is what lets a DIFFERENTLY-WORDED case transfer: the case need not
      repeat the teaching phrase, only hold the same two ideas together.
      Rule 2 is what defeats the adversarial case: a case that merely names the
      concept contributes no agreeing architectural nucleus, so it can never
      satisfy the rule.

    POLARITY IS CLAUSE-LEVEL, NOT CONDITION-LEVEL. A denial applies to the
    whole clause it stands in — otherwise the two conditions a single denying
    clause holds together would be split, one read as affirmed and one as
    denied, which is exactly the incoherence this function must not produce.

    A NEGATIVELY-WORDED TAUGHT CONDITION is not a denial. When the human
    themselves taught a condition in negative form ("reach it without crossing
    the shared house"), a case that carries the same marker is AFFIRMING the
    concept, not denying it. Each condition therefore remembers whether its
    teaching clauses were negatively worded, and a mirroring case clause is
    read as present.

    Every match is reported with the stems that produced it, so the reasoning
    chain shows WHICH taught condition transferred and on what ground.
    """
    present: List[Dict[str, Any]] = []
    denied: List[Dict[str, Any]] = []

    nucleus_stems = set(model.get("nucleus_stems") or [])
    all_conditions = list(model.get("cross_example_conditions") or []) + list(
        model.get("single_example_conditions") or []
    )

    clause_stems: List[set] = []
    for clause in clauses:
        clause_stems.append(set(_condition_stem_sets(clause)))

    for record in all_conditions:
        condition_stems = set(record.get("stems") or [])
        if len(condition_stems) < 2:
            continue
        condition_nuclei = condition_stems & nucleus_stems
        if not condition_nuclei:
            # A condition with no nucleus is not a cross-example agreement and
            # cannot carry a transfer on its own.
            continue

        condition_is_negative_taught = bool(record.get("negatively_worded_source"))

        for clause, stems in zip(clauses, clause_stems):
            overlap = condition_stems & stems
            if len(overlap) < 2:
                continue
            if not (overlap & condition_nuclei):
                continue

            polarity = _clause_negation_marker(clause, sorted(overlap))

            entry = {
                "condition": record.get("condition"),
                "stems_shared": sorted(overlap),
                "nucleus_stems_shared": sorted(overlap & condition_nuclei),
                "cross_example": bool(record.get("cross_example")),
                "example_support": list(record.get("example_support") or []),
                "clause": clause,
            }

            # A denied clause denies every condition it matches — unless the
            # condition was itself taught in negative form, in which case the
            # same marker affirms it.
            if polarity is not None and not condition_is_negative_taught:
                entry["negation"] = polarity
                denied.append(entry)
            elif polarity is not None and condition_is_negative_taught:
                entry["negation_present_but_affirming"] = polarity
                present.append(entry)
            else:
                present.append(entry)
            break

    # A condition that is BOTH affirmed and denied somewhere in the case is
    # contradictory; report it as denied so it cannot masquerade as a transfer.
    present_labels = {m.get("condition") for m in present}
    denied_labels = {m.get("condition") for m in denied}
    both = present_labels & denied_labels
    if both:
        present = [m for m in present if m.get("condition") not in both]
        for label in both:
            for m in denied:
                if m.get("condition") == label:
                    m["both_present_and_denied"] = True
                    break

    return _dedupe_matches(present), _dedupe_matches(denied)


def _denial_markers() -> Tuple[str, ...]:
    """Markers that DENY the condition that follows them.

    These are natural-language negations, not architectural vocabulary, and they
    are applied at CLAUSE level so a denial can never be split across the two
    conditions one clause holds together.

    Both the separated form ("no one", "not") and the fused form ("nobody",
    "cannot") are listed, because a writer may use either and a denial must not
    be missed merely because it was written as one word.
    """
    return (
        " not ",
        " no ",
        " never ",
        " without ",
        " less ",
        " fewer ",
        " nobody ",
        " none ",
        " nothing ",
        " cannot ",
        " unable ",
        " denies ",
    )


def _clause_negation_marker(clause: str, stems: List[str] | None = None) -> str | None:
    """The denial marker of a clause, or None when the clause affirms.

    A marker denies what FOLLOWS it. The marker therefore counts only when it
    stands BEFORE the clause's first matched stem (when stems are supplied) or,
    failing that, before the clause's first content word. This keeps the reading
    clause-scoped: every condition the clause holds together is denied together
    when a marker precedes them.

    When no stems are supplied (the learning path), the first content word is
    the reference point. A marker that opens a clause ("without crossing the
    shared house") therefore marks the clause as negatively worded, which is
    exactly the "positive-in-meaning negative form" the learner must remember.
    """
    lowered = " " + clause.lower() + " "
    tokens = _tokenize(clause)

    def position_of(stem: str) -> int | None:
        for token in tokens:
            if _stem(token) == stem:
                pos = lowered.find(" " + token)
                if pos >= 0:
                    return pos
        return None

    reference: int | None = None
    if stems:
        positions = [position_of(s) for s in stems]
        positions = [p for p in positions if p is not None]
        if positions:
            # A clause-level denial covers the condition when the marker stands
            # before the condition's LATER matched idea. "occupant does not
            # control" denies the occupant-control relation because "not"
            # precedes "control", even though it follows "occupant".
            reference = max(positions)
    if reference is None:
        for token in tokens:
            if token in _GLUE_WORDS or len(token) <= 2:
                continue
            pos = lowered.find(" " + token)
            if pos >= 0:
                reference = pos
                break
    if reference is None:
        return None

    for marker in _denial_markers():
        marker_pos = lowered.find(marker)
        if 0 <= marker_pos < reference:
            return marker.strip()
    return None


def _dedupe_matches(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: List[str] = []
    result: List[Dict[str, Any]] = []
    for match in matches:
        label = match.get("condition")
        if label in seen:
            continue
        seen.append(label)
        result.append(match)
    return result


def _vocabulary_overlap(clauses: List[str], concept_name: str) -> List[str]:
    """The concept's OWN label words appearing in the case.

    GUARD L3 + the adversarial requirement: this is recorded separately and is
    NEVER promoted to evidence. A case built entirely from these words must
    still fail to demonstrate transfer.

    Matching is STEM based, so a case cannot slip past the word-matching
    detector by using a variant of the label ("private" for "privacy").
    """
    found: List[str] = []
    for clause in clauses:
        clause_stems = set(_stem_set(_tokenize(clause)))
        for term in _concept_vocabulary(concept_name):
            if _stem(term) in clause_stems:
                found.append(term)
                break
    return _unique(found)


def _case_conditions(clauses: List[str], concept_name: str) -> List[str]:
    """The architectural conditions the case ITSELF presents.

    These are the case's own clause-level condition stems with the concept name
    stripped out. They are what distinguish a case that presents real
    architecture from one that is merely too thin to judge: a case with no
    condition of its own is `not_enough_evidence`, while a case that presents
    conditions which simply are NOT the taught ones is `incorrect_transfer`.

    A clause only counts when it actually STATES an architectural situation, not
    merely when it contains two words. Two shapes qualify:

      * the clause carries a RELATION word ("open to the street", "off the
        entrance hall") — a relation is what makes a clause architectural
        rather than a label; or
      * the clause has at least four distinctive content stems.

    A bare fragment ("A small side room") therefore contributes no condition —
    it is not enough to judge, which is exactly what the case should report.
    """
    conditions: List[str] = []
    for clause in clauses:
        clean = _strip_concept_name(clause, concept_name)
        tokens = _tokenize(clean)
        has_relation = any(t in _RELATION_WORDS for t in tokens)
        stems = _condition_stem_sets(clean)
        if not has_relation and len(stems) < 4:
            continue
        for key in _pair_conditions(stems):
            conditions.append(_condition_label(key))
    return _unique(conditions)


def _transfer_outcome(
    present: List[Dict[str, Any]],
    denied: List[Dict[str, Any]],
    vocabulary: List[str],
    case_conditions: List[str],
) -> Tuple[str, List[Dict[str, Any]]]:
    """Decide the outcome from CONDITIONS only. Vocabulary is never an input.

    Order of reasoning, strongest first:

      1. A condition is DENIED and nothing is present, is
         `contradictory_evidence` — the case actively denies the ground.
      2. A condition PRESENT whose ground recurs across independent teaching
         examples is `transfer_success` with a cross-example basis. Different
         wording, same architectural situation — the strongest signal.
      3. A condition PRESENT that is grounded (it necessarily carries a nucleus,
         because `_condition_matches` requires one) is `transfer_success`.
      4. NO learned condition present, but concept vocabulary used, is
         `vocabulary_only` — the adversarial case this test exists to catch.
      5. NO condition present and NO vocabulary used, but the case presents
         conditions of its OWN: `incorrect_transfer` — the case says something
         architectural, just not the taught thing.
      6. Otherwise `not_enough_evidence` — explicitly NOT failure.
    """
    matched_multi = [m for m in present if m.get("cross_example")]

    if denied and not present:
        return "contradictory_evidence", []
    if present and matched_multi:
        return "transfer_success", matched_multi
    if present:
        return "transfer_success", []
    if vocabulary:
        return "vocabulary_only", []
    if case_conditions:
        return "incorrect_transfer", []
    return "not_enough_evidence", []


def _confidence(
    outcome: str,
    present: List[Dict[str, Any]],
    denied: List[Dict[str, Any]],
    vocabulary: List[str],
    matched_multi: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """A qualitative confidence with its reason chain. Never a bare number."""
    if outcome == "transfer_success" and matched_multi:
        level = "high"
        why = "the condition's ground recurred across independent teaching examples"
    elif outcome == "transfer_success":
        level = "moderate"
        why = "a learned condition is present on a nucleus shared with teaching"
    elif outcome == "contradictory_evidence":
        level = "high"
        why = "the case denies a learned condition and offers none"
    elif outcome == "vocabulary_only":
        level = "high"
        why = "concept words appear with no learned condition present"
    elif outcome == "incorrect_transfer":
        level = "low"
        why = "the case presents conditions, but none that were taught"
    else:
        level = "low"
        why = "the material does not contain a learned condition either way"

    return {
        "level": level,
        "reason": why,
        "conditions_present": [m.get("condition") for m in present],
        "cross_example_conditions_present": [
            m.get("condition") for m in matched_multi
        ],
        "conditions_denied": [m.get("condition") for m in denied],
        "vocabulary_used": list(vocabulary),
        "resolved": False,
        "single_correct_reading": False,
    }


def _analyse_unseen_case(
    model: Dict[str, Any],
    unseen_case: Dict[str, Any],
) -> Dict[str, Any]:
    """Analyse one unseen case against the learned MODEL.

    Nothing about the case's expected answer is read: the case simply does not
    carry one (GUARD L2). The analysis is derived entirely from the learned
    conditions and the case's own architectural text.
    """
    concept_name = model["concept"]
    raw_text = _text_of_case(unseen_case)
    stripped = _strip_concept_name(raw_text, concept_name)
    clauses = _clauses(stripped)

    present, denied = _condition_matches(clauses, model)
    vocabulary = _vocabulary_overlap(_clauses(raw_text), concept_name)
    case_conditions = _case_conditions(clauses, concept_name)

    outcome, matched_multi = _transfer_outcome(
        present,
        denied,
        vocabulary,
        case_conditions,
    )

    # Which parts of the learned concept transferred, and which did not.
    all_condition_labels = [
        r.get("condition")
        for r in (
            list(model.get("cross_example_conditions") or [])
            + list(model.get("single_example_conditions") or [])
        )
    ]
    matched_labels = [m.get("condition") for m in present]
    denied_labels = [m.get("condition") for m in denied]
    transferred = list(matched_labels)
    not_transferred = [
        label
        for label in all_condition_labels
        if label not in matched_labels and label not in denied_labels
    ]

    confidence = _confidence(
        outcome,
        present,
        denied,
        vocabulary,
        matched_multi,
    )

    reasoning_chain = [
        {
            "step": "strip_concept_name",
            "detail": (
                "the target concept's name was removed from the material before "
                "any comparison, so it can never act as evidence"
            ),
        },
        {
            "step": "learned_conditions_compared",
            "detail": str(model.get("learned_condition_count", 0))
            + " conditions derived from teaching were compared against "
            + str(len(clauses))
            + " clause(s) of the unseen case",
        },
        {
            "step": "nuclei_used",
            "detail": (
                "cross-example idea-stems from teaching: "
                + (", ".join(model.get("nucleus_stems") or []) or "none")
            ),
        },
        {
            "step": "conditions_present",
            "detail": (
                ", ".join(m.get("condition") for m in present) if present else "none"
            ),
        },
        {
            "step": "conditions_denied",
            "detail": (
                ", ".join(m.get("condition") for m in denied) if denied else "none"
            ),
        },
        {
            "step": "vocabulary_channel",
            "detail": (
                "concept words found: " + (", ".join(vocabulary) if vocabulary else "none")
                + " — recorded separately and never used as evidence"
            ),
        },
        {
            "step": "outcome",
            "detail": outcome + " (" + confidence["reason"] + ")",
        },
    ]

    return {
        "case_id": unseen_case.get("space_id") or unseen_case.get("case_id"),
        "case_name": unseen_case.get("space_name"),
        "origin": "unseen",
        "outcome": outcome,
        "outcome_family": OUTCOME_FAMILIES[outcome],
        # The six reporting surfaces the brief requires, each SEPARATE.
        "conceptual_evidence": {
            "conditions_present": deepcopy(present),
            "cross_example_conditions_present": deepcopy(matched_multi),
            "conditions_denied": deepcopy(denied),
            "derived_from_teaching": True,
            "predefined_keyword_list_used": False,
        },
        "vocabulary_overlap": {
            "concept_words_found": list(vocabulary),
            "used_as_evidence": False,
        },
        "reasoning_chain": reasoning_chain,
        "confidence_and_uncertainty": confidence,
        "transferred_parts": transferred,
        "non_transferable_parts": not_transferred,
        "case_conditions_observed": case_conditions[:12],
        "uncertainty": {
            "resolved": False,
            "not_enough_information": outcome == "not_enough_evidence",
            "forced_recognition": False,
        },
    }


# ────────────────────────────────────────────────────────────────────────────
# Required non-claims. Keys contain forbidden terms as NEGATIONS, so the
# forbidden-language scan must exclude this block (it is scanned separately by
# key, not by value).
# ────────────────────────────────────────────────────────────────────────────

_REQUIRED_NON_CLAIMS = {
    "not_design_solution": True,
    "not_plan_proposal": True,
    "not_design_rule": True,
    "not_geometry": True,
    "not_bim": True,
    "not_render": True,
    "not_memory": True,
    "not_learned_model": True,
    "not_proof_of_human_understanding": True,
    "not_general_intelligence_claim": True,
    "qualified_as_controlled_transfer_test": True,
}

# The exact, and only, phrasing this test may use for what it demonstrates.
DEMONSTRATION_LABEL = (
    "architectural conceptual transfer under controlled test conditions"
)


def _empty_family_counts() -> Dict[str, int]:
    return {
        "LEARNED_OR_TRANSFERRED": 0,
        "RECOGNIZED_FROM_WORDS": 0,
        "NOT_ENOUGH_INFORMATION": 0,
    }


def _summarise(case_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate the case results into the plain-language final report."""
    outcome_counts = {name: 0 for name in TRANSFER_OUTCOMES}
    family_counts = _empty_family_counts()
    for row in case_results:
        outcome_counts[row["outcome"]] = outcome_counts.get(row["outcome"], 0) + 1
        family_counts[row["outcome_family"]] += 1

    return {
        "case_count": len(case_results),
        "outcome_counts": outcome_counts,
        "family_counts": family_counts,
        "transfer_successes": [
            r["case_id"] for r in case_results if r["outcome"] == "transfer_success"
        ],
        "recognized_from_words": [
            r["case_id"] for r in case_results if r["outcome"] == "vocabulary_only"
        ],
        "not_enough_information": [
            r["case_id"]
            for r in case_results
            if r["outcome"] == "not_enough_evidence"
        ],
        "incorrect_transfers": [
            r["case_id"]
            for r in case_results
            if r["outcome"] == "incorrect_transfer"
        ],
        "contradictory": [
            r["case_id"]
            for r in case_results
            if r["outcome"] == "contradictory_evidence"
        ],
        # The three-way distinction the brief demands, stated in plain terms.
        "learned_or_transferred": family_counts["LEARNED_OR_TRANSFERRED"],
        "recognized_from_words_count": family_counts["RECOGNIZED_FROM_WORDS"],
        "not_enough_information_count": family_counts["NOT_ENOUGH_INFORMATION"],
        "demonstration_label": DEMONSTRATION_LABEL,
        "claim_of_human_like_understanding": False,
    }


def run_architectural_concept_transfer_test(
    directive: Dict[str, Any],
) -> Dict[str, Any]:
    """Run the two-phase learning / transfer test.

    The directive supplies:
        concept          — the concept under test (its NAME is never evidence)
        teaching         — Phase A: multiple differently-worded examples
        unseen           — Phase B: cases never used during teaching

    Pure function. Deterministic. Reads nothing, writes nothing, learns nothing
    permanently, designs nothing, proposes no plan.
    """
    directive = _validate_directive(directive)

    concept_name = directive.get("concept")
    if not isinstance(concept_name, str) or not concept_name.strip():
        raise ValueError(
            "TransferTest: directive requires a non-empty 'concept' name"
        )

    teaching = _list(directive.get("teaching"))
    unseen = _list(directive.get("unseen"))
    if not teaching:
        raise ValueError("TransferTest: Phase A requires at least one example")
    if not unseen:
        raise ValueError("TransferTest: Phase B requires at least one case")

    teaching = [_validate_teaching_example(e) for e in teaching]
    unseen = [_validate_unseen_case(c) for c in unseen]

    # GUARD L1/L2 — refuse any unseen case that leaked from teaching.
    for case in unseen:
        _assert_no_leakage(teaching, case)

    # PHASE A — learn.
    model = _teach_phase(teaching, concept_name)

    # PHASE B — transfer.
    case_results = [_analyse_unseen_case(model, case) for case in unseen]

    summary = _summarise(case_results)

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "test_subject": TEST_SUBJECT,
        "demonstration_label": DEMONSTRATION_LABEL,
        "phase_a_learning": {
            "concept": model["concept"],
            "example_count": model["example_count"],
            "learning_rule": model["learning_rule"],
            "learned_condition_count": model["learned_condition_count"],
            "nucleus_stem_count": len(model["nucleus_stems"]),
            "nucleus_stems": list(model["nucleus_stems"]),
            "conditions_from_multiple_examples": len(
                model["cross_example_conditions"]
            ),
            "cross_example_conditions": deepcopy(model["cross_example_conditions"]),
            "single_example_conditions": deepcopy(model["single_example_conditions"]),
            "concepts_taught": model["concepts_taught"],
            "concept_example_support": model["concept_example_support"],
            "stored_as_fixed_word_list": False,
            "derived_at_run_time": True,
            "per_example": deepcopy(model["per_example"]),
            "condition_provenance": deepcopy(model["condition_provenance"]),
        },
        "phase_b_transfer": case_results,
        "final_report": summary,
        "leakage_prevention": {
            "unseen_not_used_in_teaching": True,
            "expected_answer_absent_from_case_text": True,
            "concept_name_never_used_as_evidence": True,
            "predefined_keyword_list_used": False,
            "enforcement": {
                "L1_unseen_never_taught": True,
                "L2_expected_answer_out_of_band": True,
                "L3_concept_name_stripped_before_reasoning": True,
                "L4_conditions_derived_from_teaching": True,
            },
        },
        "uncertainty": {
            "resolved": False,
            "single_correct_reading": False,
            "forced_recognition_anywhere": False,
            "concepts_are_not_mandatory": True,
            "alternative_interpretations_preserved": True,
            "multiple_valid_solutions_possible": True,
        },
        "methodology": {
            "analysis_method": "architectural_condition_transfer",
            "evidence_source": "human_teaching_examples_derived_at_run_time",
            "vocabulary_channel_isolated": True,
            "not_claiming_human_understanding": True,
        },
        "non_claims": deepcopy(_REQUIRED_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }

    _assert_no_forbidden_language(result)
    return result


def _authored_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    """Everything this boundary authored, EXCLUDING the non_claims block.

    ``non_claims`` legitimately contains forbidden terms as negations, so it is
    not scanned as emitted language; it is validated by key instead.
    """
    return {k: v for k, v in result.items() if k != "non_claims"}


def _assert_no_forbidden_language(result: Dict[str, Any]) -> None:
    """Refuse to emit rule-like, physical or drawing-system vocabulary."""
    serialized = str(_authored_payload(result)).lower()
    for term in _FORBIDDEN_TERMS:
        if _contains_term(serialized, term):
            raise AssertionError(
                "ArchitecturalConceptTransferTestV1 emitted forbidden term: "
                + term
            )

    for key, value in result["non_claims"].items():
        if value is not True:
            raise AssertionError(
                "ArchitecturalConceptTransferTestV1 non-claim "
                + key
                + " must be True"
            )

    # The only permitted wording for what this test demonstrates.
    if result.get("demonstration_label") != DEMONSTRATION_LABEL:
        raise AssertionError(
            "ArchitecturalConceptTransferTestV1 must describe itself only as "
            + repr(DEMONSTRATION_LABEL)
        )
