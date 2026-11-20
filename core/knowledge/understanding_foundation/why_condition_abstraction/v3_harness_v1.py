"""V3 harness - one deterministic P/E comparison run.

A thin runner. It does NOT add any semantics, any vocabulary, or any decision
rule: it calls the learner in both modes, calls the probe on each result, and
returns the pair so the two claims can be compared side by side.

The harness exists so that the comparison is run the SAME way every time, and so
that the "Mode P vs Mode E" question has one place where it is answered.

Transient, read-only, non-learning.
"""

from copy import deepcopy
from typing import Any, Dict, List

from . import v3_contracts as C
from . import v3_abstraction_learner_v1 as LEARNER
from . import v3_abstraction_probe_v1 as PROBE

CONTRACT = "V3AbstractionHarnessV1"
VERSION = "1.0"


def _learner_directive(
    mode: str, teaching_examples: List[Dict[str, Any]]
) -> Dict[str, Any]:
    return {
        "contract": LEARNER.DIRECTIVE_CONTRACT,
        "version": LEARNER.DIRECTIVE_VERSION,
        "mode": mode,
        "teaching_examples": teaching_examples,
    }


def _probe_directive(
    learner_result: Dict[str, Any],
    probe_inputs: Dict[str, Any],
) -> Dict[str, Any]:
    directive = {
        "contract": PROBE.DIRECTIVE_CONTRACT,
        "version": PROBE.DIRECTIVE_VERSION,
        "learner_result": learner_result,
    }
    directive.update(probe_inputs or {})
    return directive


def run_v3_comparison(directive: Any) -> Dict[str, Any]:
    """Run Mode P and Mode E over the same teaching corpus, and probe both.

    The directive carries:
      * ``teaching_examples`` - the LEARNER-visible corpus
      * ``unseen_cases``      - the unseen cases the probe reasons over
      * optional comparison corpora, all LEARNER-visible:
          ``filler_substituted_examples``, ``reformulated_examples``,
          ``why_swapped_examples``, ``counterfactual_examples``
      * optional probe-only cases: ``same_structure_pair``,
        ``different_form_case``, ``novel_combination_case``
      * optional ``evaluation_expectations`` - read only after the verdict
    """
    if not isinstance(directive, dict):
        raise TypeError(
            "V3AbstractionHarnessV1 requires a directive dict, got "
            + type(directive).__name__
        )
    teaching = directive.get("teaching_examples") or []
    if not teaching:
        raise ValueError(
            "V3AbstractionHarnessV1 requires teaching_examples"
        )
    unseen = directive.get("unseen_cases") or []
    if not unseen:
        raise ValueError("V3AbstractionHarnessV1 requires unseen_cases")

    learner_visible_keys = {
        "filler_substituted_examples": "filler_substituted_learner_result",
        "reformulated_examples": "reformulated_learner_result",
        "why_swapped_examples": "why_swapped_learner_result",
        "counterfactual_examples": "counterfactual_learner_result",
    }

    # The mode filter exists so a corpus that legitimately names a predefined
    # relation word can still be run through Mode P alone. It is not a way to
    # skip a mode in a comparison: when only one mode is requested, no
    # comparison is reported.
    requested_modes = directive.get("modes") or list(C.MODES)
    for requested in requested_modes:
        if requested not in C.MODES:
            raise ValueError(
                "V3AbstractionHarnessV1: unknown mode " + repr(requested)
            )

    results: Dict[str, Any] = {}
    for mode in requested_modes:
        learner_result = LEARNER.run_v3_abstraction_learner(
            _learner_directive(mode, teaching)
        )

        probe_inputs: Dict[str, Any] = {"unseen_cases": unseen}
        for example_key, result_key in learner_visible_keys.items():
            corpus = directive.get(example_key)
            if corpus:
                probe_inputs[result_key] = LEARNER.run_v3_abstraction_learner(
                    _learner_directive(mode, corpus)
                )
        for probe_key in ("same_structure_pair", "different_form_case",
                          "novel_combination_case"):
            if directive.get(probe_key) is not None:
                probe_inputs[probe_key] = directive[probe_key]
        if directive.get("evaluation_expectations") is not None:
            probe_inputs["evaluation_expectations"] = directive[
                "evaluation_expectations"
            ]

        probe_result = PROBE.run_v3_abstraction_probe(
            _probe_directive(learner_result, probe_inputs)
        )
        results[mode] = {
            "mode": mode,
            "learner_result": learner_result,
            "probe_result": probe_result,
            "verdict_level": probe_result["verdict"]["level"],
            "fatal_failure_modes": probe_result["verdict"][
                "fatal_failure_modes"
            ],
            "novel_relational_pattern_present": probe_result["verdict"][
                "novel_relational_pattern_present"
            ],
        }

    comparison = _compare(results)

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "test_subject": C.TEST_SUBJECT,
        "modes": list(requested_modes),
        "results": results,
        "comparison": comparison,
        "evidence_level_ranking": deepcopy(C.EVIDENCE_LEVEL_RANK),
        "representation_provenance_ledger": deepcopy(
            C.REPRESENTATION_PROVENANCE_LEDGER
        ),
        "non_claims": dict(C.REQUIRED_NON_CLAIMS),
        "persistent": False,
        "read_only": True,
    }


def _compare(results: Dict[str, Any]) -> Dict[str, Any]:
    """Compare the two modes honestly, including when they agree.

    When only one mode was run there is nothing to compare, and the comparison
    says exactly that rather than inventing a second result.
    """
    if C.MODE_P not in results or C.MODE_E not in results:
        present = sorted(results)
        return {
            "outcome": "single_mode_run",
            "modes_run": present,
            "interpretation": (
                "only " + ", ".join(present) + " was run, so there is nothing "
                "to compare"
            ),
        }

    p = results[C.MODE_P]
    e = results[C.MODE_E]
    p_rank = C.EVIDENCE_LEVEL_RANK[p["verdict_level"]]
    e_rank = C.EVIDENCE_LEVEL_RANK[e["verdict_level"]]

    if e_rank > p_rank:
        outcome = "mode_e_exceeds_mode_p"
    elif p_rank > e_rank:
        outcome = "mode_p_exceeds_mode_e"
    else:
        outcome = "no_difference_observed"

    return {
        "mode_p_level": p["verdict_level"],
        "mode_e_level": e["verdict_level"],
        "outcome": outcome,
        "mode_p_used_predefined_vocabulary": True,
        "mode_e_used_predefined_vocabulary": False,
        "mode_p_novel_pattern": p["novel_relational_pattern_present"],
        "mode_e_novel_pattern": e["novel_relational_pattern_present"],
        "interpretation": (
            "Mode E reached a higher evidence level without any predefined "
            "relation vocabulary, so the abstraction did not depend on the "
            "representation this package supplied, and the experiment is "
            "ALLOWED to be reported as an emergent-result run"
            if outcome == "mode_e_exceeds_mode_p" else
            "Mode P and Mode E reached the same level, so the predefined "
            "vocabulary made no measured difference on this corpus"
            if outcome == "no_difference_observed" else
            "Mode P reached a higher level than Mode E, which means the "
            "predefined relation vocabulary was doing the work: this is a "
            "measured PREDEFINED-REPRESENTATION-DEPENDENCE result, and it is "
            "the honest scientific outcome for this corpus"
        ),
    }


__all__ = ["CONTRACT", "VERSION", "run_v3_comparison"]
