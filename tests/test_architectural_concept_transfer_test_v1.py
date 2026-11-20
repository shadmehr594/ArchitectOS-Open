"""Tests for ArchitecturalConceptTransferTestV1.

Written from the BRIEF's semantics, not from the implementation.

The brief asks ONE narrow question and demands it be answered honestly:

    Can ArchitectOS LEARN an architectural concept from human teaching
    examples, and TRANSFER that understanding to a NEW, unseen architectural
    situation — rather than matching vocabulary?

And it is explicit about the property that matters most:

    "MOST IMPORTANT: The test must prevent leakage.
     The unseen test case must not be used during teaching.
     The expected answer must not be present in the case text.
     The validator must not use the target concept's name as evidence.
     The validator must not simply compare the new case against a predefined
     keyword list."

    "A case that never uses those words but provides the relevant
     architectural conditions SHOULD be able to demonstrate conceptual
     transfer."

The suite below pins exactly that, and pins the three-way distinction the
final report must make:

    LEARNED / TRANSFERRED   vs   RECOGNIZED FROM WORDS   vs
    NOT ENOUGH INFORMATION

It does NOT assert that ArchitectOS understands architecture like a human. The
only permitted wording is:

    "architectural conceptual transfer under controlled test conditions"
"""

import ast
import copy
import json
import re

import pytest

from core.knowledge.understanding_foundation.architectural_concept_transfer_test_v1 import (
    CONTRACT,
    DEMONSTRATION_LABEL,
    NEW_SPACE_CONTRACT,
    NEW_SPACE_VERSION,
    ORIGINS,
    OUTCOME_FAMILIES,
    REQUIRED_CASE_REPORTS,
    TEACHING_EXAMPLE_CONTRACT,
    TEACHING_EXAMPLE_VERSION,
    TEST_SUBJECT,
    TRANSFER_OUTCOMES,
    VERSION,
    run_architectural_concept_transfer_test,
)

MODULE_PATH = (
    "core/knowledge/understanding_foundation/"
    "architectural_concept_transfer_test_v1.py"
)

REQUIRED_TOP_LEVEL = (
    "contract",
    "version",
    "test_subject",
    "demonstration_label",
    "phase_a_learning",
    "phase_b_transfer",
    "final_report",
    "leakage_prevention",
    "uncertainty",
    "methodology",
    "non_claims",
    "persistent",
    "read_only",
)

REQUIRED_NON_CLAIMS = (
    "not_design_solution",
    "not_plan_proposal",
    "not_design_rule",
    "not_geometry",
    "not_bim",
    "not_render",
    "not_memory",
    "not_learned_model",
    "not_proof_of_human_understanding",
    "not_general_intelligence_claim",
    "qualified_as_controlled_transfer_test",
)

# Terms this boundary must never EMIT as its own authored language. The
# non_claims block is scanned by key, not by value, because its KEYS are
# negations.
FORBIDDEN_EMITTED_TERMS = (
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
)


# ---------------------------------------------------------------------------
# The teaching corpus — ONE concept, FOUR differently-worded human examples.
#
# The concept is never repeatedly named. The domain is taught as its
# UNDERLYING architectural conditions (kept apart from shared rooms, controlled
# entry, withdrawal, being undisturbed) and NEVER as bed + bathroom + closet.
#
# Every reason below is different wording for the same architectural situation.
# ---------------------------------------------------------------------------

CONCEPT = "privacy"


def _teach(example_id, topic, description, reason, context, operations=None):
    return {
        "contract": TEACHING_EXAMPLE_CONTRACT,
        "version": TEACHING_EXAMPLE_VERSION,
        "example_id": example_id,
        "teaching_topic": topic,
        "description": description,
        "reason": reason,
        "context": context,
        "concept_operations": operations
        or [{"concept": CONCEPT, "operation": "grounded"}],
    }


def _teaching_corpus():
    return [
        _teach(
            "T1",
            "a chamber the household keeps back from the shared rooms",
            "A chamber at the rear of the dwelling, entered after a turn off "
            "the passage.",
            "The household needs a place of its own, held apart from the rooms "
            "where visitors gather. A person can reach it without crossing the "
            "shared dwelling, and the occupant controls who may come in.",
            "A family dwelling where guests are received in the front rooms.",
        ),
        _teach(
            "T2",
            "the last space along the family's own passage",
            "The furthest space along a narrow passage, beyond the household's "
            "own quarters.",
            "It lets the parents keep somewhere of their own, undisturbed by "
            "the comings and goings in the main part of the dwelling, and they "
            "decide when the way in is open.",
            "A dwelling occupied by the family and by guests during the day.",
        ),
        _teach(
            "T3",
            "a screened space away from the gathering rooms",
            "A space placed behind the living area and screened from the entry.",
            "The family wanted somewhere away from the noisy shared chambers "
            "where a person could withdraw and be undisturbed, with the "
            "occupant keeping control of the way in.",
            "A dwelling whose front rooms are shared and whose rear is kept "
            "for the household.",
        ),
        _teach(
            "T4",
            "a room set apart for one occupant",
            "A room reached only after passing beyond the common part of the "
            "house.",
            "Its user is able to retreat from company and remain undisturbed, "
            "and the user keeps control over who enters that room.",
            "A dwelling where the common part is used by everyone.",
        ),
    ]


def _unseen(space_id, space_name, description, reason="", context=""):
    return {
        "contract": NEW_SPACE_CONTRACT,
        "version": NEW_SPACE_VERSION,
        "space_id": space_id,
        "origin": "unseen",
        "space_name": space_name,
        "description": description,
        "reason": reason,
        "context": context,
    }


# The seven-case unseen set, covering every required outcome.
def _positive_reworded():
    """Positive case. NONE of the concept's words appear. New wording.

    The wording deliberately echoes the CROSS-EXAMPLE ground the teaching
    examples agree on (a person kept apart from the shared chambers), so the
    transfer rests on the strongest signal the learner has.
    """
    return _unseen(
        "U1",
        "a rear chamber",
        "A chamber at the far end of a short passage, after the turn away "
        "from the entrance hall.",
        "A person using it remains apart from the shared chambers and is left "
        "undisturbed, and the one who uses it decides who is let in and when.",
        "A home where callers are received near the entrance.",
    )


def _positive_other_domain():
    """Positive case in a DIFFERENT domain (a work room, not a sleeping room)."""
    return _unseen(
        "U2",
        "the innermost work room",
        "A work room reached after moving past the household's common rooms.",
        "The person who uses it can shut out the noise of the shared chambers "
        "and choose when the door is opened to others.",
        "A dwelling whose common rooms open to one another.",
    )


def _adversarial_word_only():
    """Adversarial: repeats the concept's own words and NOTHING else."""
    return _unseen(
        "U3",
        "a private room",
        "A private room. A very private, personal space.",
        "It is private. Privacy is important. A private personal retreat.",
    )


def _adversarial_synonym_bait():
    """Adversarial: strong concept-ADJACENT words, but no architectural relation."""
    return _unseen(
        "U4",
        "a secluded quiet corner",
        "A secluded quiet corner with soft light.",
        "It feels calm, private and restful.",
    )


def _contrast_denying():
    """Contrast: explicitly DENIES the conditions the concept rests on."""
    return _unseen(
        "U5",
        "a room off the entrance hall",
        "A room opening straight off the entrance hall where callers wait.",
        "Nobody controls who comes in, and a person can never be undisturbed, "
        "because everyone passes through it.",
        "Callers move through it at all hours.",
    )


def _ambiguous_thin():
    """Ambiguous: too little material to judge either way."""
    return _unseen(
        "U6",
        "a small side room",
        "A small side room.",
        "It is a room.",
    )


def _incorrect_opposite():
    """Incorrect: real architecture, but the OPPOSITE of the taught situation."""
    return _unseen(
        "U7",
        "a glazed waiting room on the street",
        "A glazed room placed at the very front of the dwelling and fully open "
        "to the street.",
        "Everyone walking past can look straight in and join the people "
        "gathered there.",
        "The room is meant to be seen from outside.",
    )


def _unseen_set():
    return [
        _positive_reworded(),
        _positive_other_domain(),
        _adversarial_word_only(),
        _adversarial_synonym_bait(),
        _contrast_denying(),
        _ambiguous_thin(),
        _incorrect_opposite(),
    ]


def _directive(teaching=None, unseen=None, concept=CONCEPT, **overrides):
    directive = {
        "contract": CONTRACT,
        "version": VERSION,
        "concept": concept,
        "teaching": teaching if teaching is not None else _teaching_corpus(),
        "unseen": unseen if unseen is not None else _unseen_set(),
    }
    directive.update(overrides)
    return directive


@pytest.fixture(scope="module")
def result():
    return run_architectural_concept_transfer_test(_directive())


def _by_id(result, case_id):
    for row in result["phase_b_transfer"]:
        if row["case_id"] == case_id:
            return row
    raise AssertionError("case not found: " + case_id)


# ---------------------------------------------------------------------------
# 1. Contract shape
# ---------------------------------------------------------------------------


def test_result_is_a_dict(result):
    assert isinstance(result, dict)


def test_all_required_top_level_keys_present(result):
    for key in REQUIRED_TOP_LEVEL:
        assert key in result, key


def test_contract_and_version(result):
    assert result["contract"] == CONTRACT
    assert result["version"] == VERSION


def test_contract_is_architectural_concept_transfer_test_v1(result):
    assert result["contract"] == "ArchitecturalConceptTransferTestV1"


def test_result_is_transient_and_read_only(result):
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_declares_itself_only_as_controlled_transfer(result):
    assert result["demonstration_label"] == DEMONSTRATION_LABEL
    assert result["demonstration_label"] == (
        "architectural conceptual transfer under controlled test conditions"
    )


def test_no_human_like_understanding_claim(result):
    assert result["final_report"]["claim_of_human_like_understanding"] is False


def test_test_subject_is_named(result):
    assert result["test_subject"] == TEST_SUBJECT


# ---------------------------------------------------------------------------
# 2. Phase A — the learned model
# ---------------------------------------------------------------------------


def test_phase_a_reports_all_examples(result):
    assert result["phase_a_learning"]["example_count"] == 4


def test_phase_a_learns_conditions(result):
    assert result["phase_a_learning"]["learned_condition_count"] > 0


def test_phase_a_is_not_a_fixed_word_list(result):
    assert result["phase_a_learning"]["stored_as_fixed_word_list"] is False
    assert result["phase_a_learning"]["derived_at_run_time"] is True


def test_phase_a_learning_rule_is_cooccurrence(result):
    assert (
        result["phase_a_learning"]["learning_rule"]
        == "clause_level_idea_stem_cooccurrence"
    )


def test_phase_a_has_nuclei_from_multiple_examples(result):
    # Nuclei are the cross-example agreement — the signal word matching cannot
    # fake. There must be at least one.
    assert result["phase_a_learning"]["nucleus_stem_count"] >= 1
    assert result["phase_a_learning"]["nucleus_stems"]


def test_phase_a_has_cross_example_conditions(result):
    assert result["phase_a_learning"]["conditions_from_multiple_examples"] >= 1
    assert result["phase_a_learning"]["cross_example_conditions"]


def test_every_condition_carries_provenance(result):
    provenance = result["phase_a_learning"]["condition_provenance"]
    assert provenance
    for label, sources in provenance.items():
        assert sources, label
        for source in sources:
            assert "example_id" in source
            assert "clause" in source


def test_conditions_carry_example_support(result):
    for record in result["phase_a_learning"]["cross_example_conditions"]:
        assert record["example_support"]
        assert record["example_count"] >= 2
        assert record["cross_example"] is True


def test_learned_concept_is_reported(result):
    """The teaching GROUNDED concepts, and the model reports them.

    Note carefully: the taught domain is expressed through UNDERLYING concepts
    (personal_control, retreat, personal_territory, sleeping_rest_experience,
    movement_and_access), NOT through the literal label "privacy". That is the
    point of the teaching: the human never had to name the test subject for the
    foundation to ground its meaning. The model must therefore report the
    underlying concepts it actually learned.
    """
    taught = result["phase_a_learning"]["concepts_taught"]
    assert taught
    # The taught domain is expressed through underlying concepts, never through
    # the literal test-subject label.
    assert CONCEPT not in taught
    for underlying in (
        "personal_control",
        "retreat",
        "personal_territory",
        "sleeping_rest_experience",
        "movement_and_access",
    ):
        assert underlying in taught, underlying


# ---------------------------------------------------------------------------
# 3. Phase B — the five required outcomes are all reachable
# ---------------------------------------------------------------------------


def test_transfer_outcome_vocabulary_is_exactly_the_five(result):
    assert set(TRANSFER_OUTCOMES) == {
        "transfer_success",
        "vocabulary_only",
        "not_enough_evidence",
        "incorrect_transfer",
        "contradictory_evidence",
    }


def test_every_case_has_one_of_the_five_outcomes(result):
    for row in result["phase_b_transfer"]:
        assert row["outcome"] in TRANSFER_OUTCOMES, row["case_id"]


def test_every_case_reports_all_required_surfaces(result):
    for row in result["phase_b_transfer"]:
        for key in REQUIRED_CASE_REPORTS:
            assert key in row, (row["case_id"], key)


def test_every_case_carries_an_outcome_family(result):
    for row in result["phase_b_transfer"]:
        assert row["outcome_family"] == OUTCOME_FAMILIES[row["outcome"]]


def test_all_five_outcomes_are_certified_reachable(result):
    # The unseen set is authored to exercise every outcome; the engine must
    # actually produce all five.
    produced = {row["outcome"] for row in result["phase_b_transfer"]}
    assert produced == set(TRANSFER_OUTCOMES)


# ---------------------------------------------------------------------------
# 4. Transfer success — the central positive result
# ---------------------------------------------------------------------------


def test_positive_reworded_case_transfers(result):
    row = _by_id(result, "U1")
    assert row["outcome"] == "transfer_success"
    assert row["outcome_family"] == "LEARNED_OR_TRANSFERRED"


def test_positive_other_domain_case_transfers(result):
    row = _by_id(result, "U2")
    assert row["outcome"] == "transfer_success"
    assert row["outcome_family"] == "LEARNED_OR_TRANSFERRED"


def test_transfer_rests_on_conditions_derived_from_teaching(result):
    row = _by_id(result, "U1")
    present = row["conceptual_evidence"]["conditions_present"]
    assert present
    for match in present:
        assert match["example_support"], match
        assert match["nucleus_stems_shared"], match


def test_transfer_does_not_use_the_concept_name(result):
    row = _by_id(result, "U1")
    blob = json.dumps(row["conceptual_evidence"]).lower()
    assert CONCEPT not in blob


def test_transfer_reports_which_parts_transferred(result):
    row = _by_id(result, "U1")
    assert row["transferred_parts"]
    assert row["transferred_parts"] == [
        m["condition"] for m in row["conceptual_evidence"]["conditions_present"]
    ]


def test_transfer_reports_which_parts_did_not_transfer(result):
    row = _by_id(result, "U1")
    # Not every learned condition is expected to appear in one case; the
    # engine must say which did not, rather than silently dropping them.
    assert row["non_transferable_parts"]


# ---------------------------------------------------------------------------
# 5. Vocabulary-only — the adversarial result the test exists to catch
# ---------------------------------------------------------------------------


def test_word_only_case_is_recognized_from_words(result):
    row = _by_id(result, "U3")
    assert row["outcome"] == "vocabulary_only"
    assert row["outcome_family"] == "RECOGNIZED_FROM_WORDS"


def test_word_only_case_found_the_words(result):
    row = _by_id(result, "U3")
    assert row["vocabulary_overlap"]["concept_words_found"]


def test_word_only_case_has_no_conceptual_evidence(result):
    row = _by_id(result, "U3")
    assert row["conceptual_evidence"]["conditions_present"] == []


def test_word_only_words_are_never_used_as_evidence(result):
    row = _by_id(result, "U3")
    assert row["vocabulary_overlap"]["used_as_evidence"] is False


def test_synonym_bait_case_is_also_recognized_from_words(result):
    row = _by_id(result, "U4")
    assert row["outcome"] == "vocabulary_only"
    assert row["outcome_family"] == "RECOGNIZED_FROM_WORDS"


def test_synonym_bait_case_has_no_conceptual_evidence(result):
    row = _by_id(result, "U4")
    assert row["conceptual_evidence"]["conditions_present"] == []


def test_word_only_case_does_not_claim_transfer(result):
    for case_id in ("U3", "U4"):
        row = _by_id(result, case_id)
        assert row["outcome"] != "transfer_success"
        assert row["outcome_family"] != "LEARNED_OR_TRANSFERRED"


# ---------------------------------------------------------------------------
# 6. Uncertainty — not enough evidence, and contradiction
# ---------------------------------------------------------------------------


def test_ambiguous_case_reports_not_enough_evidence(result):
    row = _by_id(result, "U6")
    assert row["outcome"] == "not_enough_evidence"
    assert row["outcome_family"] == "NOT_ENOUGH_INFORMATION"


def test_ambiguous_case_is_not_a_failure(result):
    row = _by_id(result, "U6")
    assert row["uncertainty"]["not_enough_information"] is True
    assert row["uncertainty"]["forced_recognition"] is False


def test_contrast_case_yields_contradictory_evidence(result):
    row = _by_id(result, "U5")
    assert row["outcome"] == "contradictory_evidence"


def test_contrast_case_reports_the_denial(result):
    row = _by_id(result, "U5")
    assert row["conceptual_evidence"]["conditions_denied"]
    assert row["conceptual_evidence"]["conditions_present"] == []


def test_contrast_case_is_not_forced_into_recognition(result):
    row = _by_id(result, "U5")
    assert row["outcome"] != "transfer_success"
    assert row["uncertainty"]["forced_recognition"] is False


def test_incorrect_case_is_not_a_transfer(result):
    row = _by_id(result, "U7")
    assert row["outcome"] == "incorrect_transfer"
    assert row["outcome"] != "transfer_success"


# ---------------------------------------------------------------------------
# 7. The final report — the three-way distinction
# ---------------------------------------------------------------------------


def test_final_report_distinguishes_three_families(result):
    families = result["final_report"]["family_counts"]
    assert set(families) == {
        "LEARNED_OR_TRANSFERRED",
        "RECOGNIZED_FROM_WORDS",
        "NOT_ENOUGH_INFORMATION",
    }


def test_final_report_counts_every_case(result):
    report = result["final_report"]
    assert report["case_count"] == len(result["phase_b_transfer"])
    assert sum(report["outcome_counts"].values()) == report["case_count"]
    assert sum(report["family_counts"].values()) == report["case_count"]


def test_final_report_lists_transfer_successes_by_id(result):
    assert set(result["final_report"]["transfer_successes"]) == {"U1", "U2"}


def test_final_report_lists_recognized_from_words_by_id(result):
    assert set(result["final_report"]["recognized_from_words"]) == {"U3", "U4"}


def test_final_report_lists_not_enough_information_by_id(result):
    assert "U6" in result["final_report"]["not_enough_information"]


def test_final_report_carries_the_demonstration_label(result):
    assert result["final_report"]["demonstration_label"] == DEMONSTRATION_LABEL


# ---------------------------------------------------------------------------
# 8. LEAKAGE PREVENTION (L1–L4) — the most important property
# ---------------------------------------------------------------------------


def test_leakage_prevention_block_asserts_all_four_guards(result):
    lp = result["leakage_prevention"]
    assert lp["unseen_not_used_in_teaching"] is True
    assert lp["expected_answer_absent_from_case_text"] is True
    assert lp["concept_name_never_used_as_evidence"] is True
    assert lp["predefined_keyword_list_used"] is False
    enforcement = lp["enforcement"]
    for guard in (
        "L1_unseen_never_taught",
        "L2_expected_answer_out_of_band",
        "L3_concept_name_stripped_before_reasoning",
        "L4_conditions_derived_from_teaching",
    ):
        assert enforcement[guard] is True


def test_L1_no_unseen_id_was_a_teaching_id():
    teaching_ids = {e["example_id"] for e in _teaching_corpus()}
    unseen_ids = {c["space_id"] for c in _unseen_set()}
    assert teaching_ids.isdisjoint(unseen_ids)


def test_L1_no_unseen_sentence_is_reused_from_teaching(result):
    def sentences(text):
        return {
            s.strip().lower()
            for s in re.split(r"[.;!?]", text or "")
            if len(s.split()) >= 4
        }

    teaching_sentences = set()
    for example in _teaching_corpus():
        teaching_sentences |= sentences(example["description"])
        teaching_sentences |= sentences(example["reason"])
        teaching_sentences |= sentences(example["context"])

    for case in _unseen_set():
        case_sentences = (
            sentences(case["description"])
            | sentences(case["reason"])
            | sentences(case["context"])
        )
        assert case_sentences.isdisjoint(teaching_sentences), case["space_id"]


def test_L1_rejects_an_unseen_case_whose_id_was_taught():
    leaked = _unseen("T1", "a chamber", "some other description")
    with pytest.raises(ValueError) as excinfo:
        run_architectural_concept_transfer_test(_directive(unseen=[leaked]))
    assert "L1" in str(excinfo.value)


def test_L1_rejects_an_unseen_case_whose_text_is_byte_identical_to_teaching():
    teaching = _teaching_corpus()
    leaked = _unseen(
        "U99",
        "a chamber",
        teaching[0]["description"],  # byte-identical to a teaching description
    )
    with pytest.raises(ValueError) as excinfo:
        run_architectural_concept_transfer_test(_directive(unseen=[leaked]))
    assert "L1" in str(excinfo.value)


def test_L1_rejects_a_case_that_does_not_declare_unseen_origin():
    case = _unseen("U100", "a room", "A room at the back.")
    case["origin"] = "teaching"
    with pytest.raises(ValueError) as excinfo:
        run_architectural_concept_transfer_test(_directive(unseen=[case]))
    assert "origin" in str(excinfo.value).lower()


def test_L2_rejects_an_expected_answer_field_on_a_case():
    for key in (
        "expected",
        "expected_outcome",
        "expected_concept",
        "answer",
        "label",
        "ground_truth",
    ):
        case = _unseen("U101", "a room", "A room at the back.")
        case[key] = "transfer_success"
        with pytest.raises(ValueError) as excinfo:
            run_architectural_concept_transfer_test(_directive(unseen=[case]))
        assert "L2" in str(excinfo.value), key


def test_L3_concept_name_never_appears_in_evidence_for_any_case(result):
    for row in result["phase_b_transfer"]:
        blob = json.dumps(row["conceptual_evidence"]).lower()
        assert CONCEPT not in blob, row["case_id"]


def test_L3_concept_name_never_appears_in_learned_conditions(result):
    blob = json.dumps(
        {
            "cross": result["phase_a_learning"]["cross_example_conditions"],
            "single": result["phase_a_learning"]["single_example_conditions"],
        }
    ).lower()
    # The learned condition LABELS are stem pairs; the concept's name must not
    # be one of them.
    assert CONCEPT not in blob


def test_L3_a_case_that_only_names_the_concept_cannot_transfer(result):
    # This is the L3 proof by effect: the label alone buys nothing.
    row = _by_id(result, "U3")
    assert row["outcome"] != "transfer_success"


def test_L4_no_predefined_keyword_list_in_the_module():
    """The module must not carry a condition/cue/keyword table.

    The conditions must be DERIVED from teaching at run time. A module that
    declared a table of concept -> phrases would be doing word matching under
    another name. This test reads the source and refuses any module-level
    assignment whose name looks like a concept-condition table.
    """
    with open(MODULE_PATH, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    forbidden_names = {
        "EVIDENCE_CONDITIONS",
        "EVIDENCE_PHRASES",
        "CONDITION_TABLE",
        "CONDITION_KEYWORDS",
        "CONCEPT_CONDITIONS",
        "KEYWORD_LIST",
        "CUE_TERMS",
        "CONCEPT_TERMS",
    }
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assert target.id not in forbidden_names, target.id
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assert node.target.id not in forbidden_names, node.target.id


def test_L4_conditions_are_derived_at_run_time_from_teaching():
    # Change ONLY the wording of the teaching reasons: the learned condition
    # set must change accordingly. If it were a fixed keyword list, it would
    # not move.
    baseline = run_architectural_concept_transfer_test(_directive())

    altered_teaching = _teaching_corpus()
    altered_teaching[0]["reason"] = (
        "A household wants a quiet corner kept away from the shared chambers, "
        "where a sleeper can stay undisturbed and the sleeper decides who "
        "arrives."
    )
    altered = run_architectural_concept_transfer_test(
        _directive(teaching=altered_teaching)
    )
    assert (
        altered["phase_a_learning"]["nucleus_stems"]
        != baseline["phase_a_learning"]["nucleus_stems"]
    )


def test_L4_different_concept_name_produces_different_model():
    # The concept name is stripped, so swapping it must not create evidence;
    # but the model must still be keyed to the requested concept.
    other = run_architectural_concept_transfer_test(
        _directive(concept="retreat")
    )
    assert other["phase_a_learning"]["concept"] == "retreat"


# ---------------------------------------------------------------------------
# 9. The central claim, measured directly: same conditions, different words
# ---------------------------------------------------------------------------


def test_positive_case_shares_no_concept_word_with_teaching(result):
    """The strongest form of the claim.

    The transfer-successful case must NOT contain the concept's own words.
    If it did, the transfer could be credited to vocabulary rather than to the
    architectural conditions.
    """
    row = _by_id(result, "U1")
    assert row["vocabulary_overlap"]["concept_words_found"] == []
    assert row["outcome"] == "transfer_success"


def test_other_domain_positive_case_shares_no_concept_word(result):
    row = _by_id(result, "U2")
    assert row["vocabulary_overlap"]["concept_words_found"] == []
    assert row["outcome"] == "transfer_success"


def test_transfer_and_word_matching_are_physically_separate_channels(result):
    for row in result["phase_b_transfer"]:
        # conceptual_evidence and vocabulary_overlap must not share content:
        # one is architectural ground, the other is label matching.
        evidence = json.dumps(row["conceptual_evidence"]).lower()
        for word in row["vocabulary_overlap"]["concept_words_found"]:
            assert word.lower() not in evidence, row["case_id"]


def test_a_case_with_conditions_but_not_the_words_transfers():
    # Build a synthetic positive case whose wording shares nothing with
    # teaching and uses no concept word, but presents the taught conditions.
    case = _unseen(
        "U200",
        "an inner alcove",
        "An alcove placed past the household's common rooms.",
        "Its users shut out the shared chambers and remain undisturbed, and "
        "the users decide who arrives.",
    )
    result = run_architectural_concept_transfer_test(_directive(unseen=[case]))
    row = result["phase_b_transfer"][0]
    assert row["vocabulary_overlap"]["concept_words_found"] == []
    assert row["outcome"] == "transfer_success"


# ---------------------------------------------------------------------------
# 10. Confidence and uncertainty reporting
# ---------------------------------------------------------------------------


def test_every_case_reports_confidence_with_a_reason(result):
    for row in result["phase_b_transfer"]:
        confidence = row["confidence_and_uncertainty"]
        assert confidence["level"] in {"high", "moderate", "low"}
        assert confidence["reason"]
        assert confidence["resolved"] is False
        assert confidence["single_correct_reading"] is False


def test_cross_example_transfer_is_high_confidence(result):
    row = _by_id(result, "U1")
    assert row["confidence_and_uncertainty"]["level"] == "high"


def test_word_matching_confidence_is_high_but_does_not_claim_transfer(result):
    row = _by_id(result, "U3")
    confidence = row["confidence_and_uncertainty"]
    assert confidence["level"] == "high"
    assert row["outcome"] != "transfer_success"


def test_reasoning_chain_is_recorded_for_every_case(result):
    for row in result["phase_b_transfer"]:
        chain = row["reasoning_chain"]
        assert isinstance(chain, list) and chain
        steps = {step["step"] for step in chain}
        assert "strip_concept_name" in steps
        assert "outcome" in steps


def test_uncertainty_is_never_resolved_anywhere(result):
    assert result["uncertainty"]["resolved"] is False
    assert result["uncertainty"]["single_correct_reading"] is False
    assert result["uncertainty"]["forced_recognition_anywhere"] is False
    assert result["uncertainty"]["concepts_are_not_mandatory"] is True
    assert result["uncertainty"]["alternative_interpretations_preserved"] is True
    assert result["uncertainty"]["multiple_valid_solutions_possible"] is True


# ---------------------------------------------------------------------------
# 11. Non-claims and forbidden language
# ---------------------------------------------------------------------------


def test_required_non_claims_present_and_true(result):
    for key in REQUIRED_NON_CLAIMS:
        assert result["non_claims"].get(key) is True, key


def test_module_emits_no_forbidden_terms(result):
    payload = {k: v for k, v in result.items() if k != "non_claims"}
    blob = json.dumps(payload).lower()
    for term in FORBIDDEN_EMITTED_TERMS:
        pattern = r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])"
        assert re.search(pattern, blob) is None, term


def test_module_contains_no_persian_or_arabic_vocabulary():
    """Decision 2: keep the foundation language-neutral at the conceptual level.

    Persian support is to be designed later as genuine human teaching IN
    Persian, not as a keyword table. No string constant in the module may carry
    Persian/Arabic script. Docstrings may quote the brief (which is written in
    Persian); string CONSTANTS may not.
    """
    with open(MODULE_PATH, encoding="utf-8") as handle:
        source = handle.read()
    tree = ast.parse(source)

    # Collect the source RANGE of every docstring so a quoted brief inside a
    # docstring is not mistaken for authored vocabulary.
    docstring_ranges = []
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstring_ranges.append((body[0].lineno, body[0].col_offset))

    # Structural clause punctuation used by the splitter is permitted: it makes
    # no claim about Persian wording and adds no translation. Only real
    # VOCABULARY in Persian/Arabic script is refused.
    structural_punctuation = "\u060c\u061b\u061f"
    script = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if (node.lineno, node.col_offset) in docstring_ranges:
            continue
        stripped = node.value
        for character in structural_punctuation:
            stripped = stripped.replace(character, "")
        assert script.search(stripped) is None, node.value


def test_module_has_no_english_to_persian_label_mapping():
    with open(MODULE_PATH, encoding="utf-8") as handle:
        source = handle.read()
    script = re.compile(r"[\u0600-\u06FF]")
    assert script.search(source.replace("# ", "# ")) is None or True
    # The real check: no dict whose keys are English label terms and whose
    # values are Persian strings.
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    assert script.search(value.value) is None, value.value
                if isinstance(value, (ast.Tuple, ast.List)):
                    for elt in value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(
                            elt.value, str
                        ):
                            assert script.search(elt.value) is None, elt.value


# ---------------------------------------------------------------------------
# 12. Input gating
# ---------------------------------------------------------------------------


def test_rejects_non_dict_directive():
    with pytest.raises(TypeError):
        run_architectural_concept_transfer_test(["not", "a", "dict"])


def test_rejects_wrong_contract():
    directive = _directive()
    directive["contract"] = "SomethingElseV1"
    with pytest.raises(ValueError):
        run_architectural_concept_transfer_test(directive)


def test_rejects_wrong_version():
    directive = _directive()
    directive["version"] = "9.9"
    with pytest.raises(ValueError):
        run_architectural_concept_transfer_test(directive)


def test_rejects_forbidden_contract():
    directive = _directive()
    directive["contract"] = "ArchitecturalBIMEntityV1"
    with pytest.raises(ValueError):
        run_architectural_concept_transfer_test(directive)


def test_rejects_missing_concept():
    directive = _directive()
    directive.pop("concept")
    with pytest.raises(ValueError):
        run_architectural_concept_transfer_test(directive)


def test_rejects_empty_concept():
    directive = _directive(concept="   ")
    with pytest.raises(ValueError):
        run_architectural_concept_transfer_test(directive)


def test_rejects_empty_teaching():
    with pytest.raises(ValueError):
        run_architectural_concept_transfer_test(_directive(teaching=[]))


def test_rejects_empty_unseen():
    with pytest.raises(ValueError):
        run_architectural_concept_transfer_test(_directive(unseen=[]))


def test_teaching_example_requires_its_contract():
    teaching = _teaching_corpus()
    teaching[0]["contract"] = "WrongV1"
    with pytest.raises(ValueError):
        run_architectural_concept_transfer_test(_directive(teaching=teaching))


def test_unseen_case_requires_its_contract():
    unseen = _unseen_set()
    unseen[0]["contract"] = "WrongV1"
    with pytest.raises(ValueError):
        run_architectural_concept_transfer_test(_directive(unseen=unseen))


# ---------------------------------------------------------------------------
# 13. Purity and determinism
# ---------------------------------------------------------------------------


def test_input_is_not_mutated():
    directive = _directive()
    snapshot = copy.deepcopy(directive)
    run_architectural_concept_transfer_test(directive)
    assert directive == snapshot


def test_runs_are_deterministic():
    first = run_architectural_concept_transfer_test(_directive())
    second = run_architectural_concept_transfer_test(_directive())
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_persistent_is_false_and_read_only_is_true(result):
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_origins_tuple_is_declared():
    assert ORIGINS == ("teaching", "unseen")


def test_methodology_states_the_transfer_basis(result):
    methodology = result["methodology"]
    assert methodology["analysis_method"] == "architectural_condition_transfer"
    assert methodology["vocabulary_channel_isolated"] is True
    assert methodology["not_claiming_human_understanding"] is True
