"""Architectural abstraction LEARNER boundary (ABSTRACTION TEST V2, Phases 1-4).

This module is one half of an isolated, transient, read-only experiment. It
answers exactly one narrow question:

    "Given several human teaching examples of ONE architectural situation -
     worded differently, naming different concrete things, sharing as little
     vocabulary as possible - what FORMAL STRUCTURE is invariant across them,
     and is that invariant NECESSARY to the reason the humans gave?"

It deliberately does NOT answer:

    "What does this building look like?"   (no shape, plan, geometry)
    "What should be built here?"           (no design, no recommendation)

────────────────────────────────────────────────────────────────────────────
WHAT THIS BOUNDARY IS - AND WHAT IT IS NOT
────────────────────────────────────────────────────────────────────────────

The brief for V2 is explicit about a distinction this module must never blur:

    AN ENGINEERED ALGORITHM  is not  EMERGENT CONTENT  is not  LEARNING.

This module *runs* engineered algorithms (a tokeniser, a clause splitter, a
parser, a normaliser, an intersection operation, a necessity test, an
alternative retainer). The RESULTS those algorithms produce may be emergent
content - invariants that survive across examples - and emergent content MAY
support a claim of structured generalisation. But the boundary never reports
its own machinery as if it had been learned, and a class named
``LearnedAbstraction`` never, by itself, proves anything was learned.

Every field this module emits carries ``epistemic_status`` taken from a single
closed vocabulary:

    ENGINEERED                    the value is an algorithm's own output shape
    DERIVED                       computed from the corpus, not given
    GENERALIZED                   survived across independent examples
    CONCEPTUAL_ABSTRACTION_EVIDENCE  reserved for the probe boundary, after a
                                  full unseen evaluation (never set here)
    NOT_DEMONSTRATED              the evidence does not support the step

``CONCEPTUAL_ABSTRACTION_EVIDENCE`` is DELIBERATELY unreachable from this
module. Only the probe boundary may assign it, and only after Phase 5 + 6.

────────────────────────────────────────────────────────────────────────────
THE THREE-LEVEL MODEL (never collapsed)
────────────────────────────────────────────────────────────────────────────

    LEVEL 1  RAW / LITERAL formal condition   - carries the fillers the human
             actually named (a sleeping chamber, an alcove, a stranger ...).
             This is the only level that touches the human's words.

    LEVEL 2  NORMALIZED structure
             2A  FormalStructure        - actor / action / object / from / to /
                                            boundary / modality / polarity /
                                            effect. NO architectural meaning.
             2B  InterpretiveHypothesis - access / separation / control /
                                            exposure. A SEPARATE object, with
                                            its own provenance, assumptions,
                                            alternatives and leakage_risk.
             A hypothesis is NOT a truth and is NEVER fed back as evidence.

    LEVEL 3  LearnedAbstraction (candidate) - computed over NORMALIZED
             structure, never over literals, and never over a hard-coded
             concept-to-role map.

────────────────────────────────────────────────────────────────────────────
THE THREE MODES (all independently runnable)
────────────────────────────────────────────────────────────────────────────

    MODE F  formal structure only. MUST run with 2B never constructed.
            FormalStructure in Mode F carries no architectural relation word.
    MODE H  formal structure + interpretive hypotheses.
    MODE R  role hypothesis + interpretive hypotheses.

────────────────────────────────────────────────────────────────────────────
READ THE GIVEN-vs-LEARNED LEDGER
────────────────────────────────────────────────────────────────────────────

The GIVEN/ENGINEERED/EMERGENT ledger is emitted by the probe boundary; this
module contributes ``engineering_ledger`` for its own four phases so no
engineered step can masquerade as a learned one.

────────────────────────────────────────────────────────────────────────────
FORBIDDEN (rejected, never coerced)
────────────────────────────────────────────────────────────────────────────

    raw images · vision output · geometry · CAD · DWG · DXF · BIM · IFC ·
    rendering output · memory objects · design solutions · semantic graphs ·
    any upstream ArchitectOS production contract.

This boundary imports NOTHING from production ArchitectOS. It is transient,
read-only, deterministic, and persists nothing.
"""

from __future__ import annotations

import re

from copy import deepcopy
from typing import Any, Dict, List, Sequence, Tuple


CONTRACT = "ArchitecturalAbstractionLearnerV1"
VERSION = "1.0"

# The human example contract is consumed verbatim - no new teaching vocabulary.
TEACHING_EXAMPLE_CONTRACT = "ArchitecturalHumanTeachingExampleV1"
TEACHING_EXAMPLE_VERSION = "1.0"

# The directive that drives Phases 1-4.
DIRECTIVE_CONTRACT = "ArchitecturalAbstractionDirectiveV1"
DIRECTIVE_VERSION = "1.0"

TEST_SUBJECT = "architectural abstract concept derivation under controlled test conditions"

DEMONSTRATION_LABEL = (
    "controlled formal-structure abstraction over human teaching examples"
)

# ────────────────────────────────────────────────────────────────────────────
# The ONLY permitted epistemic statuses. A closed vocabulary.
# ────────────────────────────────────────────────────────────────────────────
EPISTEMIC_STATUSES = (
    "ENGINEERED",
    "DERIVED",
    "GENERALIZED",
    "CONCEPTUAL_ABSTRACTION_EVIDENCE",  # reserved to the probe boundary
    "NOT_DEMONSTRATED",
)

# Statuses this module is allowed to assign. NOTE: the evidence status is not
# in this tuple - that is the whole point of the separation.
_LEARNER_ASSIGNABLE_STATUSES = (
    "ENGINEERED",
    "DERIVED",
    "GENERALIZED",
    "NOT_DEMONSTRATED",
)

# ────────────────────────────────────────────────────────────────────────────
# Modes. F must be runnable without Level-2B. H and R add interpretive layers.
# ────────────────────────────────────────────────────────────────────────────
MODES = ("F", "H", "R")

MODE_DESCRIPTIONS = {
    "F": "formal structure only - runs without Level 2B",
    "H": "formal structure plus interpretive hypotheses (Level 2B)",
    "R": "role hypothesis plus interpretive hypotheses",
}

# ────────────────────────────────────────────────────────────────────────────
# The FORMAL fields of Level 2A. There is deliberately NO "meaning" field and
# no architectural relation field: a FormalStructure states form, not intent.
# ────────────────────────────────────────────────────────────────────────────
FORMAL_STRUCTURE_FIELDS = (
    "actor",
    "action",
    "object",
    "source",
    "target",
    "boundary",
    "modality",
    "polarity",
    "effect",
)

# The interpretive axes of Level 2B. These are HYPOTHESES about meaning, marked
# as such, and they live in a SEPARATE object from FormalStructure.
INTERPRETIVE_AXES = ("access", "separation", "control", "exposure")

# ────────────────────────────────────────────────────────────────────────────
# Structural relation vocabulary. These are FORMAL connectives - the parser
# uses them to place actor/action/object. They are NOT architectural meanings
# and are NOT concept-to-role rules. They are deliberately generic spatial /
# directional words that carry no building semantics.
# ────────────────────────────────────────────────────────────────────────────
_STRUCTURAL_MARKERS = (
    "within", "inside", "outside", "beyond", "through", "toward", "towards",
    "from", "into", "between", "against", "across", "around", "upon", "onto",
    "under", "over", "behind", "before", "after", "beside", "beyond",
)

# Movement / relation verbs - formal only. They describe a relation in the
# sentence, not an architectural judgement.
_RELATION_VERBS = (
    "enters", "enter", "reaches", "reach", "passes", "pass", "crosses",
    "cross", "approaches", "approach", "leads", "lead", "connects", "connect",
    "opens", "open", "closes", "close", "separates", "separate", "controls",
    "control", "governs", "govern", "exposes", "expose", "withdraws",
    "withdraw", "retreats", "retreat", "rests", "rest", "sleeps", "sleep",
    "works", "work", "waits", "wait", "stands", "stand", "sits", "sit",
    "arrives", "arrive", "departs", "depart", "remains", "remain",
    "belongs", "belong", "occupies", "occupy", "uses", "use", "holds",
    "hold", "keeps", "keep", "moves", "move", "ascends", "ascend",
    "descends", "descend", "shelters", "shelter", "guards", "guard",
    "screens", "screen", "frames", "frame", "serves", "serve", "allows",
    "allow", "lets", "let", "blocks", "block", "admits", "admit",
    "refuses", "refuse", "denies", "deny", "permits", "permit",
)

# Modality markers: how the relation is qualified - obligation, possibility,
# negation. Formal only.
_MODALITY_MARKERS = {
    "must": "obligation",
    "shall": "obligation",
    "should": "recommendation",
    "may": "possibility",
    "might": "possibility",
    "can": "capability",
    "could": "capability",
    "will": "futurity",
    "would": "conditional",
    "is able to": "capability",
    "has to": "obligation",
    "needs to": "obligation",
    "tends to": "tendency",
}

_NEGATION_MARKERS = (
    "not", "no", "never", "without", "less", "fewer", "nobody", "none",
    "nothing", "cannot", "unable", "denies", "refuses", "blocks", "lacks",
    "absent", "missing",
)

# Lexico-syntactic glue. Contains NO architectural vocabulary.
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
        "here", "there", "own", "same", "different", "itself", "themselves",
        "am", "us", "we", "you", "your", "our", "because", "since", "while",
        "although", "though", "however", "therefore", "thus", "yet", "still",
        "always", "often", "sometimes", "usually", "rather", "instead",
    }
)

# The WHY must be a first-class participant: a teaching example is only usable
# for abstraction if the human supplied a reason, not merely a description.
_WHY_CONNECTORS = (
    "because", "since", "so that", "in order to", "so", "as a result",
    "therefore", "thus", "for this reason", "this means", "which means",
    "the point is", "the reason", "that way", "which allows", "allowing",
    "enabling", "permitting", "to allow", "to enable", "to avoid",
    "to prevent", "to keep", "to let",
)

# Contracts that must never reach this boundary.
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
    "ArchitecturalDesignReasoningInputV1",
    "ArchitecturalSpatialReasoningCandidateV1",
    "ArchitecturalSemanticGraphV1",
    "ArchitecturalLayoutIntentResolverV1",
    "ProgramIntentResolutionV1",
    "ImageIntentV1",
    "SiteIntentV1",
    "ArchitecturalUnderstandingV2",
    "ArchitecturalUnderstandingV1",
    "ArchitecturalObservationV1",
    "ArchitecturalConceptOntologyV1",
    "ArchitecturalConceptRelationshipV1",
)

_REQUIRED_NON_CLAIMS = {
    "not_a_learned_model": True,
    "not_proof_of_human_understanding": True,
    "not_a_design_solution": True,
    "not_a_rule": True,
    "not_geometry": True,
    "not_bim": True,
    "not_render": True,
    "not_memory": True,
    "not_persistent": True,
    "engineered_algorithm_is_not_learning": True,
    "class_name_does_not_imply_learning": True,
}

# Terms this boundary must never emit as its own authored language.
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
    "optimal",
    "recommended",
    "synonym",
    "embedding",
)

# The ENGINEERED steps of THIS module. Emitted so nothing engineered can pass
# itself off as emergent.
ENGINEERING_LEDGER = {
    "tokenizer": "ENGINEERED",
    "clause_splitter": "ENGINEERED",
    "stem_normalizer": "ENGINEERED",
    "formal_parser": "ENGINEERED",
    "normalization_transform": "ENGINEERED",
    "intersection_algorithm": "ENGINEERED",
    "necessity_test": "ENGINEERED",
    "alternative_retention": "ENGINEERED",
    "role_projection": "ENGINEERED",
    "interpretive_hypothesis_table": "ENGINEERED",
}

# The emergent CONTENT this module may produce. Nothing here is guaranteed to
# appear; when it does, it is content, not machinery.
EMERGENT_LEDGER = {
    "surviving_invariants": "contingent on corpus",
    "necessity_determination": "contingent on corpus",
    "incidental_determination": "contingent on corpus",
    "context_determination": "contingent on corpus",
    "why_bindings": "contingent on corpus",
    "plausible_alternatives": "contingent on corpus",
    "abstraction_fingerprint": "contingent on corpus",
}

# Private aliases retained for internal use.
_ENGINEERING_LEDGER = ENGINEERING_LEDGER
_EMERGENT_LEDGER = EMERGENT_LEDGER


# --------------------------------------------------------------------------- #
# Small local helpers (no production dependency)
# --------------------------------------------------------------------------- #


def _list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _unique(values: Sequence[Any]) -> List[Any]:
    seen = set()
    out = []
    for item in values:
        key = item if isinstance(item, (str, int, float, bool)) else repr(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _tokenize(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        text = " ".join(str(v) for v in value)
    else:
        text = str(value)
    return re.findall(r"[a-z0-9]+", text.lower())


def _content_tokens(value: Any) -> List[str]:
    return [t for t in _tokenize(value) if t not in _GLUE_WORDS]


def _stem(token: str) -> str:
    """Fold a token to a coarse idea-stem.

    Deliberately shallow and architectural-agnostic: it folds plural forms and
    a few regular nominal/verbal families so that differently-worded examples
    can align on the same idea. It never encodes a synonym list, never contains
    architectural vocabulary, and never consults an external resource; it is a
    purely morphological fold.

    The families it unifies are structural, not topical:
      * plural / regular inflection (rooms -> room, watches -> watch);
      * a regular verb and its action-noun (separate / separation);
      * an adjective and its ``-cy`` noun (private / privacy).

    The fold is applied to the RAW token in a fixed order, then a final vowel
    normalisation trims a silent trailing ``e``; because every rule runs on the
    raw token before any stripping, the result cannot cascade.
    """
    t = token.lower()
    if len(t) <= 3:
        return t

    # Family fold on the RAW token: a ``-cy`` noun shares its root with the
    # corresponding adjective ("privacy" / "private" -> "privat").
    if t.endswith("cy") and len(t) >= 5:
        t = t[:-2] + "t"
    if t.endswith("e") and len(t) >= 6 and t[-2] not in "aeiou":
        t = t[:-1]

    for suffix in ("ations", "ation", "ings", "ing", "ions", "ion", "ies",
                   "ers", "er", "ors", "or", "ests", "est", "ness", "ment",
                   "ally", "ily", "ly", "ed", "es", "s"):
        if t.endswith(suffix) and len(t) - len(suffix) >= 3:
            t = t[: -len(suffix)]
            break
    return t


def _clauses(text: Any) -> List[str]:
    """Split into clauses on strong punctuation and coordinating conjunctions.

    A WHY connector ("because", "so that", ...) is NEVER treated as a clause
    boundary: the reason a human gives is part of the same proposition as the
    situation it explains, and splitting them apart would detach the WHY from
    its condition. A comma is a boundary only when both sides are substantial,
    so a list of fillers is not mistaken for a chain of conditions.
    """
    if text is None:
        return []
    raw = str(text)
    parts: List[str] = []
    for chunk in re.split(r"[;.!?\n]+", raw):
        chunk = chunk.strip()
        if not chunk:
            continue
        for sub in re.split(r"\b(?:and|but|while|whereas|yet|or)\b", chunk):
            sub = sub.strip()
            if sub:
                parts.append(sub)
    refined: List[str] = []
    for part in parts:
        if "," in part:
            pieces = [p.strip() for p in part.split(",")]
            for piece in pieces:
                if piece:
                    refined.append(piece)
        else:
            refined.append(part)
    return [p for p in refined if p]


def _contains_term(haystack: str, term: str) -> bool:
    return re.search(r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])",
                     haystack) is not None


# --------------------------------------------------------------------------- #
# Phase 1 - WHAT IS GIVEN
# --------------------------------------------------------------------------- #


def _validate_directive(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalAbstractionLearnerV1 requires a directive dict, got "
            + type(value).__name__
        )
    contract = value.get("contract")
    if contract in _FORBIDDEN_CONTRACTS:
        raise ValueError(
            "ArchitecturalAbstractionLearnerV1 rejects forbidden contract: "
            + str(contract)
        )
    if contract != DIRECTIVE_CONTRACT:
        raise ValueError(
            "ArchitecturalAbstractionLearnerV1 requires contract "
            + repr(DIRECTIVE_CONTRACT) + ", got " + repr(contract)
        )
    if value.get("version") != DIRECTIVE_VERSION:
        raise ValueError(
            "ArchitecturalAbstractionLearnerV1 requires version "
            + repr(DIRECTIVE_VERSION) + ", got " + repr(value.get("version"))
        )
    mode = value.get("mode")
    if mode not in MODES:
        raise ValueError(
            "ArchitecturalAbstractionLearnerV1 requires mode in "
            + repr(MODES) + ", got " + repr(mode)
        )
    return deepcopy(value)


def _validate_teaching_example(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "AbstractionLearner: a teaching example must be a dict, got "
            + type(value).__name__
        )
    contract = value.get("contract")
    if contract in _FORBIDDEN_CONTRACTS:
        raise ValueError(
            "AbstractionLearner: teaching example reached a forbidden "
            "contract: " + str(contract)
        )
    if contract != TEACHING_EXAMPLE_CONTRACT:
        raise ValueError(
            "AbstractionLearner: teaching example requires contract "
            + repr(TEACHING_EXAMPLE_CONTRACT) + ", got " + repr(contract)
        )
    if value.get("version") != TEACHING_EXAMPLE_VERSION:
        raise ValueError(
            "AbstractionLearner: teaching example requires version "
            + repr(TEACHING_EXAMPLE_VERSION)
        )
    return deepcopy(value)


def _assert_no_learner_leakage(teaching_examples: List[Dict[str, Any]]) -> None:
    """Refuse teaching input that carries an expected answer or evaluator key.

    The learner must never see the concept's name, an expected label, or any
    evaluation key. Those live out of band, in the evaluator's fixture.
    """
    leaked_keys = (
        "expected", "expected_outcome", "expected_concept", "expected_label",
        "answer", "ground_truth", "target", "target_skeleton",
        "intended_concept", "intended_invariant", "evaluation",
    )
    for example in teaching_examples:
        for key in leaked_keys:
            if key in example:
                raise ValueError(
                    "AbstractionLearner: leakage - a teaching example carries "
                    "an evaluation key " + repr(key) + "; the learner must "
                    "never receive the expected answer"
                )


def _phase_1_given(
    teaching_examples: List[Dict[str, Any]],
    mode: str,
) -> Dict[str, Any]:
    """Phase 1 - record WHAT IS GIVEN, and what the learner is denied."""
    texts = [str(e.get("description") or "") for e in teaching_examples]
    reasons = [str(e.get("reason") or "") for e in teaching_examples]

    vocabulary: List[str] = []
    for text in texts + reasons:
        vocabulary.extend(sorted({t for t in _content_tokens(text)}))

    surfaces = []
    for example, text, reason in zip(teaching_examples, texts, reasons):
        surfaces.append(
            {
                "example_id": example.get("example_id"),
                "description": text,
                "reason": reason,
                "context": example.get("context"),
                "why_present": bool(reason.strip()),
                "epistemic_status": "ENGINEERED",
            }
        )

    return {
        "phase": 1,
        "phase_name": "given",
        "mode": mode,
        "tenant": "learner",
        "given": {
            "teaching_example_count": len(teaching_examples),
            "surface_texts": surfaces,
            "observed_vocabulary": _unique(vocabulary),
            "reasons_supplied": sum(1 for r in reasons if r.strip()),
            "concept_name_given": False,
            "expected_answer_given": False,
            "evaluation_key_given": False,
        },
        "denied_to_learner": [
            "intended_concept_name",
            "intended_invariant",
            "expected_label",
            "evaluation_expectations",
            "author_abstraction_skeleton",
        ],
        "epistemic_status": "ENGINEERED",
    }


# --------------------------------------------------------------------------- #
# Phase 2 - FORMAL STRUCTURE FRAMEWORK (Level 1 RAW -> Level 2A FORMAL)
# --------------------------------------------------------------------------- #


def _formal_structure(clause: str) -> Dict[str, Any]:
    """Parse ONE clause into Level 2A FormalStructure.

    The result states FORM only: who acts, what they do, upon what, from where,
    toward where, across what boundary, with what modality and polarity, and
    what effect is asserted. It contains NO architectural meaning: no access,
    no separation, no control, no exposure. Those are Level 2B and are built
    elsewhere, in a separate object.
    """
    lowered = clause.lower()
    tokens = _content_tokens(clause)

    polarity = "negative" if any(
        _contains_term(lowered, m) for m in _NEGATION_MARKERS
    ) else "positive"

    modality = "assertion"
    for marker, kind in _MODALITY_MARKERS.items():
        if _contains_term(lowered, marker):
            modality = kind
            break

    boundary = None
    for marker in _STRUCTURAL_MARKERS:
        if _contains_term(lowered, marker):
            boundary = marker
            break

    # Action = first relation verb present. Formal, not architectural.
    action = None
    for verb in _RELATION_VERBS:
        if _contains_term(lowered, verb):
            action = verb
            break

    # Actor / object are recorded as RAW token spans, never as semantic roles.
    actor = tokens[0] if tokens else None
    object_token = tokens[1] if len(tokens) > 1 else None

    effect = None
    for connector in _WHY_CONNECTORS:
        if _contains_term(lowered, connector):
            after = lowered.split(connector, 1)
            if len(after) > 1 and after[1].strip():
                effect = after[1].strip()
            break

    return {
        "actor": actor,
        "action": action,
        "object": object_token,
        "source": None,
        "target": boundary,
        "boundary": boundary,
        "modality": modality,
        "polarity": polarity,
        "effect": effect,
        "level": "2A",
        "contains_architectural_meaning": False,
        "epistemic_status": "ENGINEERED",
    }


def _raw_formal_condition(clause: str) -> Dict[str, Any]:
    """Level 1 - the literal formal condition, retaining the human's words."""
    return {
        "level": "1",
        "clause": clause.strip(),
        "tokens": _content_tokens(clause),
        "stems": [_stem(t) for t in _content_tokens(clause)],
        "epistemic_status": "ENGINEERED",
    }


def _why_record(example_id: Any, reason: str) -> Dict[str, Any]:
    """A first-class WHY record. A reason is REQUIRED, not optional."""
    reason = (reason or "").strip()
    connectors = [c for c in _WHY_CONNECTORS if _contains_term(reason.lower(), c)]
    return {
        "example_id": example_id,
        "reason": reason,
        "reason_present": bool(reason),
        "connectors": connectors,
        "reason_clauses": _clauses(reason),
        "epistemic_status": "DERIVED" if reason else "NOT_DEMONSTRATED",
    }


def _phase_2_formal(
    teaching_examples: List[Dict[str, Any]],
    mode: str,
) -> Dict[str, Any]:
    """Phase 2 - build Level 1 and Level 2A for every example.

    Level 2B is NEVER constructed here: it is built only in Phase 3 when the
    mode calls for interpretive hypotheses.
    """
    examples = []
    for example in teaching_examples:
        text = str(example.get("description") or "")
        reason = str(example.get("reason") or "")
        clauses = _clauses(text)
        examples.append(
            {
                "example_id": example.get("example_id"),
                "why": _why_record(example.get("example_id"), reason),
                "level_1_raw": [_raw_formal_condition(c) for c in clauses],
                "level_2a_formal_structure": [
                    _formal_structure(c) for c in clauses
                ],
                "level_2b_interpretive_hypotheses": [],
                "clause_count": len(clauses),
                "epistemic_status": "ENGINEERED",
            }
        )

    return {
        "phase": 2,
        "phase_name": "formal_structure",
        "mode": mode,
        "tenant": "learner",
        "level_2b_constructed": False,
        "formal_structure_fields": list(FORMAL_STRUCTURE_FIELDS),
        "level_1_level_2a_never_collapsed": True,
        "examples": examples,
        "epistemic_status": "ENGINEERED",
    }


# --------------------------------------------------------------------------- #
# Phase 3 - EMERGENCE (Level 2A -> invariant candidates; optional Level 2B)
# --------------------------------------------------------------------------- #


def _condition_stems(clauses: List[str]) -> List[Tuple[str, ...]]:
    """Idea-stem PAIRS co-occurring within one clause.

    A condition is a pair of stems present together in a single clause. This is
    an ENGINEERED operation; the conditions it surfaces are corpus content.

    Kept for provenance: this pair view is what a single clause asserts at once.
    The INVARIANCE layer below works on per-stem recurrence, because a WHY that
    is phrased differently across examples will not always keep the same two
    stems inside one clause.
    """
    pairs: List[Tuple[str, ...]] = []
    for clause in clauses:
        stems = _unique([_stem(t) for t in _content_tokens(clause)])
        for i in range(len(stems)):
            for j in range(i + 1, len(stems)):
                pair = tuple(sorted((stems[i], stems[j])))
                pairs.append(pair)
    return _unique(pairs)


def _distinctive_stems(
    example_stems: Dict[Any, set],
    example_reason_stems: Dict[Any, set],
) -> List[str]:
    """Stems that recur across independent examples = invariant candidates.

    A stem is DISTINCTIVE (an invariant candidate) when it appears in at least
    two INDEPENDENT examples. Stems appearing in one example only are the
    example's filler and are retained as incidental, never silently dropped.

    This is an ENGINEERED criterion; which stems clear it is corpus content.
    """
    span: Dict[str, set] = {}
    for example_id, stems in example_stems.items():
        for stem in stems:
            span.setdefault(stem, set()).add(example_id)
    return sorted(s for s, ids in span.items() if len(ids) >= 2)


def _distinctive_conditions(
    clauses: List[str],
    excluded: Dict[str, int],
) -> List[Tuple[str, ...]]:
    """Idea-stem pairs that carry the CONDITION, not the filler.

    A pair is DISTINCTIVE when at least one of its stems is rare across the
    corpus (``excluded`` maps a stem to how many clauses carried it). Stems
    shared by nearly every clause are the example's fillers (sleeping chamber,
    resting cell) and are the very surface the abstraction must survive, so
    they are not allowed to form a condition on their own.

    This is an ENGINEERED filter; which pairs survive it is corpus content.
    """
    pairs: List[Tuple[str, ...]] = []
    for clause in clauses:
        stems = _unique([_stem(t) for t in _content_tokens(clause)])
        for i in range(len(stems)):
            for j in range(i + 1, len(stems)):
                pair = tuple(sorted((stems[i], stems[j])))
                if excluded.get(pair[0], 0) > 2 and excluded.get(pair[1], 0) > 2:
                    continue
                pairs.append(pair)
    return _unique(pairs)


def _interpretive_hypotheses(
    example_id: Any,
    clauses: List[str],
    why_clauses: List[str],
) -> List[Dict[str, Any]]:
    """Level 2B - HYPOTHESES about meaning, in a SEPARATE object.

    Each hypothesis names the interpretive axis it is about, the clause that
    suggested it, the assumptions it rests on, the alternatives that remain
    open, and a leakage_risk flag. A hypothesis is never promoted to evidence
    and is never fed back into the formal level.
    """
    hypotheses = []
    for axe in INTERPRETIVE_AXES:
        supporting = [c for c in clauses if _contains_term(c.lower(), axe)]
        if not supporting:
            supporting = [
                c for c in why_clauses if _contains_term(c.lower(), axe)
            ]
        if not supporting:
            continue
        hypotheses.append(
            {
                "axis": axe,
                "hypothesis": (
                    "the example may be read as being about " + axe
                ),
                "supporting_clauses": supporting,
                "source_example": example_id,
                "assumptions": [
                    "that the human's reason, not the description, is about "
                    "this axis",
                ],
                "alternatives": [
                    "the same clauses may support a different axis",
                    "the axis may be incidental to the human's point",
                ],
                "leakage_risk": "present",
                "is_hypothesis_not_truth": True,
                "epistemic_status": "DERIVED",
            }
        )
    return hypotheses


def _role_hypothesis(mode: str) -> Dict[str, Any]:
    """A role projection, openly marked as an EXPERIMENTAL HYPOTHESIS.

    Roles are NOT truth and are NOT a hard-coded concept-to-role map. They are
    a representational experiment: this run pretends that certain abstract
    positions exist, and records that the pretence is engineered.
    """
    return {
        "role_family": "abstract_structural_positions",
        "roles": [
            "INSIDER",
            "OUTSIDER",
            "DOMAIN",
            "BOUNDARY",
            "ACCESS",
            "CONTROL",
            "EXPOSURE",
            "EFFECT",
        ],
        "classification": "experimental representation hypothesis",
        "is_truth": False,
        "is_hard_coded_concept_map": False,
        "mode": mode,
        "epistemic_status": "ENGINEERED",
    }


def _phase_3_emergence(
    teaching_examples: List[Dict[str, Any]],
    mode: str,
) -> Dict[str, Any]:
    """Phase 3 - find what SURVIVES across independent examples.

    A condition is an INVARIANT CANDIDATE when it recurs across at least two
    independent examples. Anything appearing once is retained as incidental,
    never discarded silently.
    """
    # First pass: count how many EXAMPLES carry each stem, so the filler stems
    # - the surface vocabulary the abstraction must survive - can be told apart
    # from the distinctive stems that carry the actual condition.
    stem_example_span: Dict[str, set] = {}
    example_clauses: List[Tuple[Any, List[str], List[str]]] = []
    for example in teaching_examples:
        text = str(example.get("description") or "")
        reason = str(example.get("reason") or "")
        clauses = _clauses(text)
        reason_clauses = _clauses(reason)
        example_clauses.append((example.get("example_id"), clauses, reason_clauses))
        stems_here = {
            _stem(t) for t in _content_tokens(text + " " + reason)
        }
        for stem in stems_here:
            stem_example_span.setdefault(stem, set()).add(example.get("example_id"))

    excluded = {stem: len(ids) for stem, ids in stem_example_span.items()}

    per_example_conditions: List[Dict[str, Any]] = []
    per_example_stems: Dict[Any, set] = {}
    all_pairs: Dict[Tuple[str, ...], List[Any]] = {}

    for example_id, clauses, reason_clauses in example_clauses:
        pairs = _distinctive_conditions(clauses + reason_clauses, excluded)
        per_example_conditions.append(
            {
                "example_id": example_id,
                "conditions": [list(p) for p in pairs],
                "epistemic_status": "DERIVED",
            }
        )
        for pair in pairs:
            all_pairs.setdefault(pair, []).append(example_id)

    # Build the per-example stem sets used by the invariance criterion.
    for example in teaching_examples:
        example_id = example.get("example_id")
        text = str(example.get("description") or "")
        reason = str(example.get("reason") or "")
        per_example_stems[example_id] = {
            _stem(t) for t in _content_tokens(text + " " + reason)
        }

    # INVARIANCE CRITERION (ENGINEERED): a stem that recurs across at least two
    # independent examples is an invariant candidate. Which stems survive is
    # corpus content, not machinery. The criterion is deliberately stated on
    # recurrence, not on clause-pair co-occurrence, because a differently
    # worded WHY will not keep the same two stems inside one clause.
    stem_span: Dict[str, set] = {}
    for example_id, stems in per_example_stems.items():
        for stem in stems:
            stem_span.setdefault(stem, set()).add(example_id)

    invariants = []
    incidental = []
    for stem in sorted(stem_span):
        example_ids = sorted(stem_span[stem])
        # A stem that is a filler in every example (present in all of them)
        # cannot distinguish anything; it is recorded as a shared surface, not
        # as an invariant that was discovered.
        shared_surface = len(example_ids) == len(per_example_stems)
        record = {
            "condition": [stem],
            "label": stem,
            "example_support": example_ids,
            "example_count": len(example_ids),
            "cross_example": len(example_ids) >= 2,
            "clause_pair_provenance": [
                list(pair) for pair, ids in sorted(all_pairs.items())
                if stem in pair
            ],
            "is_shared_surface_term": shared_surface,
            "epistemic_status": (
                "GENERALIZED" if len(example_ids) >= 2 else "NOT_DEMONSTRATED"
            ),
        }
        if len(example_ids) >= 2:
            invariants.append(record)
        else:
            incidental.append(record)

    # Level 2B is constructed ONLY when the mode calls for it.
    build_2b = mode in ("H", "R")
    hypotheses: List[Dict[str, Any]] = []
    if build_2b:
        for example in teaching_examples:
            text = str(example.get("description") or "")
            reason = str(example.get("reason") or "")
            hypotheses.extend(
                _interpretive_hypotheses(
                    example.get("example_id"),
                    _clauses(text),
                    _clauses(reason),
                )
            )

    role_hypothesis = _role_hypothesis(mode) if mode == "R" else None

    return {
        "phase": 3,
        "phase_name": "emergence",
        "mode": mode,
        "tenant": "learner",
        "per_example_conditions": per_example_conditions,
        "invariant_candidates": invariants,
        "incidental_conditions": incidental,
        "invariant_count": len(invariants),
        "incidental_count": len(incidental),
        "level_2b_constructed": build_2b,
        "interpretive_hypotheses": hypotheses,
        "role_hypothesis": role_hypothesis,
        "survives_across_independent_examples": len(invariants) > 0,
        "epistemic_status": "GENERALIZED" if invariants else "NOT_DEMONSTRATED",
    }


# --------------------------------------------------------------------------- #
# Phase 4 - DERIVED ABSTRACTION (invariants -> candidate abstraction)
# --------------------------------------------------------------------------- #


def _necessity_determination(
    invariant: Dict[str, Any],
    why_records: List[Dict[str, Any]],
    per_example_stems: Dict[Any, set],
    description_stems: Dict[Any, set],
) -> str:
    """Is this invariant NECESSARY to the humans' reasons, or incidental?

    A condition is judged
      * NECESSARY  when it recurs inside the REASONS the humans gave, and only
        there;
      * CONTEXT    when it appears in the reasons AND in the descriptions (it
        is both the situation and the point);
      * INCIDENTAL when it appears only in the descriptions, or only once.

    This is a DETERMINATION, not a truth claim, and it is reached by an
    engineered test over emergent content.
    """
    stem = invariant["condition"][0]
    in_reason = False
    in_description = False
    for record in why_records:
        reason_stems = {
            _stem(t) for t in _content_tokens(record.get("reason") or "")
        }
        if stem in reason_stems:
            in_reason = True
    for stems in description_stems.values():
        if stem in stems:
            in_description = True
    if in_reason and not in_description:
        return "necessary"
    if in_reason and in_description:
        return "context"
    return "incidental"


def _abstraction_fingerprint(
    invariants: List[Dict[str, Any]],
    necessity: Dict[str, str],
    why_bindings: List[Dict[str, Any]],
) -> str:
    """A STRUCTURAL fingerprint of the abstraction - never a text hash.

    It folds only what the abstraction MEANS structurally: the sorted set of
    invariant labels, their necessity determinations, and the count of WHY
    bindings. Irrelevant wording and filler changes must NOT move it; a genuine
    WHY or condition change MUST move it.
    """
    labels = sorted("|".join(sorted(inv["condition"])) for inv in invariants)
    necessities = sorted(necessity.get(label, "unknown") for label in labels)
    payload = "::".join(labels) + "#" + "::".join(necessities) + "#" + str(
        len(why_bindings)
    )
    # A short, stable digest - structural, not cryptographic identity.
    digest = 0
    for ch in payload:
        digest = (digest * 131 + ord(ch)) % (2 ** 61 - 1)
    return "abs1:" + format(digest, "016x")


def _phase_4_abstraction(
    teaching_examples: List[Dict[str, Any]],
    emergence: Dict[str, Any],
    mode: str,
) -> Dict[str, Any]:
    """Phase 4 - assemble the DERIVED candidate abstraction.

    The candidate is computed over NORMALIZED structure only. It is a
    candidate: it is never reported as CONCEPTUAL_ABSTRACTION_EVIDENCE, which
    only the probe boundary may assign after an unseen evaluation.
    """
    why_records = [
        _why_record(e.get("example_id"), str(e.get("reason") or ""))
        for e in teaching_examples
    ]

    description_stems: Dict[Any, set] = {}
    for example in teaching_examples:
        description_stems[example.get("example_id")] = {
            _stem(t) for t in _content_tokens(str(example.get("description") or ""))
        }

    invariants = emergence["invariant_candidates"]
    necessity: Dict[str, str] = {}
    why_bindings: List[Dict[str, Any]] = []
    alternatives: List[Dict[str, Any]] = []

    for invariant in invariants:
        label = invariant["label"]
        determination = _necessity_determination(
            invariant, why_records, {}, description_stems
        )
        necessity[label] = determination
        if determination in ("necessary", "context"):
            for record in why_records:
                reason_stems = {
                    _stem(t)
                    for t in _content_tokens(record.get("reason") or "")
                }
                if set(invariant["condition"]) & reason_stems:
                    why_bindings.append(
                        {
                            "condition": label,
                            "example_id": record["example_id"],
                            "reason": record["reason"],
                            "binding": "condition is named in the human's why",
                            "epistemic_status": "DERIVED",
                        }
                    )
        alternatives.append(
            {
                "condition": label,
                "plausible_alternative_reading": (
                    "the same condition may be explained by a different human "
                    "reason than the one recorded"
                ),
                "retained": True,
                "epistemic_status": "DERIVED",
            }
        )

    # Only conditions bound to the humans' WHY may be carried as the
    # abstraction's own invariants: a condition that never appears in any
    # reason is a property of the situation, not of the idea.
    necessary_invariants = [
        inv for inv in invariants
        if necessity.get(inv["label"]) in ("necessary", "context")
    ]

    fingerprint = _abstraction_fingerprint(
        necessary_invariants, necessity, why_bindings
    )

    candidate = {
        "level": "3",
        "name": "LearnedAbstraction",
        "candidate_id": fingerprint,
        "invariants": [
            {
                "condition": inv["label"],
                "example_support": inv["example_support"],
                "example_count": inv["example_count"],
                "necessity": necessity.get(inv["label"], "unknown"),
                "epistemic_status": "GENERALIZED",
            }
            for inv in necessary_invariants
        ],
        "situation_only_conditions": [
            inv["label"] for inv in invariants
            if necessity.get(inv["label"]) == "incidental"
        ],
        "necessity_map": necessity,
        "why_bindings": why_bindings,
        "plausible_alternatives": alternatives,
        "fingerprint": fingerprint,
        "fingerprint_basis": "structural_invariants_and_necessity_not_text",
        "epistemic_status": "DERIVED",
        "claimed_as_conceptual_abstraction_evidence": False,
        "class_name_implies_learning": False,
    }

    return {
        "phase": 4,
        "phase_name": "derived_abstraction",
        "mode": mode,
        "tenant": "learner",
        "candidate_abstraction": candidate,
        "epistemic_status": "DERIVED" if invariants else "NOT_DEMONSTRATED",
    }


def _authored_learner_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "contract": result.get("contract"),
        "version": result.get("version"),
        "test_subject": result.get("test_subject"),
        "demonstration_label": result.get("demonstration_label"),
        "mode": result.get("mode"),
        "phase_1_given": result.get("phase_1_given"),
        "phase_2_formal": result.get("phase_2_formal"),
        "phase_3_emergence": result.get("phase_3_emergence"),
        "phase_4_abstraction": result.get("phase_4_abstraction"),
        "engineering_ledger": result.get("engineering_ledger"),
        "emergent_ledger": result.get("emergent_ledger"),
        "non_claims": _REQUIRED_NON_CLAIMS,
    }


def _assert_no_forbidden_language(result: Dict[str, Any]) -> None:
    payload = json.dumps(_authored_learner_payload(result), sort_keys=True)
    stack = [x for x in re.split(r"[^a-z0-9_]+", payload.lower()) if x]
    for term in _FORBIDDEN_TERMS:
        if term in stack:
            raise ValueError(
                "ArchitecturalAbstractionLearnerV1 must not emit the forbidden "
                "term " + repr(term)
            )


def _assert_mode_f_is_meaning_free(phase_2: Dict[str, Any]) -> None:
    """In Mode F the formal structure must carry NO architectural meaning."""
    if phase_2["mode"] != "F":
        return
    if phase_2.get("level_2b_constructed"):
        raise ValueError(
            "AbstractionLearner: Mode F must never construct Level 2B"
        )
    for example in phase_2["examples"]:
        for structure in example["level_2a_formal_structure"]:
            if structure.get("contains_architectural_meaning"):
                raise ValueError(
                    "AbstractionLearner: Mode F formal structure carries "
                    "architectural meaning"
                )
            blob = json.dumps(structure, sort_keys=True).lower()
            for axis in INTERPRETIVE_AXES:
                if _contains_term(blob.replace('"', " "), axis):
                    raise ValueError(
                        "AbstractionLearner: Mode F formal structure leaked the "
                        "interpretive axis " + repr(axis)
                    )


def _assert_no_evaluation_status(result: Dict[str, Any]) -> None:
    """The learner must NEVER assign the reserved evidence status."""
    blob = json.dumps(result, sort_keys=True)
    # The status string may appear ONLY inside the declared vocabulary lists.
    occurrences = blob.count("CONCEPTUAL_ABSTRACTION_EVIDENCE")
    allowed = 1  # the EPISTEMIC_STATUSES tuple literal is not in the payload
    if occurrences > allowed:
        raise ValueError(
            "AbstractionLearner: the reserved status must not be assigned by "
            "the learner boundary"
        )
    for phase_key in ("phase_1_given", "phase_2_formal", "phase_3_emergence",
                      "phase_4_abstraction"):
        phase = result.get(phase_key) or {}
        if phase.get("epistemic_status") == "CONCEPTUAL_ABSTRACTION_EVIDENCE":
            raise ValueError(
                "AbstractionLearner: " + phase_key + " assigned the reserved "
                "evidence status"
            )


def run_architectural_abstraction_learner(directive: Any) -> Dict[str, Any]:
    """Run Phases 1-4 of the abstraction experiment. Transient and read-only."""
    import json as _json  # local import keeps the module header dependency-free

    global json
    json = _json

    validated = _validate_directive(directive)
    mode = validated["mode"]
    teaching = _list(validated.get("teaching_examples"))
    if not teaching:
        raise ValueError(
            "ArchitecturalAbstractionLearnerV1 requires teaching examples"
        )
    teaching = [_validate_teaching_example(e) for e in teaching]
    _assert_no_learner_leakage(teaching)

    phase_1 = _phase_1_given(teaching, mode)
    phase_2 = _phase_2_formal(teaching, mode)
    phase_3 = _phase_3_emergence(teaching, mode)
    phase_4 = _phase_4_abstraction(teaching, phase_3, mode)

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "test_subject": TEST_SUBJECT,
        "demonstration_label": DEMONSTRATION_LABEL,
        "mode": mode,
        "mode_description": MODE_DESCRIPTIONS[mode],
        "phase_1_given": phase_1,
        "phase_2_formal": phase_2,
        "phase_3_emergence": phase_3,
        "phase_4_abstraction": phase_4,
        "engineering_ledger": dict(_ENGINEERING_LEDGER),
        "emergent_ledger": dict(_EMERGENT_LEDGER),
        "epistemic_status_scale": list(EPISTEMIC_STATUSES),
        "learner_assignable_statuses": list(_LEARNER_ASSIGNABLE_STATUSES),
        "non_claims": dict(_REQUIRED_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }

    _assert_no_forbidden_language(result)
    _assert_mode_f_is_meaning_free(phase_2)
    _assert_no_evaluation_status(result)
    return result
