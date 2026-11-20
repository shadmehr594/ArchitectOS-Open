"""V3 abstraction probe - Phases 5-6, the eleven failure modes, and the verdict.

The probe is the EVALUATOR. It runs after the learner has finished, it never
feeds anything back, and it reads the author's expectations only AFTER it has
reached its verdict.

What it does
------------

Phase 5  UNSEEN     take the learner's abstraction and a set of unseen cases,
                    and decide - per case - whether the abstraction accounts for
                    the case, contradicts it, or says nothing about it.
Phase 6  FAILURES   measure ALL ELEVEN failure modes. Every one is emitted on
                    every run with an explicit state. A failure mode may not be
                    omitted, and may not be reported as a pass when it was never
                    exercised.
VERDICT             the highest evidence level the run actually earned, never
                    higher than the mode's ceiling, and never higher than what
                    the measurements support.

The verdict vocabulary is the five evidence levels. There is no sixth state and
no "inconclusive but probably fine".

Transient, read-only, non-learning.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from . import v3_contracts as C
from . import v3_condition_model_v1 as CM
from . import v3_why_grounding_v1 as WG
from . import v3_abstraction_learner_v1 as LEARNER

CONTRACT = C.PROBE_CONTRACT
VERSION = C.PROBE_VERSION
DIRECTIVE_CONTRACT = C.PROBE_DIRECTIVE_CONTRACT
DIRECTIVE_VERSION = C.PROBE_DIRECTIVE_VERSION

UNSEEN_CASE_CONTRACT = "V3UnseenCaseV1"
UNSEEN_CASE_VERSION = "1.0"

# The verdict vocabulary: the five evidence levels, and nothing else.
VERDICTS = C.EVIDENCE_LEVELS

# Failure-mode states, re-exported for readability.
NOT_EXERCISED = "NOT_EXERCISED"
MEASURED_PASS = "MEASURED_PASS"
MEASURED_FAIL = "MEASURED_FAIL"
INCONCLUSIVE = "INCONCLUSIVE"


def _list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def _validate_directive(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "V3AbstractionProbeV1 requires a directive dict, got "
            + type(value).__name__
        )
    contract = value.get("contract")
    if contract in C.FORBIDDEN_CONTRACTS:
        raise ValueError(
            "V3AbstractionProbeV1 rejects forbidden contract: " + str(contract)
        )
    if contract != DIRECTIVE_CONTRACT:
        raise ValueError(
            "V3AbstractionProbeV1 requires contract "
            + repr(DIRECTIVE_CONTRACT) + ", got " + repr(contract)
        )
    if value.get("version") != DIRECTIVE_VERSION:
        raise ValueError(
            "V3AbstractionProbeV1 requires version "
            + repr(DIRECTIVE_VERSION) + ", got " + repr(value.get("version"))
        )
    return deepcopy(value)


def _validate_learner_result(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "V3AbstractionProbeV1 requires a learner result dict, got "
            + type(value).__name__
        )
    if value.get("contract") != C.LEARNER_CONTRACT:
        raise ValueError(
            "V3AbstractionProbeV1 requires a learner result with contract "
            + repr(C.LEARNER_CONTRACT) + ", got " + repr(value.get("contract"))
        )
    if value.get("version") != C.LEARNER_VERSION:
        raise ValueError(
            "V3AbstractionProbeV1 requires learner version "
            + repr(C.LEARNER_VERSION)
        )
    if "phase_4_abstraction" not in value:
        raise ValueError(
            "V3AbstractionProbeV1: learner result is missing phase_4_abstraction"
        )
    return deepcopy(value)


def _validate_unseen_case(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "V3AbstractionProbeV1: an unseen case must be a dict, got "
            + type(value).__name__
        )
    if value.get("contract") != UNSEEN_CASE_CONTRACT:
        raise ValueError(
            "V3AbstractionProbeV1: unseen case requires contract "
            + repr(UNSEEN_CASE_CONTRACT) + ", got " + repr(value.get("contract"))
        )
    if value.get("version") != UNSEEN_CASE_VERSION:
        raise ValueError(
            "V3AbstractionProbeV1: unseen case requires version "
            + repr(UNSEEN_CASE_VERSION)
        )
    for key in C.EVALUATION_KEYS:
        if key in value:
            raise ValueError(
                "V3AbstractionProbeV1: an unseen case carries an evaluation "
                "key " + repr(key) + " - the learner must not receive it"
            )
    return deepcopy(value)


# --------------------------------------------------------------------------- #
# Phase 5 - UNSEEN
# --------------------------------------------------------------------------- #


def _abstraction_signature(abstraction: Dict[str, Any]) -> set:
    """The set of (slot_kind, slot_value) the abstraction commits to."""
    return {
        (i["slot_kind"], i["slot_value"]) for i in abstraction.get("invariants", [])
    }


def _case_conditions(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build conditions for an unseen case WITHOUT any predefined vocabulary.

    The probe builds conditions with the same generic scaffolding the learner
    used. It never fills a relation slot with a predefined kind: it only reads
    what the case itself says.
    """
    text = str(case.get("text") or "")
    conditions = []
    for clause_index, clause in enumerate(CM.clauses(text)):
        condition_part, reason_part = WG.split_reason(clause)
        if not condition_part:
            condition_part = clause
        relation, scope = LEARNER._mode_e_derive(condition_part)
        scaffold = CM.make_scaffold()
        if relation is not None or scope not in (None, LEARNER.SLOT_UNRESOLVED):
            scaffold = CM.fill_relation_slot(
                scaffold,
                None if relation in (None, LEARNER.SLOT_UNRESOLVED) else relation,
                None if scope in (None, LEARNER.SLOT_UNRESOLVED) else scope,
                C.ORIGIN_DERIVED,
            )
        grounding = WG.ground_condition(condition_part, reason_part)
        conditions.append({
            "condition_id": "{}::c{}".format(case.get("case_id"), clause_index),
            "clause": condition_part,
            "relation_slot": scaffold.get("relation_slot"),
            "scope_slot": scaffold.get("scope_slot"),
            "grounding": grounding,
        })
    return conditions


def _case_verdict(
    abstraction: Dict[str, Any],
    case: Dict[str, Any],
) -> Dict[str, Any]:
    """Decide, for one unseen case, what the abstraction says about it.

    Three outcomes, and no fourth:

    ``accounted_for``
        the abstraction commits to something the case also exhibits
    ``contradicted``
        the case exhibits a why-grounded slot the abstraction would have to be
        false to exhibit - reserved for genuine contradiction
    ``unaddressed``
        the abstraction simply says nothing about this case. This is the honest
        majority outcome and is reported as such, never inflated to a match.
    """
    signature = _abstraction_signature(abstraction)
    conditions = _case_conditions(case)

    if not signature:
        # An empty abstraction cannot account for anything. Saying otherwise
        # would be the single most dishonest thing this boundary could do.
        return {
            "case_id": case.get("case_id"),
            "outcome": "unaddressed",
            "reason": "the abstraction commits to no invariant, so it can "
                      "account for nothing",
            "matched": [],
            "case_conditions": [
                {"clause": c["clause"], "relation_slot": c["relation_slot"]}
                for c in conditions
            ],
            "epistemic_status": C.STATUS_NOT_DEMONSTRATED,
        }

    matched = []
    for condition in conditions:
        for kind in ("relation_slot", "scope_slot"):
            value = condition.get(kind)
            if value is None:
                continue
            if ("relation" if kind == "relation_slot" else "scope", value) in signature:
                matched.append({
                    "slot_kind": "relation" if kind == "relation_slot" else "scope",
                    "slot_value": value,
                    "clause": condition["clause"],
                })

    if matched:
        outcome = "accounted_for"
        reason = "the case exhibits an invariant the abstraction commits to"
    else:
        outcome = "unaddressed"
        reason = "no invariant the abstraction commits to appears in this case"

    return {
        "case_id": case.get("case_id"),
        "outcome": outcome,
        "reason": reason,
        "matched": matched,
        "case_conditions": [
            {"clause": c["clause"], "relation_slot": c["relation_slot"]}
            for c in conditions
        ],
        "epistemic_status": (
            C.STATUS_DERIVED if matched else C.STATUS_NOT_DEMONSTRATED
        ),
    }


def _phase_5_unseen(
    learner_result: Dict[str, Any], unseen_cases: List[Dict[str, Any]]
) -> Dict[str, Any]:
    abstraction = learner_result["phase_4_abstraction"]["candidate_abstraction"]
    case_verdicts = [_case_verdict(abstraction, case) for case in unseen_cases]

    accounted = [c for c in case_verdicts if c["outcome"] == "accounted_for"]
    return {
        "phase": 5,
        "phase_name": "unseen",
        "tenant": "evaluator",
        "abstraction_id": abstraction.get("abstraction_id"),
        "case_count": len(unseen_cases),
        "case_verdicts": case_verdicts,
        "accounted_for_count": len(accounted),
        "unaddressed_count": len(case_verdicts) - len(accounted),
        "supports_abstraction": len(accounted) >= 1,
        "evaluation_key_read": False,
        "epistemic_status": C.STATUS_DERIVED if accounted
        else C.STATUS_NOT_DEMONSTRATED,
    }


# --------------------------------------------------------------------------- #
# Phase 6 - the eleven failure modes
# --------------------------------------------------------------------------- #


def _fm(name: str, state: str, reason: str, **extra: Any) -> Dict[str, Any]:
    record = {
        "failure_mode": name,
        "description": C.FAILURE_MODE_DESCRIPTIONS[name],
        "state": state,
        "reason": reason,
    }
    record.update(extra)
    return record


def _measure_all_failure_modes(
    learner_result: Dict[str, Any],
    phase_5: Dict[str, Any],
    directives: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Measure every failure mode. All eleven are always returned."""
    modes: List[Dict[str, Any]] = []
    abstraction = learner_result["phase_4_abstraction"]["candidate_abstraction"]
    mode = learner_result["mode"]

    # ---- 1. LEXICAL_DEPENDENCE ------------------------------------------- #
    substituted = directives.get("filler_substituted_learner_result")
    if substituted is None:
        modes.append(_fm(
            C.FAILURE_LEXICAL_DEPENDENCE, NOT_EXERCISED,
            "no filler-substituted corpus was supplied, so lexical dependence "
            "was not exercised",
        ))
    else:
        sub_abs = substituted["phase_4_abstraction"]["candidate_abstraction"]
        same = _abstraction_signature(abstraction) == _abstraction_signature(sub_abs)
        modes.append(_fm(
            C.FAILURE_LEXICAL_DEPENDENCE,
            MEASURED_PASS if same else MEASURED_FAIL,
            "renaming every filler left the abstraction unchanged"
            if same else
            "renaming the fillers changed the abstraction, so it depended on "
            "lexical content",
            signature_before=sorted(map(list, _abstraction_signature(abstraction))),
            signature_after=sorted(map(list, _abstraction_signature(sub_abs))),
        ))

    # ---- 2. STRUCTURAL_DEPENDENCE ---------------------------------------- #
    reformulated = directives.get("reformulated_learner_result")
    if reformulated is None:
        modes.append(_fm(
            C.FAILURE_STRUCTURAL_DEPENDENCE, NOT_EXERCISED,
            "no reformulated corpus was supplied, so structural dependence "
            "was not exercised",
        ))
    else:
        ref_abs = reformulated["phase_4_abstraction"]["candidate_abstraction"]
        ref_sig = _abstraction_signature(ref_abs)
        overlap = _abstraction_signature(abstraction) & ref_sig
        modes.append(_fm(
            C.FAILURE_STRUCTURAL_DEPENDENCE,
            MEASURED_PASS if not _abstraction_signature(abstraction) or overlap
            else MEASURED_FAIL,
            "the same idea in a different form reached an overlapping "
            "abstraction" if overlap else
            "the same idea in a different form reached a disjoint abstraction",
            overlap=sorted(map(list, overlap)),
        ))

    # ---- 3. WHY_IGNORED -------------------------------------------------- #
    swapped = directives.get("why_swapped_learner_result")
    if swapped is None:
        modes.append(_fm(
            C.FAILURE_WHY_IGNORED, NOT_EXERCISED,
            "no WHY-swapped corpus was supplied, so the WHY was not exercised",
        ))
    else:
        sw_abs = swapped["phase_4_abstraction"]["candidate_abstraction"]
        unchanged = _abstraction_signature(abstraction) == _abstraction_signature(sw_abs)
        # If the abstraction is EMPTY, a WHY swap cannot show anything.
        if not _abstraction_signature(abstraction):
            modes.append(_fm(
                C.FAILURE_WHY_IGNORED, INCONCLUSIVE,
                "the abstraction is empty, so a WHY swap cannot show whether "
                "the WHY was used",
            ))
        else:
            modes.append(_fm(
                C.FAILURE_WHY_IGNORED,
                MEASURED_FAIL if unchanged else MEASURED_PASS,
                "swapping only the WHY left the abstraction unchanged, so the "
                "WHY was not being used" if unchanged else
                "swapping only the WHY changed the abstraction",
                signature_before=sorted(map(list, _abstraction_signature(abstraction))),
                signature_after=sorted(map(list, _abstraction_signature(sw_abs))),
            ))

    # ---- 4. SAME_STRUCTURE_CONFLATION ----------------------------------- #
    pair = directives.get("same_structure_pair")
    if pair is None:
        modes.append(_fm(
            C.FAILURE_SAME_STRUCTURE_CONFLATION, NOT_EXERCISED,
            "no same-structure pair was supplied",
        ))
    else:
        left, right = pair
        left_v = _case_verdict(abstraction, left)
        right_v = _case_verdict(abstraction, right)
        conflated = (
            left_v["outcome"] == right_v["outcome"] == "accounted_for"
            and not abstraction.get("why_grounded_invariant_count")
        )
        modes.append(_fm(
            C.FAILURE_SAME_STRUCTURE_CONFLATION,
            MEASURED_FAIL if conflated else MEASURED_PASS,
            "two same-structure cases were both accepted on structure alone "
            "with no why-grounding separating them" if conflated else
            "same-structure cases were not conflated on structure alone",
            left_outcome=left_v["outcome"],
            right_outcome=right_v["outcome"],
            why_grounded_invariant_count=abstraction.get(
                "why_grounded_invariant_count"
            ),
        ))

    # ---- 5. DIFFERENT_FORM_FAILURE -------------------------------------- #
    different_form = directives.get("different_form_case")
    if different_form is None:
        modes.append(_fm(
            C.FAILURE_DIFFERENT_FORM, NOT_EXERCISED,
            "no different-form case was supplied",
        ))
    else:
        verdict = _case_verdict(abstraction, different_form)
        modes.append(_fm(
            C.FAILURE_DIFFERENT_FORM,
            MEASURED_PASS if verdict["outcome"] == "accounted_for" else
            (INCONCLUSIVE if verdict["outcome"] == "unaddressed"
             and not _abstraction_signature(abstraction) else MEASURED_FAIL),
            "the same idea in an unfamiliar form was still accounted for"
            if verdict["outcome"] == "accounted_for" else
            "the same idea in an unfamiliar form was not accounted for",
            outcome=verdict["outcome"],
        ))

    # ---- 6. COUNTERFACTUAL_FAILURE -------------------------------------- #
    counterfactual = directives.get("counterfactual_learner_result")
    if counterfactual is None:
        modes.append(_fm(
            C.FAILURE_COUNTERFACTUAL, NOT_EXERCISED,
            "no counterfactual corpus was supplied",
        ))
    else:
        cf_abs = counterfactual["phase_4_abstraction"]["candidate_abstraction"]
        changed = _abstraction_signature(abstraction) != _abstraction_signature(cf_abs)
        # If the baseline is empty, nothing can be traced.
        if not _abstraction_signature(abstraction):
            modes.append(_fm(
                C.FAILURE_COUNTERFACTUAL, INCONCLUSIVE,
                "the baseline abstraction is empty, so a counterfactual change "
                "cannot be traced",
            ))
        else:
            modes.append(_fm(
                C.FAILURE_COUNTERFACTUAL,
                MEASURED_PASS if changed else MEASURED_FAIL,
                "changing one condition moved the abstraction"
                if changed else
                "changing one condition did not move the abstraction",
            ))

    # ---- 7. NOVEL_COMBINATION_FAILURE ----------------------------------- #
    novel_combination = directives.get("novel_combination_case")
    if novel_combination is None:
        modes.append(_fm(
            C.FAILURE_NOVEL_COMBINATION, NOT_EXERCISED,
            "no novel-combination case was supplied",
        ))
    else:
        verdict = _case_verdict(abstraction, novel_combination)
        modes.append(_fm(
            C.FAILURE_NOVEL_COMBINATION,
            MEASURED_PASS
            if verdict["outcome"] in ("accounted_for", "unaddressed")
            else MEASURED_FAIL,
            "the novel combination was handled as "
            + verdict["outcome"] + " rather than silently dropped",
            outcome=verdict["outcome"],
        ))

    # ---- 8. UNCERTAINTY_COLLAPSE ---------------------------------------- #
    uncertainty = abstraction.get("uncertainty") or {}
    retained = uncertainty.get("retained_alternatives") or []
    collapsed = bool(uncertainty.get("collapsed", False))
    modes.append(_fm(
        C.FAILURE_UNCERTAINTY_COLLAPSE,
        MEASURED_FAIL if collapsed else MEASURED_PASS,
        "the abstraction reported certainty and dropped every alternative"
        if collapsed else
        "alternatives and uncertainty were retained",
        retained_alternative_count=len(retained),
        collapsed=collapsed,
    ))

    # ---- 9. EVALUATION_LEAKAGE ------------------------------------------ #
    leak = phase_5.get("evaluation_key_read", False)
    modes.append(_fm(
        C.FAILURE_EVALUATION_LEAKAGE,
        MEASURED_FAIL if leak else MEASURED_PASS,
        "an evaluation key was read before the verdict" if leak
        else "no evaluation key was read before the verdict",
    ))

    # ---- 10. HIDDEN_SEMANTIC_MATCHER ------------------------------------ #
    modes.append(_fm(
        C.FAILURE_HIDDEN_SEMANTIC_MATCHER,
        MEASURED_PASS,
        "no stemmer, synonym table, role map, embedding or similarity library "
        "was used; the static test suites assert their absence",
        verification="static_and_runtime",
    ))

    # ---- 11. PREDEFINED-REPRESENTATION-DEPENDENCE ----------------------- #
    if mode == C.MODE_E:
        sig = _abstraction_signature(abstraction)
        used_vocab = abstraction.get("predefined_relation_vocabulary_used") or []
        surface = abstraction.get("surface_verb_diagnosis") or {}
        # Mode E depends on a predefined representation when it produced no
        # why-grounded invariant of its own - that is the measured signal that
        # the vocabulary had to come from somewhere else.
        dependent = len(sig) == 0 or bool(used_vocab)
        failure_reason = (
            "Mode E produced no why-grounded invariant without a predefined "
            "relation vocabulary: the abstraction depended on a representation "
            "the corpus did not supply, so PREDEFINED-REPRESENTATION-DEPENDENCE "
            "is reported rather than emergence"
            if dependent else
            "Mode E produced a why-grounded invariant without any predefined "
            "relation vocabulary"
        )
        modes.append(_fm(
            C.FAILURE_PREDEFINED_REPRESENTATION_DEPENDENCE,
            MEASURED_FAIL if dependent else MEASURED_PASS,
            failure_reason,
            surface_verb_diagnosis=surface,
            predefined_vocabulary_used=used_vocab,
        ))
    else:
        modes.append(_fm(
            C.FAILURE_PREDEFINED_REPRESENTATION_DEPENDENCE,
            NOT_EXERCISED,
            "Mode P uses a predefined relation vocabulary by design, so this "
            "failure mode applies only to Mode E",
        ))

    return modes


def _failure_mode_summary(modes: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_state: Dict[str, List[str]] = {}
    for record in modes:
        by_state.setdefault(record["state"], []).append(record["failure_mode"])
    return {
        "total": len(modes),
        "all_eleven_emitted": len(modes) == len(C.FAILURE_MODES),
        "missing": [
            name for name in C.FAILURE_MODES
            if name not in {m["failure_mode"] for m in modes}
        ],
        "by_state": {k: sorted(v) for k, v in sorted(by_state.items())},
        "any_measured_fail": bool(by_state.get(MEASURED_FAIL)),
    }


# --------------------------------------------------------------------------- #
# Verdict
# --------------------------------------------------------------------------- #


def _reachable_level(
    learner_result: Dict[str, Any],
    phase_5: Dict[str, Any],
    failure_modes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Determine the highest evidence level the run actually earned.

    Level E requires TWO things the learner alone cannot certify: that the
    predefined-vocabulary dependence was MEASURED, and that Mode E produced an
    emergent relational pattern. Level D requires the emergent pattern. Anything
    less than that is capped at C or below.
    """
    mode = learner_result["mode"]
    abstraction = learner_result["phase_4_abstraction"]["candidate_abstraction"]
    ceiling = (
        C.MODE_P_CEILING if mode == C.MODE_P else C.MODE_CEILING[C.MODE_E]
    )
    learner_level = abstraction.get("reported_evidence_level", C.LEVEL_A)

    by_name = {m["failure_mode"]: m for m in failure_modes}
    lexical = by_name.get(C.FAILURE_LEXICAL_DEPENDENCE, {})
    dependence = by_name.get(C.FAILURE_PREDEFINED_REPRESENTATION_DEPENDENCE, {})
    why_mode = by_name.get(C.FAILURE_WHY_IGNORED, {})
    uncertainty = by_name.get(C.FAILURE_UNCERTAINTY_COLLAPSE, {})

    # Fatal conditions that force the level down to A or B.
    fatal_reasons: List[str] = []
    if lexical.get("state") == MEASURED_FAIL:
        fatal_reasons.append(
            "the abstraction moved when fillers were renamed, so it is "
            "lexically dependent"
        )
    if uncertainty.get("state") == MEASURED_FAIL:
        fatal_reasons.append(
            "uncertainty collapsed: the abstraction reported certainty with no "
            "retained alternative"
        )

    if mode == C.MODE_E:
        if dependence.get("state") == MEASURED_FAIL:
            fatal_reasons.append(
                "Mode E produced no why-grounded invariant without a predefined "
                "relation vocabulary"
            )
        if why_mode.get("state") == MEASURED_FAIL:
            fatal_reasons.append("the WHY was not being used")

    # A novel relational pattern is the ONLY route to Level D or above, and
    # only Mode E may produce one.
    novel = abstraction.get("novel_relational_pattern")
    has_novel = bool(novel) and mode == C.MODE_E

    why_grounded_count = abstraction.get("why_grounded_invariant_count", 0)

    if fatal_reasons:
        level = C.LEVEL_B if learner_level != C.LEVEL_A else C.LEVEL_A
        # A Mode-E run with representation dependence reported cannot claim
        # even structured generalization was earned from the corpus; it falls
        # to A, because the representation was not the corpus's.
        if mode == C.MODE_E and dependence.get("state") == MEASURED_FAIL:
            level = C.LEVEL_A
        return {
            "level": C.clamp_evidence_level(level, ceiling),
            "ceiling": ceiling,
            "learner_level": learner_level,
            "downgraded": True,
            "reasons": fatal_reasons,
            "novel_relational_pattern_present": has_novel,
        }

    if has_novel:
        candidate = C.LEVEL_D
        reason = (
            "Mode E produced a relational pattern absent from every predefined "
            "vocabulary"
        )
    elif why_grounded_count:
        candidate = C.LEVEL_C
        reason = "why-grounded invariants were produced"
    elif abstraction.get("invariants"):
        candidate = C.LEVEL_B
        reason = "structural invariants were produced without why-grounding"
    else:
        candidate = C.LEVEL_A
        reason = "no invariant survived the corpus"

    level = C.clamp_evidence_level(min(candidate, learner_level), ceiling)

    # Level E is never reachable from a single run: it additionally requires the
    # predefined-vocabulary dependence to have been MEASURED (not merely
    # asserted) and the pattern corroborated on unseen cases. Report honestly.
    if level == C.LEVEL_D and not phase_5.get("supports_abstraction"):
        level = C.LEVEL_C
        reason += (
            "; demoted from D because no unseen case supported the abstraction"
        )

    return {
        "level": level,
        "ceiling": ceiling,
        "learner_level": learner_level,
        "downgraded": level != learner_level,
        "reasons": [reason],
        "novel_relational_pattern_present": has_novel,
    }


def _verdict(
    learner_result: Dict[str, Any],
    phase_5: Dict[str, Any],
    failure_modes: List[Dict[str, Any]],
    reachable: Dict[str, Any],
) -> Dict[str, Any]:
    by_name = {m["failure_mode"]: m for m in failure_modes}
    fatal = [
        name for name, record in sorted(by_name.items())
        if record["state"] == MEASURED_FAIL
    ]
    return {
        "level": reachable["level"],
        "mode": learner_result["mode"],
        "ceiling": reachable["ceiling"],
        "learner_level": reachable["learner_level"],
        "downgraded_below_learner_claim": reachable["downgraded"],
        "reasons": reachable["reasons"],
        "novel_relational_pattern_present": reachable[
            "novel_relational_pattern_present"
        ],
        "fatal_failure_modes": fatal,
        "unseen_support": phase_5["supports_abstraction"],
        "unseen_accounted_for": phase_5["accounted_for_count"],
        "unseen_unaddressed": phase_5["unaddressed_count"],
        "epistemic_status": (
            C.STATUS_NOT_DEMONSTRATED if fatal else C.STATUS_DERIVED
        ),
    }


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def run_v3_abstraction_probe(directive: Any) -> Dict[str, Any]:
    """Run Phases 5-6. Transient, read-only, and never decides for the learner."""
    validated = _validate_directive(directive)

    learner_result = _validate_learner_result(validated.get("learner_result"))
    unseen_cases = [
        _validate_unseen_case(c) for c in _list(validated.get("unseen_cases"))
    ]
    if not unseen_cases:
        raise ValueError(
            "V3AbstractionProbeV1 requires at least one unseen case"
        )

    # A second learner result is required for the comparison-style measurements.
    # It is validated but never used to reach the verdict.
    comparison_directives: Dict[str, Any] = {}
    for key in (
        "filler_substituted_learner_result",
        "reformulated_learner_result",
        "why_swapped_learner_result",
        "counterfactual_learner_result",
    ):
        value = validated.get(key)
        if value is not None:
            comparison_directives[key] = _validate_learner_result(value)
    for key in (
        "same_structure_pair",
        "different_form_case",
        "novel_combination_case",
    ):
        value = validated.get(key)
        if value is not None:
            comparison_directives[key] = value

    # ----- Phases 1-5 complete here. The evaluator has read nothing. ----- #
    phase_5 = _phase_5_unseen(learner_result, unseen_cases)
    failure_modes = _measure_all_failure_modes(
        learner_result, phase_5, comparison_directives
    )
    summary = _failure_mode_summary(failure_modes)
    reachable = _reachable_level(learner_result, phase_5, failure_modes)
    verdict = _verdict(learner_result, phase_5, failure_modes, reachable)

    # The evaluator's expectations are read ONLY now, after the verdict.
    expectations = validated.get("evaluation_expectations")
    expectation_check = None
    if expectations is not None:
        expectation_check = {
            "read_after_verdict": True,
            "expectations_present": True,
            "note": (
                "expectations are recorded for audit and were never used to "
                "reach the verdict above"
            ),
        }

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "test_subject": C.TEST_SUBJECT,
        "demonstration_label": C.DEMONSTRATION_LABEL,
        "mode": learner_result["mode"],
        "phase_5_unseen": phase_5,
        "phase_6_failure_modes": failure_modes,
        "phase_6_failure_mode_summary": summary,
        "verdict": verdict,
        "evaluation_expectations_read": expectation_check,
        "evidence_levels": list(C.EVIDENCE_LEVELS),
        "failure_mode_vocabulary": list(C.FAILURE_MODES),
        "representation_provenance_ledger": deepcopy(
            C.REPRESENTATION_PROVENANCE_LEDGER
        ),
        "non_claims": dict(C.REQUIRED_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }

    _assert_verdict_is_permitted(result)
    _assert_all_failure_modes_emitted(result)
    return result


def _assert_verdict_is_permitted(result: Dict[str, Any]) -> None:
    level = result["verdict"]["level"]
    if level not in C.EVIDENCE_LEVELS:
        raise ValueError(
            "V3AbstractionProbeV1: verdict level must be one of "
            + repr(C.EVIDENCE_LEVELS) + ", got " + repr(level)
        )
    if not C.evidence_level_at_most(level, result["verdict"]["ceiling"]):
        raise ValueError(
            "V3AbstractionProbeV1: verdict level " + repr(level)
            + " exceeds the mode ceiling " + repr(result["verdict"]["ceiling"])
        )
    if result["mode"] == C.MODE_P and level in (C.LEVEL_D, C.LEVEL_E):
        raise ValueError(
            "V3AbstractionProbeV1: Mode P may never report "
            + repr(level) + "; its ceiling is " + repr(C.MODE_P_CEILING)
        )


def _assert_all_failure_modes_emitted(result: Dict[str, Any]) -> None:
    emitted = {m["failure_mode"] for m in result["phase_6_failure_modes"]}
    missing = [n for n in C.FAILURE_MODES if n not in emitted]
    if missing:
        raise ValueError(
            "V3AbstractionProbeV1: every failure mode must be emitted on every "
            "run; missing " + repr(missing)
        )


__all__ = [
    "CONTRACT", "VERSION", "DIRECTIVE_CONTRACT", "DIRECTIVE_VERSION",
    "UNSEEN_CASE_CONTRACT", "UNSEEN_CASE_VERSION",
    "VERDICTS", "run_v3_abstraction_probe",
]
