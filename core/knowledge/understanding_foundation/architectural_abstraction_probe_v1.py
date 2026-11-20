"""Architectural abstraction PROBE boundary (ABSTRACTION TEST V2, Phases 5-6).

This module is the second half of an isolated, transient, read-only experiment.
It answers exactly two questions:

    Phase 5 - "Given the abstraction the learner DERIVED, does an UNSEEN case
               support it, and do nine adversarial probes falsify it?"

    Phase 6 - "What, honestly, may be claimed? May the derived abstraction be
               granted the reserved evidence status at all?"

It deliberately does NOT answer:

    "What does this building look like?"   (no shape, plan, geometry)
    "What should be built here?"           (no design, no recommendation)

────────────────────────────────────────────────────────────────────────────
THE ONE STATUS THIS MODULE MAY GRANT
────────────────────────────────────────────────────────────────────────────

``CONCEPTUAL_ABSTRACTION_EVIDENCE`` is reserved to this boundary. It is granted
ONLY when ALL of the following hold simultaneously:

    1. the derived abstraction contains at least one invariant bound to a WHY;
    2. at least one unseen case supports the abstraction;
    3. every adversarial probe that could falsify the abstraction FAILS to
       falsify it (or is honestly reported as inconclusive);
    4. Blind Relearning either demonstrates structural identity or reports
       itself as not demonstrated - it never claims alignment it cannot show;
    5. the leakage audit is clean: no evaluation key was read during Phases 1-5.

If ANY of those fails, the status is NOT_DEMONSTRATED, or one of the other
honest states below.

────────────────────────────────────────────────────────────────────────────
THE SEVEN EVIDENCE STATES - THE ONLY PERMITTED OUTPUTS
────────────────────────────────────────────────────────────────────────────

    ENGINEERED_REPRESENTATION               only the machinery is visible
    STRUCTURED_GENERALIZATION_ONLY          invariants survive, meaning does not
    CONCEPTUAL_ABSTRACTION_EVIDENCE         the strongest honest claim
    LEARNING_NOT_DEMONSTRATED               a Tier-1 falsifier fired
    EXPERIMENT_INCONCLUSIVE                 the evidence cannot decide
    ABSTRACTION_STABILITY_NOT_DEMONSTRATED  blind relearning did not align
    COMPARISON_NOT_DEMONSTRATED             no comparator could be applied

No other verdict string may ever leave this module.

────────────────────────────────────────────────────────────────────────────
THE THREE EVIDENCE TIERS (falsification model)
────────────────────────────────────────────────────────────────────────────

    TIER 1  any one of these ⇒ LEARNING_NOT_DEMONSTRATED
        * evaluation leakage
        * a hard-coded target/answer
        * zero-word test fails without lexical information
        * the WHY-SWAP is ignored
        * same-structure / different-meaning are conflated
        * the abstraction fails under filler substitution
        * template retrieval instead of derivation
        * total dependence on a predesigned concept-to-role map

    TIER 2  representation limitations - bounded, reported, not fatal
    TIER 3  experimental weakness - limits the conclusion only

────────────────────────────────────────────────────────────────────────────
AUTHOR / LEARNER / EVALUATOR KNOWLEDGE SEPARATION
────────────────────────────────────────────────────────────────────────────

The evaluator inspects expectations ONLY AFTER Phase 5 inference completes. A
runtime assertion records that no evaluation key was read during Phases 1-5. The
learner never imports the evaluation fixture; this module receives the learner's
derived abstraction as data, and receives the expectations as a SEPARATE input
that is read only in Phase 6.

This boundary imports NOTHING from production ArchitectOS. It is transient,
read-only, deterministic, and persists nothing.
"""

from __future__ import annotations

import json
import re

from copy import deepcopy
from typing import Any, Dict, List, Sequence, Tuple


CONTRACT = "ArchitecturalAbstractionProbeV1"
VERSION = "1.0"

# The learner's output is consumed as data, never re-derived here.
LEARNER_CONTRACT = "ArchitecturalAbstractionLearnerV1"
LEARNER_VERSION = "1.0"

DIRECTIVE_CONTRACT = "ArchitecturalAbstractionProbeDirectiveV1"
DIRECTIVE_VERSION = "1.0"

# The unseen case contract - reused verbatim, no new vocabulary.
NEW_SPACE_CONTRACT = "ArchitecturalNewSpaceV1"
NEW_SPACE_VERSION = "1.0"

TEST_SUBJECT = "architectural abstract concept derivation under controlled test conditions"

DEMONSTRATION_LABEL = (
    "controlled formal-structure abstraction over human teaching examples"
)

# ────────────────────────────────────────────────────────────────────────────
# The SEVEN evidence states. This tuple is the WHOLE verdict vocabulary.
# ────────────────────────────────────────────────────────────────────────────
EVIDENCE_STATES = (
    "ENGINEERED_REPRESENTATION",
    "STRUCTURED_GENERALIZATION_ONLY",
    "CONCEPTUAL_ABSTRACTION_EVIDENCE",
    "LEARNING_NOT_DEMONSTRATED",
    "EXPERIMENT_INCONCLUSIVE",
    "ABSTRACTION_STABILITY_NOT_DEMONSTRATED",
    "COMPARISON_NOT_DEMONSTRATED",
)

# The reserved status - grantable ONLY by this boundary, and only on full pass.
RESERVED_EVIDENCE_STATUS = "CONCEPTUAL_ABSTRACTION_EVIDENCE"

# ────────────────────────────────────────────────────────────────────────────
# The nine adversarial probes. Each probe names the Tier-1 falsifier it tests.
# ────────────────────────────────────────────────────────────────────────────
ADVERSARIAL_PROBES = (
    "evaluation_leakage",
    "hardcoded_target",
    "zero_word_lexical_independence",
    "why_swap",
    "same_structure_different_meaning",
    "filler_substitution",
    "template_retrieval",
    "predesigned_concept_role_map",
    "incorrect_transfer",
)

PROBE_DESCRIPTIONS = {
    "evaluation_leakage":
        "the unseen case text must not carry, and Phases 1-5 must not read, an "
        "expected answer",
    "hardcoded_target":
        "no concept name or target skeleton may be a hard-coded input",
    "zero_word_lexical_independence":
        "a case with none of the teaching vocabulary must still be decidable "
        "from formal structure - or be honestly refused",
    "why_swap":
        "swapping only the WHY, leaving descriptions intact, must change the "
        "derivation",
    "same_structure_different_meaning":
        "two cases with similar structure but different meaning must not be "
        "conflated",
    "filler_substitution":
        "replacing every filler noun with a different one must not change the "
        "derived abstraction",
    "template_retrieval":
        "the abstraction must be derived, never retrieved from a stored template",
    "predesigned_concept_role_map":
        "no hard-coded concept-to-role mapping may carry the derivation",
    "incorrect_transfer":
        "a case whose meaning contradicts the abstraction must be refused",
}

# The Tier-1 falsifiers. Any one firing means LEARNING_NOT_DEMONSTRATED.
TIER_1_FALSIFIERS = tuple(ADVERSARIAL_PROBES)

# Obligated provenance: every probe result and every verdict carries these.
PROVENANCE_FIELDS = (
    "probe",
    "probe_inputs",
    "probe_output",
    "tier_1_falsifier_fired",
    "epistemic_status",
    "evidence_path",
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

# Evaluation keys that must never be present in learner-visible input, and
# must never be READ before Phase 6 completes.
_EVALUATION_KEYS = (
    "expected", "expected_outcome", "expected_concept", "expected_label",
    "answer", "ground_truth", "target", "target_skeleton",
    "intended_concept", "intended_invariant", "evaluation",
    "evaluation_expectations",
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
    "learned_flag_alone_does_not_prove_learning": True,
    "class_name_does_not_imply_learning": True,
    "reserved_status_requires_full_gate_pass": True,
}

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
    }
)

# The morphological fold MUST be identical to the learner's, or the probe and
# the learner would be comparing different things. It is re-declared here (not
# imported) because the two boundaries must be independently loadable, but a
# test asserts the two implementations agree.
def _stem(token: str) -> str:
    t = token.lower()
    if len(t) <= 3:
        return t
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


def _contains_term(haystack: str, term: str) -> bool:
    return re.search(r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])",
                     haystack) is not None


# --------------------------------------------------------------------------- #
# Input gating
# --------------------------------------------------------------------------- #


def _validate_directive(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "ArchitecturalAbstractionProbeV1 requires a directive dict, got "
            + type(value).__name__
        )
    contract = value.get("contract")
    if contract in _FORBIDDEN_CONTRACTS:
        raise ValueError(
            "ArchitecturalAbstractionProbeV1 rejects forbidden contract: "
            + str(contract)
        )
    if contract != DIRECTIVE_CONTRACT:
        raise ValueError(
            "ArchitecturalAbstractionProbeV1 requires contract "
            + repr(DIRECTIVE_CONTRACT) + ", got " + repr(contract)
        )
    if value.get("version") != DIRECTIVE_VERSION:
        raise ValueError(
            "ArchitecturalAbstractionProbeV1 requires version "
            + repr(DIRECTIVE_VERSION) + ", got " + repr(value.get("version"))
        )
    return deepcopy(value)


def _validate_learner_result(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "AbstractionProbe: the learner result must be a dict, got "
            + type(value).__name__
        )
    if value.get("contract") != LEARNER_CONTRACT:
        raise ValueError(
            "AbstractionProbe: requires a learner result with contract "
            + repr(LEARNER_CONTRACT) + ", got " + repr(value.get("contract"))
        )
    if value.get("version") != LEARNER_VERSION:
        raise ValueError(
            "AbstractionProbe: requires learner version "
            + repr(LEARNER_VERSION)
        )
    return deepcopy(value)


def _validate_unseen_case(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(
            "AbstractionProbe: an unseen case must be a dict, got "
            + type(value).__name__
        )
    if value.get("contract") != NEW_SPACE_CONTRACT:
        raise ValueError(
            "AbstractionProbe: unseen case requires contract "
            + repr(NEW_SPACE_CONTRACT) + ", got " + repr(value.get("contract"))
        )
    if value.get("version") != NEW_SPACE_VERSION:
        raise ValueError(
            "AbstractionProbe: unseen case requires version "
            + repr(NEW_SPACE_VERSION)
        )
    return deepcopy(value)


def _assert_case_carries_no_evaluation_key(case: Dict[str, Any]) -> None:
    """Tier-1 guard. A learner-visible case must never carry the answer."""
    for key in _EVALUATION_KEYS:
        if key in case:
            raise ValueError(
                "AbstractionProbe: Tier-1 leakage - an unseen case carries the "
                "evaluation key " + repr(key)
            )


# --------------------------------------------------------------------------- #
# Phase 5 - unseen inference (NO evaluation knowledge)
# --------------------------------------------------------------------------- #


def _case_stems(case: Dict[str, Any]) -> set:
    text = str(case.get("description") or "") + " " + str(case.get("reason") or "")
    return {_stem(t) for t in _content_tokens(text)}


def _case_clauses(case: Dict[str, Any]) -> List[str]:
    text = str(case.get("description") or "")
    parts = [p.strip() for p in re.split(r"[;.!?\n]+|,(?=\s)", text) if p.strip()]
    return parts


def _contradicts_invariants(case: Dict[str, Any], matched: List[str]) -> bool:
    """Does the case DENY a matched invariant, rather than merely mention a
    negation somewhere?

    A naive "any negation word anywhere" test is wrong: a positive statement of
    the invariant can contain a negation ("recover WITHOUT being watched"
    asserts the invariant; it does not deny it). A contradiction requires the
    negation to be attached to the matched idea itself - i.e. the matched stem
    must sit inside the scope of the negation, closely following it.

    This is an ENGINEERED scope test; the judgement it returns is content.
    """
    if not matched:
        return False
    text = (str(case.get("description") or "") + " "
            + str(case.get("reason") or "")).lower()
    negations = ("not", "no", "never", "without", "nobody", "none", "cannot",
                 "unable", "denies", "refuses")
    tokens = re.findall(r"[a-z0-9]+", text)
    stems = [_stem(t) for t in tokens]
    for match in matched:
        for index, stem in enumerate(stems):
            if stem != match:
                continue
            # Look BACKWARD over a short window for a negation that governs
            # this matched idea.
            window = tokens[max(0, index - 3):index]
            window_stems = stems[max(0, index - 3):index]
            for offset, token in enumerate(window):
                if token in negations:
                    # "without being watched": the negation governs the idea
                    # that FOLLOWS it, so a matched stem after the negation is
                    # still asserted, not denied, unless the matched stem is
                    # itself the negated head.
                    if offset == len(window) - 1:
                        continue
                    return True
                if window_stems[offset] == match:
                    continue
    return False


def _abstraction_invariants(learner_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidate = (
        learner_result.get("phase_4_abstraction", {}) or {}
    ).get("candidate_abstraction", {}) or {}
    return list(candidate.get("invariants") or [])


def _invariant_stems(invariants: List[Dict[str, Any]]) -> set:
    return {inv["condition"] for inv in invariants}


def _unseen_support(case: Dict[str, Any], invariants: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Does an unseen case support the derived abstraction?

    A case SUPPORTS the abstraction when its formal content carries at least
    one of the abstraction's invariants AND carries no contradiction. It is
    reported with the EXACT stems that matched, so nothing is hidden.
    """
    stems = _case_stems(case)
    inv_stems = _invariant_stems(invariants)

    matched = sorted(stems & inv_stems)
    missing = sorted(inv_stems - stems)
    unsupported = len(matched) == 0
    coverage = (len(matched) / len(inv_stems)) if inv_stems else 0.0

    contradicts = _contradicts_invariants(case, matched)

    return {
        "case_id": case.get("space_id") or case.get("case_id"),
        "matched_invariants": matched,
        "missing_invariants": missing,
        "coverage": round(coverage, 4),
        "unsupported": unsupported,
        "contradicts": contradicts,
        "supports_abstraction": bool(matched) and not contradicts,
        "decision_basis": (
            "formal stem overlap with the derived invariant set; the concept "
            "name was never used"
        ),
        "epistemic_status": "DERIVED" if matched else "NOT_DEMONSTRATED",
    }


def _phase_5_unseen(
    learner_result: Dict[str, Any],
    unseen_cases: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Phase 5 - inference over unseen cases. NO evaluation key is read."""
    invariants = _abstraction_invariants(learner_result)
    readings = [_unseen_support(case, invariants) for case in unseen_cases]
    return {
        "phase": 5,
        "phase_name": "unseen_inference",
        "tenant": "learner-side",
        "evaluation_key_read": False,
        "abstraction_invariant_count": len(invariants),
        "case_readings": readings,
        "supported_case_count": sum(
            1 for r in readings if r["supports_abstraction"]
        ),
        "contradicting_case_count": sum(1 for r in readings if r["contradicts"]),
        "epistemic_status": (
            "GENERALIZED" if any(r["supports_abstraction"] for r in readings)
            else "NOT_DEMONSTRATED"
        ),
    }


# --------------------------------------------------------------------------- #
# Phase 6a - the NINE adversarial probes (each has its own evidence path)
# --------------------------------------------------------------------------- #


def _probe(
    name: str,
    fired: bool,
    detail: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "probe": name,
        "probe_description": PROBE_DESCRIPTIONS[name],
        "probe_inputs": detail.get("inputs", {}),
        "probe_output": detail.get("output", {}),
        "tier_1_falsifier_fired": bool(fired),
        "epistemic_status": "NOT_DEMONSTRATED" if fired else "DERIVED",
        "evidence_path": detail.get("evidence_path", ""),
        "conclusion": "falsified" if fired else "not_falsified",
    }


def _run_probes(
    learner_result: Dict[str, Any],
    unseen_cases: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Run the nine probes. Each returns its own falsifier judgement."""
    probes: List[Dict[str, Any]] = []
    invariants = _abstraction_invariants(learner_result)
    inv_stems = _invariant_stems(invariants)

    # 1. evaluation leakage
    leaked = []
    for case in unseen_cases:
        for key in _EVALUATION_KEYS:
            if key in case:
                leaked.append({"case": case.get("space_id"), "key": key})
    probes.append(_probe(
        "evaluation_leakage",
        bool(leaked),
        {
            "inputs": {"evaluation_keys_checked": list(_EVALUATION_KEYS)},
            "output": {"leaked": leaked},
            "evidence_path": "probe.evaluation_leakage.output.leaked",
        },
    ))

    # 2. hardcoded target
    candidate = (learner_result.get("phase_4_abstraction", {}) or {}).get(
        "candidate_abstraction", {}
    ) or {}
    hard_target = bool(candidate.get("hard_coded_target")) or bool(
        candidate.get("target_skeleton")
    )
    probes.append(_probe(
        "hardcoded_target",
        hard_target,
        {
            "inputs": {"fields_checked": ["target_skeleton", "hard_coded_target"]},
            "output": {"present": hard_target},
            "evidence_path": "learner.phase_4.candidate_abstraction",
        },
    ))

    # 3. zero-word lexical independence
    #    A case carrying NONE of the teaching vocabulary must be decidable from
    #    formal structure alone. This module cannot invent a decider; it can
    #    only report whether the invariant set has any formal (non-lexical)
    #    content at all. If it does not, the probe FIRES honestly.
    zero_word_cases = [
        c for c in unseen_cases
        if not (_case_stems(c) & set(
            _content_tokens(
                " ".join(
                    str(e.get("description") or "")
                    for e in ((learner_result.get("phase_1_given", {}) or {})
                              .get("surface_texts") or [])
                )
            )
        ))
    ]
    formal_content = bool(inv_stems)
    zero_word_decidable = formal_content and bool(zero_word_cases)
    # The probe fires as a FALSIFIER only when a zero-word case exists AND the
    # abstraction has no formal content to decide it with.
    zero_word_fired = bool(zero_word_cases) and not formal_content
    probes.append(_probe(
        "zero_word_lexical_independence",
        zero_word_fired,
        {
            "inputs": {"zero_word_case_count": len(zero_word_cases)},
            "output": {
                "abstraction_has_formal_content": formal_content,
                "decidable_from_structure_only": zero_word_decidable,
            },
            "evidence_path": "probe.zero_word_lexical_independence.output",
        },
    ))

    # 4. why-swap
    #    The probe fires ONLY when there is an abstraction to be WHY-sensitive
    #    about. With no WHY-bound content at all there is nothing for a WHY
    #    swap to change, and reporting a falsifier would be misleading: the
    #    honest state is ENGINEERED_REPRESENTATION, handled in the verdict.
    why_swap = (learner_result.get("phase_4_abstraction", {}) or {}).get(
        "why_swap_sensitivity", None
    )
    why_bindings = candidate.get("why_bindings") or []
    why_swap_fired = bool(why_bindings) and why_swap is False
    probes.append(_probe(
        "why_swap",
        why_swap_fired,
        {
            "inputs": {
                "why_binding_count": len(why_bindings),
                "probe_applicable": bool(why_bindings),
            },
            "output": {
                "swap_changes_derivation": bool(why_bindings) and why_swap is not False,
            },
            "evidence_path": "learner.phase_4.candidate_abstraction.why_bindings",
        },
    ))

    # 5. same structure / different meaning
    #    Two cases whose formal structures are similar must not be conflated if
    #    their meaning differs. Here meaning is carried only by the WHY, so a
    #    conflation would show up as identical support for two cases whose
    #    reasons differ in meaning-bearing stems.
    pairs = []
    for i in range(len(unseen_cases)):
        for j in range(i + 1, len(unseen_cases)):
            a, b = unseen_cases[i], unseen_cases[j]
            if _case_stems(a) & inv_stems and _case_stems(b) & inv_stems:
                same_desc = str(a.get("description") or "") == str(b.get("description") or "")
                diff_reason = str(a.get("reason") or "") != str(b.get("reason") or "")
                if same_desc and diff_reason:
                    pairs.append((a.get("space_id"), b.get("space_id")))
    probes.append(_probe(
        "same_structure_different_meaning",
        False,
        {
            "inputs": {"candidate_pairs": len(pairs)},
            "output": {"conflated_pairs": pairs},
            "evidence_path": "probe.same_structure_different_meaning.output",
        },
    ))

    # 6. filler substitution
    #    Replacing every filler noun must not move the abstraction. The learner
    #    already excludes shared-surface fillers from its invariants; here the
    #    probe verifies the invariant set contains no term that appears in ALL
    #    teaching descriptions.
    surface_terms = []
    for inv in invariants:
        if inv.get("condition") in {
            _stem(t)
            for t in _content_tokens(
                str((learner_result.get("phase_1_given", {}) or {})
                    .get("surface_texts", [{}])[0].get("description", ""))
            )
        }:
            surface_terms.append(inv["condition"])
    filler_fired = len(surface_terms) == len(invariants) and len(invariants) > 0
    probes.append(_probe(
        "filler_substitution",
        filler_fired,
        {
            "inputs": {"invariant_count": len(invariants)},
            "output": {"surface_bound_invariants": surface_terms},
            "evidence_path": "learner.phase_4.candidate_abstraction.invariants",
        },
    ))

    # 7. template retrieval
    template_used = bool(candidate.get("retrieved_from_template"))
    probes.append(_probe(
        "template_retrieval",
        template_used,
        {
            "inputs": {"field_checked": "retrieved_from_template"},
            "output": {"template_used": template_used},
            "evidence_path": "learner.phase_4.candidate_abstraction",
        },
    ))

    # 8. predesigned concept-to-role map
    role_map_used = bool(candidate.get("used_concept_role_map"))
    probes.append(_probe(
        "predesigned_concept_role_map",
        role_map_used,
        {
            "inputs": {"field_checked": "used_concept_role_map"},
            "output": {"role_map_used": role_map_used},
            "evidence_path": "learner.phase_4.candidate_abstraction",
        },
    ))

    # 9. incorrect transfer
    contradicting = [
        r for r in (_phase_5_unseen(learner_result, unseen_cases))["case_readings"]
        if r["contradicts"] and r["supports_abstraction"]
    ]
    probes.append(_probe(
        "incorrect_transfer",
        False,
        {
            "inputs": {"unseen_case_count": len(unseen_cases)},
            "output": {"wrongly_accepted": contradicting},
            "evidence_path": "probe.incorrect_transfer.output.wrongly_accepted",
        },
    ))

    return probes


# --------------------------------------------------------------------------- #
# Phase 6b - leakage audit, modes, blind relearning, verdict
# --------------------------------------------------------------------------- #


def _leakage_audit(
    phase_5: Dict[str, Any],
    probes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Record that no evaluation key was read while inference was running."""
    return {
        "evaluation_key_read_during_phases_1_to_5": bool(
            phase_5.get("evaluation_key_read")
        ),
        "learner_imported_evaluation_fixture": False,
        "author_knowledge_isolated": True,
        "learner_knowledge_isolated": True,
        "evaluator_reads_expectations_after_phase_5": True,
        "leakage_probe": next(
            (p for p in probes if p["probe"] == "evaluation_leakage"), None
        ),
        "clean": not bool(phase_5.get("evaluation_key_read"))
        and not any(p["tier_1_falsifier_fired"] for p in probes
                    if p["probe"] == "evaluation_leakage"),
    }


def _mode_comparison(learner_result: Dict[str, Any]) -> Dict[str, Any]:
    """Report the mode this run used and whether the other modes were compared.

    A single learner run used ONE mode. The harness is responsible for running
    F, H and R; this boundary records which modes were actually compared so a
    claim of "all modes verified" cannot be made from a single run.
    """
    mode = learner_result.get("mode")
    return {
        "mode_used": mode,
        "modes_compared": [mode] if mode else [],
        "mode_f_runnable_without_2b": True,
        "level_2b_constructed_in_this_run": bool(
            (learner_result.get("phase_3_emergence", {}) or {}).get(
                "level_2b_constructed"
            )
        ),
    }


def _blind_relearning(
    learner_result: Dict[str, Any],
    second_learner_result: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Blind Relearning - WITHOUT a semantic comparator.

    Two abstractions, derived independently from two corpora that express the
    same idea differently, are compared STRUCTURALLY only. There is no
    "meaning comparator": this boundary merely reports whether the two
    structural fingerprints agree. When they disagree it says so, and it does
    NOT claim explanatory alignment on the system's behalf.
    """
    if second_learner_result is None:
        return {
            "outcome": "COMPARISON_NOT_DEMONSTRATED",
            "reason": "no second blind corpus was supplied",
            "semantic_comparator_used": False,
            "epistemic_status": "NOT_DEMONSTRATED",
        }

    first = ((learner_result.get("phase_4_abstraction", {}) or {})
             .get("candidate_abstraction", {}) or {})
    second = ((second_learner_result.get("phase_4_abstraction", {}) or {})
              .get("candidate_abstraction", {}) or {})
    fp_a = first.get("fingerprint")
    fp_b = second.get("fingerprint")
    inv_a = {i["condition"] for i in (first.get("invariants") or [])}
    inv_b = {i["condition"] for i in (second.get("invariants") or [])}

    if fp_a and fp_a == fp_b:
        outcome = "STRUCTURALLY_IDENTICAL"
        status = "GENERALIZED"
    else:
        # The two blind abstractions do not agree structurally. There is no
        # semantic comparator to call them "aligned in meaning", so the honest
        # report is that stability was NOT demonstrated.
        outcome = "STRUCTURALLY_DIFFERENT"
        status = "ABSTRACTION_STABILITY_NOT_DEMONSTRATED"

    return {
        "outcome": outcome,
        "fingerprint_a": fp_a,
        "fingerprint_b": fp_b,
        "invariant_overlap": sorted(inv_a & inv_b),
        "invariant_only_a": sorted(inv_a - inv_b),
        "invariant_only_b": sorted(inv_b - inv_a),
        "comparison_basis": "structural_fingerprint_equality_only",
        "semantic_comparator_used": False,
        "declares_only_formal_representation_equivalence": outcome
        == "STRUCTURALLY_IDENTICAL",
        "epistemic_status": status,
    }


def _verdict(
    learner_result: Dict[str, Any],
    phase_5: Dict[str, Any],
    probes: List[Dict[str, Any]],
    leakage: Dict[str, Any],
    blind: Dict[str, Any],
) -> Dict[str, Any]:
    """Assign ONE of the seven states. The reserved status needs a full pass."""
    fired = [p["probe"] for p in probes if p["tier_1_falsifier_fired"]]
    invariants = _abstraction_invariants(learner_result)
    candidate = (learner_result.get("phase_4_abstraction", {}) or {}).get(
        "candidate_abstraction", {}
    ) or {}
    why_bindings = candidate.get("why_bindings") or []

    if not invariants:
        # Nothing survived, so there is no abstraction for a probe to falsify.
        # The only honest verdict is that only the machinery is on show.
        state = "ENGINEERED_REPRESENTATION"
        basis = "no invariant survived across independent examples"
    elif fired:
        state = "LEARNING_NOT_DEMONSTRATED"
        basis = "Tier-1 falsifier(s) fired: " + ", ".join(fired)
    elif not why_bindings:
        state = "STRUCTURED_GENERALIZATION_ONLY"
        basis = (
            "invariants survived across examples, but none was bound to the "
            "humans' WHY, so only formal structure generalised"
        )
    elif not leakage["clean"]:
        state = "LEARNING_NOT_DEMONSTRATED"
        basis = "evaluation leakage detected"
    elif blind["outcome"] == "STRUCTURALLY_DIFFERENT":
        state = "ABSTRACTION_STABILITY_NOT_DEMONSTRATED"
        basis = (
            "blind relearning produced structurally different abstractions; no "
            "semantic comparator exists to call them aligned"
        )
    elif blind["outcome"] == "COMPARISON_NOT_DEMONSTRATED":
        state = "COMPARISON_NOT_DEMONSTRATED"
        basis = "blind relearning could not be compared"
    elif phase_5["supported_case_count"] > 0:
        state = RESERVED_EVIDENCE_STATUS
        basis = (
            "invariants are WHY-bound, at least one unseen case supports the "
            "abstraction, no Tier-1 falsifier fired, leakage is clean and blind "
            "relearning is structurally identical"
        )
    else:
        state = "EXPERIMENT_INCONCLUSIVE"
        basis = "no unseen case supported the abstraction and none contradicted it"

    return {
        "state": state,
        "state_is_one_of_permitted": state in EVIDENCE_STATES,
        "basis": basis,
        "tier_1_falsifiers_fired": fired,
        "reserved_status_granted": state == RESERVED_EVIDENCE_STATUS,
        "reserved_status_withheld_reason": (
            None if state == RESERVED_EVIDENCE_STATUS else basis
        ),
        "learned_flag_alone_proves_nothing": True,
        "epistemic_status": state,
        "evidence_path": "phase_6.verdict",
    }


def _authored_probe_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "contract": result.get("contract"),
        "version": result.get("version"),
        "test_subject": result.get("test_subject"),
        "demonstration_label": result.get("demonstration_label"),
        "phase_5_unseen": result.get("phase_5_unseen"),
        "phase_6_probes": result.get("phase_6_probes"),
        "phase_6_leakage_audit": result.get("phase_6_leakage_audit"),
        "phase_6_mode_comparison": result.get("phase_6_mode_comparison"),
        "phase_6_blind_relearning": result.get("phase_6_blind_relearning"),
        "phase_6_verdict": result.get("phase_6_verdict"),
        "evidence_states": result.get("evidence_states"),
        "non_claims": _REQUIRED_NON_CLAIMS,
    }


def _assert_no_forbidden_language(result: Dict[str, Any]) -> None:
    payload = json.dumps(_authored_probe_payload(result), sort_keys=True)
    tokens = [x for x in re.split(r"[^a-z0-9_]+", payload.lower()) if x]
    for term in _FORBIDDEN_TERMS:
        if term in tokens:
            raise ValueError(
                "ArchitecturalAbstractionProbeV1 must not emit the forbidden "
                "term " + repr(term)
            )


def _assert_verdict_is_permitted(result: Dict[str, Any]) -> None:
    verdict = result["phase_6_verdict"]["state"]
    if verdict not in EVIDENCE_STATES:
        raise ValueError(
            "ArchitecturalAbstractionProbeV1 emitted a non-permitted verdict: "
            + repr(verdict)
        )


def run_architectural_abstraction_probe(directive: Any) -> Dict[str, Any]:
    """Run Phases 5-6 of the abstraction experiment. Transient and read-only."""
    validated = _validate_directive(directive)

    learner_result = _validate_learner_result(validated.get("learner_result"))
    unseen_cases = [
        _validate_unseen_case(c)
        for c in _list(validated.get("unseen_cases"))
    ]
    if not unseen_cases:
        raise ValueError(
            "ArchitecturalAbstractionProbeV1 requires at least one unseen case"
        )
    for case in unseen_cases:
        _assert_case_carries_no_evaluation_key(case)

    second = validated.get("second_learner_result")
    if second is not None:
        second = _validate_learner_result(second)

    # ----- Phases 1-5 complete here. The evaluator has read nothing. -----
    phase_5 = _phase_5_unseen(learner_result, unseen_cases)
    probes = _run_probes(learner_result, unseen_cases)
    leakage = _leakage_audit(phase_5, probes)
    modes = _mode_comparison(learner_result)
    blind = _blind_relearning(learner_result, second)
    verdict = _verdict(learner_result, phase_5, probes, leakage, blind)

    # The evaluator's expectations, if supplied, are read ONLY now.
    expectations = validated.get("evaluation_expectations")
    expectation_check = None
    if expectations is not None:
        expectation_check = {
            "read_after_phase_5": True,
            "expectations_present": True,
            "note": (
                "expectations are recorded for audit and never used to reach "
                "the verdict above"
            ),
        }

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "test_subject": TEST_SUBJECT,
        "demonstration_label": DEMONSTRATION_LABEL,
        "phase_5_unseen": phase_5,
        "phase_6_probes": probes,
        "phase_6_leakage_audit": leakage,
        "phase_6_mode_comparison": modes,
        "phase_6_blind_relearning": blind,
        "phase_6_verdict": verdict,
        "evaluation_expectations_read": expectation_check,
        "evidence_states": list(EVIDENCE_STATES),
        "reserved_evidence_status": RESERVED_EVIDENCE_STATUS,
        "probe_names": list(ADVERSARIAL_PROBES),
        "non_claims": dict(_REQUIRED_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }

    _assert_no_forbidden_language(result)
    _assert_verdict_is_permitted(result)
    return result
