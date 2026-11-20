"""The V3 adversarial matrix: the full experiment, over the authored fixtures.

This suite runs the whole pipeline - learner in both modes, probe on both - over
the fixture corpora, and asserts the properties the experiment was built to
guarantee. It deliberately does NOT assert that the system succeeds: the
experiment is allowed to fail, and the honest failure is the most important
result here.

What it asserts
---------------
1. All eleven failure modes are emitted for both modes.
2. Mode P never exceeds its ceiling; Mode E is the only mode that may.
3. Mode E never receives or emits a predefined relation vocabulary.
4. The representation provenance ledger is present and complete.
5. The verdict never claims a level the measurements do not support.
6. PREDEFINED-REPRESENTATION-DEPENDENCE is reported as a valid result when
   Mode E cannot produce a why-grounded invariant without a predefined
   vocabulary.
7. Nothing in the run claims to be a learned model.
"""

import json
import os

import pytest

from core.knowledge.understanding_foundation.why_condition_abstraction import (
    v3_contracts as C,
)
from core.knowledge.understanding_foundation.why_condition_abstraction import (
    v3_harness_v1 as H,
)

FIXTURE_DIR = os.path.join("tests", "fixtures", "abstraction_v3")


def _load(name):
    with open(os.path.join(FIXTURE_DIR, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


def _teaching():
    return _load("teaching_corpus.json")


def _unseen():
    return _load("unseen_corpus.json")


def _full_directive():
    teaching = _teaching()
    unseen = _unseen()
    corpora = teaching["comparison_corpora"]
    probe_only = unseen["probe_only_cases"]
    return {
        "teaching_examples": teaching["teaching_examples"],
        "unseen_cases": unseen["unseen_cases"],
        "filler_substituted_examples": corpora["filler_substituted_examples"],
        "reformulated_examples": corpora["reformulated_examples"],
        "why_swapped_examples": corpora["why_swapped_examples"],
        "counterfactual_examples": corpora["counterfactual_examples"],
        "same_structure_pair": probe_only["same_structure_pair"],
        "different_form_case": probe_only["different_form_case"],
        "novel_combination_case": probe_only["novel_combination_case"],
    }


@pytest.fixture(scope="module")
def comparison():
    return H.run_v3_comparison(_full_directive())


# ---------------------------------------------------------------------------#
# 1. Both modes run, and both verdicts are honest
# ---------------------------------------------------------------------------#


def test_both_modes_run(comparison):
    assert set(comparison["results"].keys()) == set(C.MODES)


@pytest.mark.parametrize("mode", list(C.MODES))
def test_all_eleven_failure_modes_are_emitted_in_the_full_experiment(
    comparison, mode
):
    probe = comparison["results"][mode]["probe_result"]
    assert probe["phase_6_failure_mode_summary"]["all_eleven_emitted"] is True


@pytest.mark.parametrize("mode", list(C.MODES))
def test_every_verdict_is_a_permitted_level(comparison, mode):
    probe = comparison["results"][mode]["probe_result"]
    assert probe["verdict"]["level"] in C.EVIDENCE_LEVELS


def test_mode_p_verdict_stays_under_its_ceiling(comparison):
    probe = comparison["results"]["P"]["probe_result"]
    assert C.evidence_level_at_most(
        probe["verdict"]["level"], C.MODE_P_CEILING
    )
    assert probe["verdict"]["level"] not in (C.LEVEL_D, C.LEVEL_E)


def test_mode_p_uses_the_predefined_vocabulary_and_says_so(comparison):
    abstraction = comparison["results"]["P"]["learner_result"][
        "phase_4_abstraction"
    ]["candidate_abstraction"]
    assert abstraction["predefined_relation_vocabulary_used"] == list(
        C.MODE_P_RELATION_VOCABULARY
    )


def test_mode_e_uses_no_predefined_vocabulary(comparison):
    abstraction = comparison["results"]["E"]["learner_result"][
        "phase_4_abstraction"
    ]["candidate_abstraction"]
    assert abstraction["predefined_relation_vocabulary_used"] == []


# ---------------------------------------------------------------------------#
# 2. Mode E is genuinely denied the vocabulary
# ---------------------------------------------------------------------------#


def test_mode_e_learner_visible_input_contains_no_relation_word(comparison):
    result = comparison["results"]["E"]["learner_result"]
    blob = json.dumps({
        "phase_1": result["phase_1_given"],
        "phase_2": result["phase_2_conditions"],
        "phase_3": result["phase_3_coherence"],
        "phase_4": result["phase_4_abstraction"],
    }, sort_keys=True).lower()
    import re
    for term in C.MODE_E_FORBIDDEN_RELATION_TERMS:
        assert not re.search(
            r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])", blob
        ), term


def test_mode_e_reports_predfined_dependence_honestly(comparison):
    """The measured Mode-E outcome, whatever it is, must be a measured state."""
    probe = comparison["results"]["E"]["probe_result"]
    by_name = {m["failure_mode"]: m for m in probe["phase_6_failure_modes"]}
    state = by_name[C.FAILURE_PREDEFINED_REPRESENTATION_DEPENDENCE]["state"]
    assert state in ("MEASURED_PASS", "MEASURED_FAIL")


def test_if_mode_e_has_no_pattern_it_does_not_claim_a_high_level(comparison):
    """The central honesty guard.

    If Mode E reached no emergent pattern, it must not report Level D or E.
    """
    abstraction = comparison["results"]["E"]["learner_result"][
        "phase_4_abstraction"
    ]["candidate_abstraction"]
    probe = comparison["results"]["E"]["probe_result"]
    if abstraction["novel_relational_pattern"] is None:
        assert probe["verdict"]["level"] not in (C.LEVEL_D, C.LEVEL_E)


# ---------------------------------------------------------------------------#
# 3. The provenance ledger
# ---------------------------------------------------------------------------#


def test_the_provenance_ledger_is_present_in_every_result(comparison):
    for mode in C.MODES:
        learner = comparison["results"][mode]["learner_result"]
        probe = comparison["results"][mode]["probe_result"]
        assert learner["representation_provenance_ledger"]
        assert probe["representation_provenance_ledger"]
    assert comparison["representation_provenance_ledger"]


def test_every_provenance_entry_declares_an_origin():
    for element, record in C.REPRESENTATION_PROVENANCE_LEDGER.items():
        assert record["origin"] in C.REPRESENTATION_ORIGINS, element
        assert "introduced_by" in record, element
        assert "may_be_mode_e" in record, element


def test_predefined_relation_elements_are_marked_mode_p_only():
    ledger = C.REPRESENTATION_PROVENANCE_LEDGER
    for element in ("predefined_relation_kind", "predefined_scope_kind"):
        assert ledger[element]["may_be_mode_e"] is False
        assert ledger[element]["origin"] == C.ORIGIN_ENGINEERED


def test_the_generic_scaffold_is_engineered_but_the_slot_content_is_emergent():
    ledger = C.REPRESENTATION_PROVENANCE_LEDGER
    assert ledger["subject"]["origin"] == C.ORIGIN_ENGINEERED
    assert ledger["object"]["origin"] == C.ORIGIN_ENGINEERED
    # The slot SHAPE is engineered; the CONTENT is emergent.
    assert ledger["relation_slot"]["origin"] == C.ORIGIN_EMERGENT
    assert ledger["scope_slot"]["origin"] == C.ORIGIN_EMERGENT


def test_no_provenance_entry_is_left_unclassified():
    for element, record in C.REPRESENTATION_PROVENANCE_LEDGER.items():
        assert record["origin"] in (
            C.ORIGIN_ENGINEERED, C.ORIGIN_DERIVED, C.ORIGIN_EMERGENT,
        ), element


# ---------------------------------------------------------------------------#
# 4. The comparison is honest
# ---------------------------------------------------------------------------#


def test_the_comparison_states_whether_the_vocabulary_helped(comparison):
    outcome = comparison["comparison"]["outcome"]
    assert outcome in (
        "mode_e_exceeds_mode_p",
        "mode_p_exceeds_mode_e",
        "no_difference_observed",
    )
    assert comparison["comparison"]["interpretation"]


def test_a_mode_p_advantage_is_reported_as_representation_dependence(
    comparison
):
    if comparison["comparison"]["outcome"] == "mode_p_exceeds_mode_e":
        assert "PREDEFINED-REPRESENTATION-DEPENDENCE" in (
            comparison["comparison"]["interpretation"]
        )


# ---------------------------------------------------------------------------#
# 5. The MODE P baseline really works
# ---------------------------------------------------------------------------#


def test_mode_p_baseline_reaches_its_ceiling_on_a_favourable_corpus():
    """Mode P must be a real baseline, not a straw man.

    On a corpus whose WHY repeats the supplied vocabulary, Mode P must reach
    its Level-B ceiling. If it could not, the P/E comparison would be vacuous.
    Mode P is run on its own here: the favourable corpus NAMES a predefined
    relation word, so the Mode-E firewall would correctly refuse it.
    """
    teaching = _teaching()
    probe_corpus = teaching["mode_p_probe_corpus"]
    result = H.run_v3_comparison({
        "teaching_examples": probe_corpus["teaching_examples"],
        "unseen_cases": probe_corpus["unseen_cases"],
        "modes": ["P"],
    })
    abstraction = result["results"]["P"]["learner_result"][
        "phase_4_abstraction"
    ]["candidate_abstraction"]
    assert abstraction["reported_evidence_level"] == C.LEVEL_B
    assert abstraction["invariants"]
    assert abstraction["invariants"][0]["bound_to_why"] is True


def test_mode_e_refuses_a_corpus_that_names_a_predefined_relation_word():
    """The firewall's most important behaviour, asserted directly.

    Mode E must not be runnable on a corpus that already contains a predefined
    relation word: if it were, its result could not be evidence of emergence.
    """
    teaching = _teaching()
    probe_corpus = teaching["mode_p_probe_corpus"]
    with pytest.raises(ValueError):
        H.run_v3_comparison({
            "teaching_examples": probe_corpus["teaching_examples"],
            "unseen_cases": probe_corpus["unseen_cases"],
            "modes": ["E"],
        })


# ---------------------------------------------------------------------------#
# 6. Non-claims
# ---------------------------------------------------------------------------#


@pytest.mark.parametrize("mode", list(C.MODES))
def test_no_run_claims_to_be_a_learned_model(comparison, mode):
    learner = comparison["results"][mode]["learner_result"]
    abstraction = learner["phase_4_abstraction"]["candidate_abstraction"]
    assert abstraction["claimed_as_learning"] is False
    assert abstraction["claimed_as_conceptual_abstraction_evidence"] is False
    assert learner["non_claims"]["not_a_learned_model"] is True


@pytest.mark.parametrize("mode", list(C.MODES))
def test_the_fingerprint_is_never_presented_as_evidence(comparison, mode):
    abstraction = comparison["results"][mode]["learner_result"][
        "phase_4_abstraction"
    ]["candidate_abstraction"]
    assert abstraction["fingerprint_semantics"] == "representation_stability"
    assert abstraction["fingerprint_is_learning_evidence"] is False


def test_the_harness_emits_non_claims(comparison):
    assert comparison["non_claims"] == C.REQUIRED_NON_CLAIMS


def test_the_harness_is_transient_and_read_only(comparison):
    assert comparison["persistent"] is False
    assert comparison["read_only"] is True
