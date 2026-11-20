"""V3 abstraction learner - Phases 1-4, in two separated modes.

The learner produces ``V3WhyGroundedAbstractionV1``. It runs in exactly one of
two modes, and the modes exist so that two DIFFERENT claims can fail
independently:

MODE P  representation-dependent generalization.
        The learner is given a predefined relational vocabulary and uses it to
        fill the relation slots. This is legitimate and useful - it is what V2
        effectively did - but everything it produces is ENGINEERED or DERIVED,
        its fingerprint is a stability measurement only, and its ceiling is
        ``LEVEL_B_STRUCTURED_GENERALIZATION``. It may NEVER report a novel
        relational pattern or conceptual abstraction evidence.

MODE E  emergent relational structure.
        The learner receives NO architectural relation vocabulary - the firewall
        in ``v3_contracts`` refuses to let one through. Relation slots start
        ``null`` and are filled ONLY by a coherence rule over the corpus. If no
        slot can be derived, the learner says so and emits
        ``PREDEFINED-REPRESENTATION-DEPENDENCE``. That is a valid result.

Phases
------

Phase 1  GIVEN       what the learner was handed, and what it is denied.
Phase 2  CONDITIONS  each example -> conditions with scaffolds, polarity,
                     modality and WHY bindings.
Phase 3  COHERENCE   which slot fills survive across independent examples AND
                     are bound to the humans' WHY.
Phase 4  ABSTRACTION the derived candidate, with its provenance, alternatives,
                     uncertainty, and an explicit ceiling.

Determinism. No randomness, no clock. Same input, same output. Transient,
read-only, non-learning.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from . import v3_contracts as C
from . import v3_condition_model_v1 as CM
from . import v3_why_grounding_v1 as WG

CONTRACT = C.LEARNER_CONTRACT
VERSION = C.LEARNER_VERSION
DIRECTIVE_CONTRACT = C.LEARNER_DIRECTIVE_CONTRACT
DIRECTIVE_VERSION = C.LEARNER_DIRECTIVE_VERSION

TEACHING_EXAMPLE_CONTRACT = "V3WhyConditionTeachingExampleV1"
TEACHING_EXAMPLE_VERSION = "1.0"

# --------------------------------------------------------------------------- #
# The ENGINEERED / EMERGENT ledger for THIS module. Emitted on every run so
# nothing engineered can pass itself off as emergent.
# --------------------------------------------------------------------------- #

ENGINEERING_LEDGER = {
    "tokenizer": C.ORIGIN_ENGINEERED,
    "clause_splitter": C.ORIGIN_ENGINEERED,
    "condition_builder": C.ORIGIN_ENGINEERED,
    "polarity_table": C.ORIGIN_ENGINEERED,
    "modality_table": C.ORIGIN_ENGINEERED,
    "why_connector_table": C.ORIGIN_ENGINEERED,
    "slot_coherence_rule": C.ORIGIN_ENGINEERED,
    "recurrence_rule": C.ORIGIN_ENGINEERED,
    "why_binding_rule": C.ORIGIN_ENGINEERED,
    "fingerprint_function": C.ORIGIN_ENGINEERED,
    "mode_p_predefined_relation_vocabulary": C.ORIGIN_ENGINEERED,
}

EMERGENT_LEDGER = {
    "derived_relation_slot_content": "contingent on corpus",
    "derived_scope_slot_content": "contingent on corpus",
    "surviving_why_grounded_invariants": "contingent on corpus",
    "why_bindings": "contingent on corpus",
    "plausible_alternatives": "contingent on corpus",
    "novel_relational_pattern": "contingent on corpus; may never appear",
    "abstraction_fingerprint": "contingent on corpus",
}

# The slot values that carry NO relation. A derived slot may legitimately be
# "unresolved", which is different from "empty because we forgot".
SLOT_UNRESOLVED = "UNRESOLVED"

# --------------------------------------------------------------------------- #
# The MODE-P predefined relation vocabulary.
#
# Declared HERE as well as in the contracts module so the learner can name what
# it is using. This table is ENGINEERED. `mode_p_relation_vocabulary()` is never
# called in Mode E, and a guard asserts that.
# --------------------------------------------------------------------------- #

_MODE_P_RELATION_KINDS = C.MODE_P_RELATION_VOCABULARY
_MODE_P_SCOPE_KINDS = C.MODE_P_SCOPE_VOCABULARY

# A small ENGINEERED surface-indicator table used ONLY by MODE P to decide which
# predefined kind best fits a clause. It exists so Mode P is a real, working
# baseline rather than a straw man. It is exactly the kind of engineering that
# MODE E is denied.
_MODE_P_KIND_INDICATORS = {
    "encounter": ("faces", "meets", "confronts", "arrives at", "fronts",
                  "overlooks", "greets"),
    "access": ("enters", "entry", "reaches", "arrives", "connects", "opens",
               "leads", "approach", "way in"),
    "containment": ("within", "inside", "encloses", "holds", "contains",
                    "wraps", "surrounds"),
    "adjacency": ("beside", "next to", "adjacent", "alongside", "against",
                  "borders", "touches", "abuts"),
    "sequence": ("then", "next", "before", "after", "follows", "precedes",
                 "passes through", "in turn"),
    "separation": ("separates", "apart", "divides", "distinct", "screened",
                   "buffered", "set back", "withdrawn"),
    "modality_of_action": ("can", "may", "must", "shall", "should", "lets",
                           "allows", "permits", "enables"),
    "persistence": ("remains", "stays", "persists", "endures", "keeps",
                    "continues", "throughout"),
}

_MODE_P_SCOPE_INDICATORS = {
    "domain_containment": ("inside", "within", "enclosed", "contained"),
    "temporal_sequence": ("then", "before", "after", "morning", "evening",
                          "day", "night", "throughout"),
    "boundary_crossing": ("through", "across", "past", "over", "into", "out of"),
    "observational_line": ("sees", "view", "visible", "looks", "watches",
                           "sight", "visible"),
    "acoustic_path": ("hears", "sound", "noise", "audible", "quiet",
                      "listens"),
}


# --------------------------------------------------------------------------- #
# Directive and input validation
# --------------------------------------------------------------------------- #


def _list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _validate_directive(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "V3AbstractionLearnerV1 requires a directive dict, got "
            + type(value).__name__
        )
    contract = value.get("contract")
    if contract in C.FORBIDDEN_CONTRACTS:
        raise ValueError(
            "V3AbstractionLearnerV1 rejects forbidden contract: "
            + str(contract)
        )
    if contract != DIRECTIVE_CONTRACT:
        raise ValueError(
            "V3AbstractionLearnerV1 requires contract "
            + repr(DIRECTIVE_CONTRACT) + ", got " + repr(contract)
        )
    if value.get("version") != DIRECTIVE_VERSION:
        raise ValueError(
            "V3AbstractionLearnerV1 requires version "
            + repr(DIRECTIVE_VERSION) + ", got " + repr(value.get("version"))
        )
    mode = value.get("mode")
    if mode not in C.MODES:
        raise ValueError(
            "V3AbstractionLearnerV1 requires mode in " + repr(C.MODES)
            + ", got " + repr(mode)
        )
    return deepcopy(value)


def _validate_example(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "V3AbstractionLearnerV1: a teaching example must be a dict, got "
            + type(value).__name__
        )
    contract = value.get("contract")
    if contract in C.FORBIDDEN_CONTRACTS:
        raise ValueError(
            "V3AbstractionLearnerV1: teaching example reached a forbidden "
            "contract: " + str(contract)
        )
    if contract != TEACHING_EXAMPLE_CONTRACT:
        raise ValueError(
            "V3AbstractionLearnerV1: teaching example requires contract "
            + repr(TEACHING_EXAMPLE_CONTRACT) + ", got " + repr(contract)
        )
    if value.get("version") != TEACHING_EXAMPLE_VERSION:
        raise ValueError(
            "V3AbstractionLearnerV1: teaching example requires version "
            + repr(TEACHING_EXAMPLE_VERSION)
        )
    return deepcopy(value)


def _assert_no_leakage(examples: List[Dict[str, Any]]) -> None:
    """Refuse teaching input that carries an expected answer."""
    for example in examples:
        for key in C.EVALUATION_KEYS:
            if key in example:
                raise ValueError(
                    "V3AbstractionLearnerV1: leakage - a teaching example "
                    "carries an evaluation key " + repr(key)
                )


# --------------------------------------------------------------------------- #
# Phase 1 - GIVEN
# --------------------------------------------------------------------------- #


def _phase_1_given(
    examples: List[Dict[str, Any]], mode: str
) -> Dict[str, Any]:
    texts = [str(e.get("text") or "") for e in examples]
    reasons = [
        WG.split_reason(t)[1] for t in texts
    ]
    vocabulary: List[str] = []
    for text in texts:
        vocabulary.extend(CM._content_tokens(text))

    return {
        "phase": 1,
        "phase_name": "given",
        "mode": mode,
        "tenant": "learner",
        "given": {
            "teaching_example_count": len(examples),
            "surface_texts": [
                {
                    "example_id": e.get("example_id"),
                    "text": str(e.get("text") or ""),
                    "why_present": bool(WG.split_reason(str(e.get("text") or ""))[1]),
                    "epistemic_status": C.STATUS_ENGINEERED,
                }
                for e in examples
            ],
            "observed_vocabulary": sorted(set(vocabulary)),
            "reasons_supplied": sum(1 for r in reasons if r),
            "relation_vocabulary_given": (
                list(_MODE_P_RELATION_KINDS) if mode == C.MODE_P else []
            ),
            "scope_vocabulary_given": (
                list(_MODE_P_SCOPE_KINDS) if mode == C.MODE_P else []
            ),
            "concept_name_given": False,
            "expected_answer_given": False,
            "evaluation_key_given": False,
        },
        "denied_to_learner": [
            "intended_concept_name",
            "intended_relation",
            "expected_label",
            "evaluation_expectations",
            "author_reference",
        ],
        "mode_e_no_relation_vocabulary": mode == C.MODE_E,
        "epistemic_status": C.STATUS_ENGINEERED,
    }


# --------------------------------------------------------------------------- #
# Phase 2 - CONDITIONS
# --------------------------------------------------------------------------- #


def _mode_p_fill(clause: str) -> Tuple[Any, Any]:
    """MODE P: choose a predefined relation/scope kind for a clause.

    ENGINEERED, and proudly so: this is a table lookup against a predefined
    vocabulary. It is the baseline the experiment measures against, not a
    candidate for emergence. It returns None for both when no indicator is
    present, rather than forcing a kind onto the clause.
    """
    lowered = clause.lower()
    relation = None
    for kind in _MODE_P_RELATION_KINDS:
        indicators = _MODE_P_KIND_INDICATORS.get(kind, ())
        if any(CM._contains_term(lowered, i) for i in indicators):
            relation = kind
            break
    scope = None
    for kind in _MODE_P_SCOPE_KINDS:
        indicators = _MODE_P_SCOPE_INDICATORS.get(kind, ())
        if any(CM._contains_term(lowered, i) for i in indicators):
            scope = kind
            break
    return relation, scope


def _mode_e_derive(clause: str) -> Tuple[Any, Any]:
    """MODE E: attempt to derive a relation slot from the clause itself.

    This is the demanding half of the experiment. It has NO architectural
    vocabulary available. All it may use is the generic scaffolding and the
    clause's own structure.

    The rule it may apply is ENGINEERED and must be stated plainly: a relation
    can only be derived when the clause asserts a RELATIONSHIP between two
    participants - that is, when it has a subject-like head, a connecting verb,
    and an object-like tail. When it merely predicates a property of one thing,
    there is nothing to place in the slot, and the honest answer is UNRESOLVED.

    The CONTENT of the slot is not a predefined word: it is the clause's own
    connecting verb, taken verbatim. That is what makes it emergent rather than
    engineered - the slot is filled with something the corpus produced, not with
    something this code supplied.

    Because the slot content is a verb taken from the text, it is by
    construction not one of the predefined relation words, and the firewall
    check downstream will confirm this.
    """
    tokens = CM._content_tokens(clause)
    if len(tokens) < 3:
        return SLOT_UNRESOLVED, SLOT_UNRESOLVED

    # Find the connecting verb: the first content token that a light,
    # corpus-independent morphology marks as a finite verb form. This is a
    # structural test, not a semantic one - it does not know what the verb
    # MEANS, only that a verb is what joins two participants.
    verb_index = None
    for index, token in enumerate(tokens):
        if _looks_like_verb(token) and index not in (0, len(tokens) - 1):
            verb_index = index
            break
    if verb_index is None:
        return SLOT_UNRESOLVED, SLOT_UNRESOLVED

    # A verb alone is not a relation: there must be material on both sides.
    before = tokens[:verb_index]
    after = tokens[verb_index + 1:]
    if not before or not after:
        return SLOT_UNRESOLVED, SLOT_UNRESOLVED

    relation_slot = tokens[verb_index]
    # The scope slot is filled only when the clause itself carries a scope
    # marker. The marker set is ENGINEERED and generic (spatial/temporal
    # prepositions), containing no architectural relation vocabulary.
    scope_slot = SLOT_UNRESOLVED
    for marker in _GENERIC_SCOPE_MARKERS:
        if CM._contains_term(clause.lower(), marker):
            scope_slot = marker
            break
    return relation_slot, scope_slot


# Generic spatial/temporal prepositions. ENGINEERED, and carrying NO
# architectural relation meaning: "through" is a preposition, not a claim about
# circulation.
_GENERIC_SCOPE_MARKERS = (
    "through", "across", "between", "into", "onto", "toward", "towards",
    "from", "within", "beside", "around", "along", "past", "beyond",
    "before", "after", "during", "throughout",
)

# Finite-verb morphology markers. ENGINEERED and purely structural.
_VERB_SUFFIXES = ("s", "es", "ed", "ing")


def _looks_like_verb(token: str) -> bool:
    """A structural, corpus-independent verb test.

    Deliberately crude: V3 does not want a good parser here, because a good
    parser would smuggle in linguistic knowledge that makes the emergence claim
    unearned. A token counts as a verb-like connector if it is long enough and
    is not obviously a noun-shaped token. This is ENGINEERED and is declared as
    such.
    """
    if len(token) < 3:
        return False
    if token.endswith("tion") or token.endswith("ment") or token.endswith("ness"):
        return False
    return True


def _phase_2_conditions(
    examples: List[Dict[str, Any]], mode: str
) -> Dict[str, Any]:
    per_example: List[Dict[str, Any]] = []
    all_conditions: List[Dict[str, Any]] = []

    for example in examples:
        example_id = example.get("example_id")
        text = str(example.get("text") or "")
        conditions = []

        for clause_index, clause in enumerate(CM.clauses(text)):
            condition_part, reason_part = WG.split_reason(clause)
            if not condition_part:
                condition_part = clause

            grounding = WG.ground_condition(
                condition_part, reason_part,
                source_why_id=None, source_example_id=example_id,
            )

            if mode == C.MODE_P:
                relation, scope = _mode_p_fill(condition_part)
                origin = C.ORIGIN_ENGINEERED
            else:
                relation, scope = _mode_e_derive(condition_part)
                origin = C.ORIGIN_DERIVED

            # The UNRESOLVED sentinel means "the corpus did not supply this
            # slot". It is an internal marker and must NEVER reach the scaffold:
            # an unfilled slot is stored as null, with no origin, so an audit
            # can tell an empty slot from a filled one at a glance.
            resolved_relation = (
                None if relation in (None, SLOT_UNRESOLVED) else relation
            )
            resolved_scope = (
                None if scope in (None, SLOT_UNRESOLVED) else scope
            )

            scaffold = CM.make_scaffold()
            if resolved_relation is not None or resolved_scope is not None:
                scaffold = CM.fill_relation_slot(
                    scaffold,
                    resolved_relation,
                    resolved_scope,
                    origin,
                )

            condition = CM.make_condition(
                condition_id="{}::c{}".format(example_id, clause_index),
                clause=condition_part,
                why_verbatim=grounding["why_verbatim"],
                why_clause=grounding["why_clause"],
                why_grounding={
                    "why_verbatim": grounding["why_verbatim"],
                    "why_clause": grounding["why_clause"],
                    "grounding": grounding["grounding"],
                    "causal_direction": grounding["causal_direction"]["value"],
                    "origin": C.ORIGIN_DERIVED,
                },
                relation=scaffold,
                alternatives=[{
                    "plausible_alternative_reading":
                        "the same condition may be explained by a different "
                        "human reason than the one recorded",
                    "retained": True,
                    "origin": C.ORIGIN_DERIVED,
                }],
                source={
                    "source_example_id": example_id,
                    "extraction_rule": "clause_from_teaching_example",
                },
            )
            condition["grounding_record"] = grounding
            conditions.append(condition)
            all_conditions.append(condition)

        per_example.append({
            "example_id": example_id,
            "condition_count": len(conditions),
            "conditions": conditions,
            "epistemic_status": C.STATUS_DERIVED,
        })

    return {
        "phase": 2,
        "phase_name": "conditions",
        "mode": mode,
        "tenant": "learner",
        "per_example": per_example,
        "condition_count": len(all_conditions),
        "slot_origin_used": (
            C.ORIGIN_ENGINEERED if mode == C.MODE_P else C.ORIGIN_DERIVED
        ),
        "epistemic_status": C.STATUS_DERIVED if all_conditions
        else C.STATUS_NOT_DEMONSTRATED,
    }


# --------------------------------------------------------------------------- #
# Phase 3 - COHERENCE
# --------------------------------------------------------------------------- #


def _phase_3_coherence(
    examples: List[Dict[str, Any]],
    phase_2: Dict[str, Any],
    mode: str,
) -> Dict[str, Any]:
    """Find which slot fills survive across independent examples.

    A slot fill is a candidate invariant when it recurs in at least two
    INDEPENDENT examples. Recurrence is counted per-example, not per-clause, so
    a single example repeating a word twice cannot manufacture an invariant.

    Each candidate is then tested against the humans' WHY: a candidate whose
    content never appears in any reason is a property of the situation, not of
    the idea, and is recorded as incidental rather than carried into the
    abstraction.
    """
    per_example_relations: Dict[Any, set] = {}
    per_example_scopes: Dict[Any, set] = {}
    per_example_verbs: Dict[Any, set] = {}

    for entry in phase_2["per_example"]:
        example_id = entry["example_id"]
        relat, scop, verbs = set(), set(), set()
        for condition in entry["conditions"]:
            scaffold = condition["relation"]
            if scaffold.get("relation_slot") is not None:
                relat.add(scaffold["relation_slot"])
            if scaffold.get("scope_slot") is not None:
                scop.add(scaffold["scope_slot"])
            for token in CM._content_tokens(condition["provenance"]["source_clause"]):
                verbs.add(token)
        per_example_relations[example_id] = relat
        per_example_scopes[example_id] = scop
        per_example_verbs[example_id] = verbs

    def _recurrence(per_example: Dict[Any, set]) -> Dict[str, Dict[str, Any]]:
        span: Dict[str, set] = {}
        for example_id, values in per_example.items():
            for value in values:
                span.setdefault(value, set()).add(example_id)
        out = {}
        for value, ids in span.items():
            out[value] = {
                "value": value,
                "example_support": sorted(ids),
                "example_count": len(ids),
                "cross_example": len(ids) >= 2,
                "shared_surface": len(ids) == len(per_example),
            }
        return out

    relation_recurrence = _recurrence(per_example_relations)
    scope_recurrence = _recurrence(per_example_scopes)

    # WHY binding test: does the candidate value appear in any human reason?
    why_texts = [
        WG.split_reason(str(e.get("text") or ""))[1] for e in examples
    ]
    why_vocabulary = set()
    for reason in why_texts:
        why_vocabulary.update(CM._content_tokens(reason))

    invariants: List[Dict[str, Any]] = []
    incidental: List[Dict[str, Any]] = []

    for value, record in sorted(relation_recurrence.items()):
        in_why = value in why_vocabulary
        entry = {
            "slot_kind": "relation",
            "slot_value": value,
            "example_support": record["example_support"],
            "example_count": record["example_count"],
            "bound_to_why": in_why,
            "shared_surface": record["shared_surface"],
            "epistemic_status": (
                C.STATUS_GENERALIZED if record["cross_example"]
                else C.STATUS_NOT_DEMONSTRATED
            ),
        }
        if record["cross_example"] and in_why:
            invariants.append(entry)
        elif record["cross_example"]:
            entry["note"] = (
                "recurs across examples but is never named in a human reason: "
                "a property of the situation, not of the idea"
            )
            incidental.append(entry)
        else:
            incidental.append(entry)

    for value, record in sorted(scope_recurrence.items()):
        in_why = value in why_vocabulary
        entry = {
            "slot_kind": "scope",
            "slot_value": value,
            "example_support": record["example_support"],
            "example_count": record["example_count"],
            "bound_to_why": in_why,
            "shared_surface": record["shared_surface"],
            "epistemic_status": (
                C.STATUS_GENERALIZED if record["cross_example"]
                else C.STATUS_NOT_DEMONSTRATED
            ),
        }
        # A SCOPE marker alone is never a why-grounded invariant. A generic
        # preposition recurring across examples ("from", "through") marks a
        # shared surface habit, not an idea: if it were carried, the abstraction
        # would be resting on grammatical glue. It is recorded as incidental and
        # is deliberately NOT promoted, so the learner cannot overclaim on the
        # strength of a preposition.
        entry["note"] = (
            "a scope marker is grammatical glue; it is recorded but never "
            "promoted to a why-grounded invariant on its own"
        )
        incidental.append(entry)

    # A novel relational pattern may be reported ONLY in MODE E, and only when a
    # relation slot was derived whose value appears in NO predefined vocabulary.
    novel_pattern = None
    surface_verb_diagnosis = None
    if mode == C.MODE_E:
        surface_verb_diagnosis = _surface_verb_invariant_diagnosis(
            invariants, phase_2
        )
        novel_pattern = _detect_novel_pattern(invariants)

    return {
        "phase": 3,
        "phase_name": "coherence",
        "mode": mode,
        "tenant": "learner",
        "relation_recurrence": relation_recurrence,
        "scope_recurrence": scope_recurrence,
        "why_vocabulary": sorted(why_vocabulary),
        "invariant_candidates": invariants,
        "incidental_candidates": incidental,
        "invariant_count": len(invariants),
        "slot_derived": any(
            entry["slot_kind"] == "relation" for entry in invariants
        ),
        "novel_relational_pattern": novel_pattern,
        "surface_verb_diagnosis": surface_verb_diagnosis,
        "emergence_available": mode == C.MODE_E,
        "epistemic_status": C.STATUS_GENERALIZED if invariants
        else C.STATUS_NOT_DEMONSTRATED,
    }


def _detect_novel_pattern(
    invariants: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Detect a relational pattern not present in any predefined vocabulary.

    MODE E ONLY. Returns None unless a relation-slot value survives across
    examples AND is absent from both the Mode-P relation and scope vocabularies.
    A Mode-P value found here would prove the Mode-E result was assisted by a
    predefined representation, so such a value is refused, not reported.

    A SURFACE VERB is NOT a novel relational pattern. If the only difference
    between the derived slots of two examples is the particular verb each clause
    happened to use, then the "pattern" is surface vocabulary, and reporting it
    would be exactly the lexical dependence this experiment exists to catch. A
    slot value therefore also has to be recurrent AS THE SAME VALUE across
    examples - a value that recurs only because it was copied from one example's
    verb has no cross-example support and is refused here.
    """
    predefined = set(_MODE_P_RELATION_KINDS) | set(_MODE_P_SCOPE_KINDS)
    for entry in invariants:
        if entry["slot_kind"] != "relation":
            continue
        value = entry["slot_value"]
        if value in predefined:
            # Refuse: this is representation dependence, not emergence.
            continue
        return {
            "contract": C.NOVEL_PATTERN_CONTRACT,
            "version": C.NOVEL_PATTERN_VERSION,
            "output_type": C.STATUS_NOVEL_RELATIONAL_PATTERN,
            "pattern_id": "novel::" + str(value),
            "source_conditions": entry["example_support"],
            "supporting_examples": entry["example_support"],
            "why_bindings": ["bound_to_why"] if entry.get("bound_to_why") else [],
            "alternatives": [
                "the same derived slot may be an artefact of the simplest "
                "clause structure rather than a stable relational idea"
            ],
            "uncertainty": {
                "level": "high",
                "reason": "derived without any predefined architectural "
                          "relation vocabulary; corroboration is limited to "
                          "this corpus",
            },
            "provenance": {
                "origin": C.ORIGIN_EMERGENT,
                "derivation_rule": "clause_connecting_verb_recurrence",
                "predefined_vocabulary_used": [],
            },
            "in_initial_vocabulary": False,
            "epistemic_status": C.STATUS_NOVEL_RELATIONAL_PATTERN,
            "claimed_as_conceptual_abstraction_evidence": False,
        }
    return None


def _surface_verb_invariant_diagnosis(
    invariants: List[Dict[str, Any]],
    phase_2: Dict[str, Any],
) -> Dict[str, Any]:
    """Diagnose whether a surviving relation slot is only surface vocabulary.

    A relation slot survives across examples only when the SAME verb recurs. In
    naturally-worded examples the same idea is usually carried by DIFFERENT
    verbs ("set back", "sits apart", "stands back"), so a surviving slot is
    strong evidence of lexical rather than relational stability, and the learner
    must be able to say so.

    This is a DIAGNOSIS, not a verdict: it feeds the level decision so the
    learner cannot report a why-grounded generalization that rests on a shared
    verb.
    """
    relation_invariants = [
        i for i in invariants if i["slot_kind"] == "relation"
    ]
    if not relation_invariants:
        return {
            "suspected": False,
            "reason": "no relation slot survived, so there is nothing to test",
        }

    # Distinct verbs used per example for the surviving value.
    supporting = set()
    for entry in relation_invariants:
        supporting.update(entry["example_support"])

    verbs_per_example = {}
    for example_entry in phase_2["per_example"]:
        example_id = example_entry["example_id"]
        verbs_per_example[example_id] = {
            c["relation"]["relation_slot"]
            for c in example_entry["conditions"]
            if c["relation"].get("relation_slot") is not None
        }

    # How many DISTINCT verbs appear across the examples the invariant rests on?
    distinct = set()
    for example_id in supporting:
        distinct.update(verbs_per_example.get(example_id, set()))

    suspected = len(distinct) <= 1 and len(supporting) >= 2
    return {
        "suspected": suspected,
        "surviving_values": [i["slot_value"] for i in relation_invariants],
        "distinct_verbs_across_supporting_examples": sorted(distinct),
        "supporting_examples": sorted(supporting),
        "reason": (
            "every supporting example used the SAME verb, so the surviving "
            "slot is a shared surface token rather than a relational idea"
            if suspected else
            "the supporting examples used more than one verb"
        ),
    }


# --------------------------------------------------------------------------- #
# Phase 4 - ABSTRACTION
# --------------------------------------------------------------------------- #


def _fingerprint(
    invariants: List[Dict[str, Any]],
    novel_pattern: Optional[Dict[str, Any]],
) -> str:
    """A STRUCTURAL fingerprint. A stability measurement, never evidence."""
    import hashlib
    labels = sorted(
        "{}:{}".format(i["slot_kind"], i["slot_value"]) for i in invariants
    )
    payload = "|".join(labels) + "#" + (
        novel_pattern["pattern_id"] if novel_pattern else "none"
    )
    return "abs3:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _phase_4_abstraction(
    examples: List[Dict[str, Any]],
    phase_3: Dict[str, Any],
    mode: str,
) -> Dict[str, Any]:
    invariants = phase_3["invariant_candidates"]
    novel_pattern = phase_3.get("novel_relational_pattern")
    surface_verb_diagnosis = phase_3.get("surface_verb_diagnosis")
    why_grounded = [i for i in invariants if i.get("bound_to_why")]
    fingerprint = _fingerprint(invariants, novel_pattern)

    # MODE P can never emit a novel pattern; if one somehow appeared it is
    # dropped here AND recorded, so the droppage is auditable.
    novel_dropped_in_mode_p = None
    if mode == C.MODE_P and novel_pattern is not None:
        novel_dropped_in_mode_p = novel_pattern
        novel_pattern = None

    if mode == C.MODE_P:
        ceiling = C.MODE_P_CEILING
    else:
        ceiling = C.MODE_CEILING[C.MODE_E]

    surface_verb_suspected = bool(
        surface_verb_diagnosis and surface_verb_diagnosis.get("suspected")
    )

    if not invariants:
        reported_level = C.LEVEL_A
        level_reason = "no invariant survived the corpus"
    elif mode == C.MODE_P:
        reported_level = C.LEVEL_B
        level_reason = (
            "invariants were produced using a predefined relation vocabulary; "
            "the result is structured generalization over an engineered "
            "representation and can rise no higher"
        )
    elif surface_verb_suspected:
        # The surviving slot rests on a shared verb, so it is lexical, not
        # relational. This is the LEXICAL_DEPENDENCE failure the experiment
        # exists to detect, and the learner must not report above Level B.
        reported_level = C.LEVEL_B
        level_reason = (
            "every supporting example used the same connecting verb, so the "
            "surviving slot is a shared surface token: this is lexical "
            "dependence, and it cannot support a why-grounded generalization"
        )
    elif not why_grounded:
        reported_level = C.LEVEL_B
        level_reason = (
            "Mode E derived slots, but no surviving invariant is bound to a "
            "human reason, so the abstraction is structural only"
        )
    elif novel_pattern is not None:
        reported_level = C.LEVEL_D
        level_reason = (
            "Mode E derived a relation slot absent from every predefined "
            "vocabulary, recurrent across independent examples and bound to "
            "the humans' WHY"
        )
    else:
        reported_level = C.LEVEL_C
        level_reason = (
            "Mode E produced why-grounded invariants derived without any "
            "predefined relation vocabulary, but no slot met the emergent novel "
            "pattern bar"
        )

    reported_level = C.clamp_evidence_level(reported_level, ceiling)

    abstraction = {
        "contract": C.ABSTRACTION_CONTRACT,
        "version": C.ABSTRACTION_VERSION,
        "abstraction_id": fingerprint,
        "level": "abstraction",
        "mode": mode,
        "invariants": [
            {
                "slot_kind": i["slot_kind"],
                "slot_value": i["slot_value"],
                "example_support": i["example_support"],
                "example_count": i["example_count"],
                "bound_to_why": i["bound_to_why"],
                "epistemic_status": i["epistemic_status"],
            }
            for i in invariants
        ],
        "incidental_conditions": phase_3["incidental_candidates"],
        "novel_relational_pattern": novel_pattern,
        "novel_pattern_dropped_in_mode_p": novel_dropped_in_mode_p,
        "surface_verb_diagnosis": surface_verb_diagnosis,
        "why_grounded_invariant_count": len(why_grounded),
        "fingerprint": fingerprint,
        "fingerprint_semantics": C.FINGERPRINT_SEMANTICS,
        "fingerprint_is_learning_evidence": False,
        "reported_evidence_level": reported_level,
        "mode_ceiling": ceiling,
        "level_reason": level_reason,
        "predefined_relation_vocabulary_used": (
            list(_MODE_P_RELATION_KINDS) if mode == C.MODE_P else []
        ),
        "uncertainty": {
            "level": "high",
            "retained_alternatives": [
                "the invariant may reflect the corpus rather than an "
                "architectural idea"
            ],
            "collapsed": False,
            "origin": C.ORIGIN_EMERGENT,
        },
        "alternatives": [
            {
                "plausible_alternative_reading":
                    "a different corpus may not support the same invariant",
                "retained": True,
                "origin": C.ORIGIN_EMERGENT,
            }
        ],
        "epistemic_status": (
            C.STATUS_GENERALIZED if invariants else C.STATUS_NOT_DEMONSTRATED
        ),
        "claimed_as_learning": False,
        "claimed_as_conceptual_abstraction_evidence": False,
    }

    return {
        "phase": 4,
        "phase_name": "abstraction",
        "mode": mode,
        "tenant": "learner",
        "candidate_abstraction": abstraction,
        "epistemic_status": abstraction["epistemic_status"],
    }


# --------------------------------------------------------------------------- #
# Self-audits
# --------------------------------------------------------------------------- #


def _authored_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "contract": result.get("contract"),
        "version": result.get("version"),
        "mode": result.get("mode"),
        "phase_1_given": result.get("phase_1_given"),
        "phase_2_conditions": result.get("phase_2_conditions"),
        "phase_3_coherence": result.get("phase_3_coherence"),
        "phase_4_abstraction": result.get("phase_4_abstraction"),
        "engineering_ledger": result.get("engineering_ledger"),
        "emergent_ledger": result.get("emergent_ledger"),
        "non_claims": C.REQUIRED_NON_CLAIMS,
    }


def _assert_no_forbidden_language(result: Dict[str, Any]) -> None:
    import json as _json
    import re
    payload = _json.dumps(_authored_payload(result), sort_keys=True).lower()
    for term in C.FORBIDDEN_EMITTED_TERMS:
        if re.search(r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])",
                     payload):
            raise ValueError(
                "V3AbstractionLearnerV1 must not emit the forbidden term "
                + repr(term)
            )


def _assert_mode_e_purity(result: Dict[str, Any]) -> None:
    """MODE E must not have received or emitted an architectural relation word.

    This is the single most important guard in V3. If it cannot hold, the
    Mode-E result is not evidence of emergence, and the experiment must say so.
    """
    if result["mode"] != C.MODE_E:
        return
    payload = _authored_payload(result)
    # Everything EXCEPT the declared guard/ceiling/vocabulary bookkeeping must
    # be free of the forbidden terms. Mode E legitimately records the empty list
    # of predefined vocabulary it used, and the contracts module names the terms
    # it refuses - those are bookkeeping, not representation.
    C.assert_mode_e_receives_no_relation_vocabulary(
        {
            "phase_1_given": result["phase_1_given"],
            "phase_2_conditions": result["phase_2_conditions"],
            "phase_3_coherence": result["phase_3_coherence"],
            "phase_4_abstraction": result["phase_4_abstraction"],
        }
    )
    del payload


def _assert_learner_never_assigns_reserved_status(result: Dict[str, Any]) -> None:
    """The learner must NEVER assign the reserved evidence status.

    The string legitimately appears exactly once, inside the declared
    ``epistemic_status_scale`` vocabulary. It must appear NOWHERE ELSE - not as
    a phase status, not as a condition status, not as an abstraction status.
    The check is structural: every ``epistemic_status`` field is walked and the
    reserved value is refused wherever it is found as an ASSIGNMENT.
    """
    reserved = C.STATUS_CONCEPTUAL_ABSTRACTION_EVIDENCE

    def _walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "epistemic_status" and value == reserved:
                    raise ValueError(
                        "V3AbstractionLearnerV1: the reserved evidence status "
                        "was assigned at " + path + " - the learner boundary "
                        "may never assign it"
                    )
                if key in ("reported_evidence_level", "evidence_level_reached",
                           "mode_ceiling") and value == reserved:
                    raise ValueError(
                        "V3AbstractionLearnerV1: the reserved evidence level "
                        "was assigned at " + path
                    )
                _walk(value, path + "." + str(key))
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                _walk(value, path + "[" + str(index) + "]")

    _walk(result, "$")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def run_v3_abstraction_learner(directive: Any) -> Dict[str, Any]:
    """Run Phases 1-4 for one mode. Transient and read-only."""
    validated = _validate_directive(directive)
    mode = validated["mode"]

    examples = _list(validated.get("teaching_examples"))
    if len(examples) < 1:
        raise ValueError(
            "V3AbstractionLearnerV1 requires at least one teaching example"
        )
    examples = [_validate_example(e) for e in examples]
    _assert_no_leakage(examples)

    # MODE E FIREWALL: refuse any directive that carries a relation vocabulary
    # into Mode E. Checked BEFORE any derivation, so a Mode-E run can never be
    # silently assisted by a predefined representation.
    if mode == C.MODE_E:
        C.assert_mode_e_receives_no_relation_vocabulary(
            {
                "teaching_examples": examples,
                "given_relation_vocabulary": _list(
                    validated.get("relation_vocabulary")
                ),
                "given_scope_vocabulary": _list(
                    validated.get("scope_vocabulary")
                ),
            }
        )

    phase_1 = _phase_1_given(examples, mode)
    phase_2 = _phase_2_conditions(examples, mode)
    phase_3 = _phase_3_coherence(examples, phase_2, mode)
    phase_4 = _phase_4_abstraction(examples, phase_3, mode)

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "test_subject": C.TEST_SUBJECT,
        "demonstration_label": C.DEMONSTRATION_LABEL,
        "mode": mode,
        "mode_description": C.MODE_DESCRIPTIONS[mode],
        "phase_1_given": phase_1,
        "phase_2_conditions": phase_2,
        "phase_3_coherence": phase_3,
        "phase_4_abstraction": phase_4,
        "engineering_ledger": dict(ENGINEERING_LEDGER),
        "emergent_ledger": dict(EMERGENT_LEDGER),
        "representation_provenance_ledger": deepcopy(
            C.REPRESENTATION_PROVENANCE_LEDGER
        ),
        "epistemic_status_scale": list(C.EPISTEMIC_STATUSES),
        "learner_assignable_statuses": list(C.LEARNER_ASSIGNABLE_STATUSES),
        "evidence_level_reached": phase_4["candidate_abstraction"][
            "reported_evidence_level"
        ],
        "mode_ceiling": phase_4["candidate_abstraction"]["mode_ceiling"],
        "non_claims": dict(C.REQUIRED_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }

    _assert_no_forbidden_language(result)
    _assert_mode_e_purity(result)
    _assert_learner_never_assigns_reserved_status(result)
    return result


__all__ = [
    "CONTRACT", "VERSION", "DIRECTIVE_CONTRACT", "DIRECTIVE_VERSION",
    "TEACHING_EXAMPLE_CONTRACT", "TEACHING_EXAMPLE_VERSION",
    "ENGINEERING_LEDGER", "EMERGENT_LEDGER", "SLOT_UNRESOLVED",
    "run_v3_abstraction_learner",
]
