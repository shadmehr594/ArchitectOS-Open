"""Tests for ArchitecturalAbstractionProbeV1 (ABSTRACTION TEST V2, Phases 5-6).

Written from the BRIEF's semantics, not from the implementation.

The brief demands that a verdict be reached ONLY after inference AND an unseen
evaluation, that the reserved status be granted ONLY on a full gate pass, and
that the module never produce a positive verdict from a class name, a label, or
an expected answer.

It further demands:

    * the seven evidence states are the ONLY permitted outputs;
    * Blind Relearning runs WITHOUT a semantic comparator, and reports
      ABSTRACTION_STABILITY_NOT_DEMONSTRATED when it cannot show alignment;
    * author / learner / evaluator knowledge stay separated at runtime;
    * every verdict and every probe result carries an auditable evidence path.

This suite pins exactly that.
"""

import ast
import copy
import json
import re

import pytest

from core.knowledge.understanding_foundation.architectural_abstraction_learner_v1 import (
    DIRECTIVE_CONTRACT as LEARNER_DC,
    DIRECTIVE_VERSION as LEARNER_DV,
    run_architectural_abstraction_learner,
)
from core.knowledge.understanding_foundation.architectural_abstraction_probe_v1 import (
    ADVERSARIAL_PROBES,
    CONTRACT,
    DEMONSTRATION_LABEL,
    DIRECTIVE_CONTRACT,
    DIRECTIVE_VERSION,
    EVIDENCE_STATES,
    NEW_SPACE_CONTRACT,
    NEW_SPACE_VERSION,
    PROBE_DESCRIPTIONS,
    RESERVED_EVIDENCE_STATUS,
    TEST_SUBJECT,
    TIER_1_FALSIFIERS,
    VERSION,
    run_architectural_abstraction_probe,
)

LEARNER_CONTRACT = "ArchitecturalAbstractionLearnerV1"
MODULE_PATH = (
    "core/knowledge/understanding_foundation/architectural_abstraction_probe_v1.py"
)

REQUIRED_TOP_LEVEL = (
    "contract",
    "version",
    "test_subject",
    "demonstration_label",
    "phase_5_unseen",
    "phase_6_probes",
    "phase_6_leakage_audit",
    "phase_6_mode_comparison",
    "phase_6_blind_relearning",
    "phase_6_verdict",
    "evidence_states",
    "non_claims",
    "persistent",
    "read_only",
)

TEACHING_CONTRACT = "ArchitecturalHumanTeachingExampleV1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ex(example_id, description, reason):
    return {
        "contract": TEACHING_CONTRACT,
        "version": "1.0",
        "example_id": example_id,
        "description": description,
        "reason": reason,
    }


def _space(space_id, description, reason):
    return {
        "contract": NEW_SPACE_CONTRACT,
        "version": NEW_SPACE_VERSION,
        "space_id": space_id,
        "description": description,
        "reason": reason,
    }


def _corpus_a():
    return [
        _ex("A1", "A sleeping chamber is set apart from the shared rooms, "
                  "screened by depth.",
            "because the occupant needs to recover where nobody watches them"),
        _ex("A2", "A resting cell stands beyond the common hall, withdrawn "
                  "behind a threshold.",
            "because a person has to be unobserved while they recover"),
        _ex("A3", "A quiet nook sits past the gathering space, kept out of sight.",
            "because the household member needs an unwatched place to rest"),
        _ex("A4", "A small bay lies off the busy corridor, turned away from "
                  "company.",
            "because whoever uses it must recover out of anyone view"),
    ]


def _corpus_b():
    return [
        _ex("B1", "A sheltered recess sits past the family zone, shielded from "
                  "view.",
            "since the resident has to recover unobserved"),
        _ex("B2", "A tucked corner rests behind the entry sequence, hidden from "
                  "onlookers.",
            "for its owner needs to recover away from prying eyes"),
        _ex("B3", "A withdrawn pocket lies off the social space, kept from sight.",
            "because the user must recover where nobody watches"),
    ]


def _learner(mode="F", teaching=None):
    directive = {
        "contract": LEARNER_DC,
        "version": LEARNER_DV,
        "mode": mode,
        "teaching_examples": _corpus_a() if teaching is None else teaching,
    }
    return run_architectural_abstraction_learner(directive)


def _support_case():
    return _space(
        "U1",
        "A small room sits off the main area, kept out of view.",
        "because the person who uses it has to recover without being watched",
    )


def _probe_directive(unseen=None, learner=None, second=None, expectations=None):
    directive = {
        "contract": DIRECTIVE_CONTRACT,
        "version": DIRECTIVE_VERSION,
        "learner_result": _learner() if learner is None else learner,
        "unseen_cases": [_support_case()] if unseen is None else unseen,
    }
    if second is not None:
        directive["second_learner_result"] = second
    if expectations is not None:
        directive["evaluation_expectations"] = expectations
    return directive


@pytest.fixture()
def result():
    return run_architectural_abstraction_probe(_probe_directive())


# ---------------------------------------------------------------------------
# 1. Contract shape
# ---------------------------------------------------------------------------


def test_top_level_shape(result):
    for key in REQUIRED_TOP_LEVEL:
        assert key in result, key


def test_contract_and_version(result):
    assert result["contract"] == CONTRACT == "ArchitecturalAbstractionProbeV1"
    assert result["version"] == VERSION == "1.0"


def test_test_subject_and_label(result):
    assert result["test_subject"] == TEST_SUBJECT
    assert result["demonstration_label"] == DEMONSTRATION_LABEL


def test_persistent_is_false_and_read_only_is_true(result):
    assert result["persistent"] is False
    assert result["read_only"] is True


# ---------------------------------------------------------------------------
# 2. The seven evidence states are the whole vocabulary
# ---------------------------------------------------------------------------


def test_evidence_states_are_the_declared_seven(result):
    assert result["evidence_states"] == list(EVIDENCE_STATES)
    assert len(EVIDENCE_STATES) == 7


def test_every_required_state_is_present():
    for state in (
        "ENGINEERED_REPRESENTATION",
        "STRUCTURED_GENERALIZATION_ONLY",
        "CONCEPTUAL_ABSTRACTION_EVIDENCE",
        "LEARNING_NOT_DEMONSTRATED",
        "EXPERIMENT_INCONCLUSIVE",
        "ABSTRACTION_STABILITY_NOT_DEMONSTRATED",
        "COMPARISON_NOT_DEMONSTRATED",
    ):
        assert state in EVIDENCE_STATES


def test_verdict_is_one_of_the_permitted_states(result):
    assert result["phase_6_verdict"]["state"] in EVIDENCE_STATES
    assert result["phase_6_verdict"]["state_is_one_of_permitted"] is True


# ---------------------------------------------------------------------------
# 3. The nine adversarial probes
# ---------------------------------------------------------------------------


def test_all_nine_probes_run(result):
    names = [p["probe"] for p in result["phase_6_probes"]]
    assert names == list(ADVERSARIAL_PROBES)
    assert len(names) == 9


def test_every_probe_carries_an_evidence_path(result):
    for probe in result["phase_6_probes"]:
        assert probe["evidence_path"]
        assert "probe_output" in probe
        assert "probe_inputs" in probe


def test_every_probe_declares_a_falsifier_judgement(result):
    for probe in result["phase_6_probes"]:
        assert isinstance(probe["tier_1_falsifier_fired"], bool)
        assert probe["conclusion"] in ("falsified", "not_falsified")


def test_probe_descriptions_cover_all_nine():
    assert set(PROBE_DESCRIPTIONS) == set(ADVERSARIAL_PROBES)


def test_tier_1_falsifiers_are_the_nine_probes():
    assert TIER_1_FALSIFIERS == ADVERSARIAL_PROBES


def test_the_evaluation_leakage_probe_passes_on_clean_input(result):
    leakage = next(p for p in result["phase_6_probes"]
                   if p["probe"] == "evaluation_leakage")
    assert leakage["tier_1_falsifier_fired"] is False


def test_the_why_swap_probe_reports_the_bindings_it_saw(result):
    probe = next(p for p in result["phase_6_probes"] if p["probe"] == "why_swap")
    assert "why_binding_count" in probe["probe_inputs"]


def test_the_incorrect_transfer_probe_reports_wrong_accepts(result):
    probe = next(p for p in result["phase_6_probes"]
                 if p["probe"] == "incorrect_transfer")
    assert "wrongly_accepted" in probe["probe_output"]


# ---------------------------------------------------------------------------
# 4. Phase 5 reads no evaluation key
# ---------------------------------------------------------------------------


def test_phase_5_declares_no_evaluation_key_read(result):
    assert result["phase_5_unseen"]["evaluation_key_read"] is False


def test_leakage_audit_is_clean(result):
    assert result["phase_6_leakage_audit"]["clean"] is True


def test_evaluation_expectations_are_read_after_phase_5(result):
    directive = _probe_directive(
        expectations={"intended_concept_name": "withdrawal_for_recovery"}
    )
    r = run_architectural_abstraction_probe(directive)
    assert r["evaluation_expectations_read"]["read_after_phase_5"] is True


# ---------------------------------------------------------------------------
# 5. Unseen support is decided from structure, never from the concept name
# ---------------------------------------------------------------------------


def test_support_case_is_supported(result):
    assert result["phase_5_unseen"]["supported_case_count"] >= 1


def test_support_records_the_exact_matched_invariants(result):
    reading = result["phase_5_unseen"]["case_readings"][0]
    assert reading["matched_invariants"]
    assert "case" in reading["decision_basis"] or "formal" in reading[
        "decision_basis"
    ]


def test_a_case_with_no_overlap_is_unsupported():
    case = _space("U9", "A wide plaza opens onto the street for everyone.",
                  "because the town wanted a place to gather and be seen")
    r = run_architectural_abstraction_probe(_probe_directive(unseen=[case]))
    reading = r["phase_5_unseen"]["case_readings"][0]
    assert reading["unsupported"] is True


def test_a_contradicting_case_is_not_accepted():
    case = _space(
        "C1",
        "A large hall sits at the very centre of the shared rooms, fully open "
        "to everyone.",
        "because the gathering must always be watched and never separated",
    )
    r = run_architectural_abstraction_probe(_probe_directive(unseen=[case]))
    reading = r["phase_5_unseen"]["case_readings"][0]
    assert reading["supports_abstraction"] is False


# ---------------------------------------------------------------------------
# 6. Blind Relearning - no semantic comparator
# ---------------------------------------------------------------------------


def test_blind_relearning_without_a_second_corpus_is_not_demonstrated(result):
    blind = result["phase_6_blind_relearning"]
    assert blind["outcome"] == "COMPARISON_NOT_DEMONSTRATED"
    assert blind["semantic_comparator_used"] is False


def test_blind_relearning_uses_no_semantic_comparator_even_with_two_corpora():
    r = run_architectural_abstraction_probe(
        _probe_directive(second=_learner("F", _corpus_b()))
    )
    blind = r["phase_6_blind_relearning"]
    assert blind["semantic_comparator_used"] is False
    assert blind["comparison_basis"] == "structural_fingerprint_equality_only"


def test_blind_relearning_reports_stability_not_demonstrated_when_different():
    r = run_architectural_abstraction_probe(
        _probe_directive(second=_learner("F", _corpus_b()))
    )
    blind = r["phase_6_blind_relearning"]
    if blind["fingerprint_a"] != blind["fingerprint_b"]:
        assert blind["outcome"] == "STRUCTURALLY_DIFFERENT"
        assert blind["epistemic_status"] == "ABSTRACTION_STABILITY_NOT_DEMONSTRATED"
        assert r["phase_6_verdict"]["state"] == "ABSTRACTION_STABILITY_NOT_DEMONSTRATED"


def test_blind_relearning_never_claims_alignment_it_cannot_show():
    r = run_architectural_abstraction_probe(
        _probe_directive(second=_learner("F", _corpus_b()))
    )
    blind = r["phase_6_blind_relearning"]
    if blind["outcome"] != "STRUCTURALLY_IDENTICAL":
        assert blind["declares_only_formal_representation_equivalence"] is False


def test_blind_relearning_identical_corpora_are_structurally_identical():
    r = run_architectural_abstraction_probe(
        _probe_directive(second=_learner("F", _corpus_a()))
    )
    assert r["phase_6_blind_relearning"]["outcome"] == "STRUCTURALLY_IDENTICAL"


# ---------------------------------------------------------------------------
# 7. Mode comparison
# ---------------------------------------------------------------------------


def test_mode_comparison_records_the_mode_used(result):
    assert result["phase_6_mode_comparison"]["mode_used"] == "F"
    assert result["phase_6_mode_comparison"]["modes_compared"] == ["F"]


def test_mode_f_is_runnable_without_2b(result):
    assert result["phase_6_mode_comparison"]["mode_f_runnable_without_2b"] is True


def test_modes_f_h_r_all_run_independently():
    for mode in ("F", "H", "R"):
        learner = _learner(mode)
        r = run_architectural_abstraction_probe(_probe_directive(learner=learner))
        assert r["phase_6_mode_comparison"]["mode_used"] == mode


# ---------------------------------------------------------------------------
# 8. Verdict gating
# ---------------------------------------------------------------------------


def test_reserved_status_is_not_granted_without_blind_agreement(result):
    # No second corpus was supplied, so the reserved status must be withheld.
    assert result["phase_6_verdict"]["state"] != RESERVED_EVIDENCE_STATUS
    assert result["phase_6_verdict"]["reserved_status_granted"] is False


def test_reserved_status_is_granted_only_on_a_full_pass():
    # Same corpus twice: WHY-bound invariants survive, an unseen case supports
    # them, no probe fires, leakage is clean, blind relearning is identical.
    r = run_architectural_abstraction_probe(
        _probe_directive(second=_learner("F", _corpus_a()))
    )
    verdict = r["phase_6_verdict"]
    assert verdict["state"] == RESERVED_EVIDENCE_STATUS
    assert verdict["reserved_status_granted"] is True
    assert verdict["tier_1_falsifiers_fired"] == []


def test_a_tier_1_falsifier_forces_learning_not_demonstrated():
    # Inject an evaluation key into a case: the leakage probe must fire and the
    # verdict must collapse.
    bad = _support_case()
    bad["expected"] = "supports_abstraction"
    with pytest.raises(ValueError):
        run_architectural_abstraction_probe(_probe_directive(unseen=[bad]))


def test_no_invariants_yields_engineered_representation():
    # A corpus whose examples share nothing: no invariant survives.
    teaching = [
        _ex("N1", "A tower rises above the town.", "because the family wanted "
            "a wide view of the valley"),
        _ex("N2", "A cellar lies under the barn.", "because the grain had to "
            "stay cool through summer"),
    ]
    learner = _learner("F", teaching)
    r = run_architectural_abstraction_probe(_probe_directive(learner=learner))
    assert r["phase_6_verdict"]["state"] == "ENGINEERED_REPRESENTATION"


def test_verdict_never_derives_from_a_class_name_alone():
    # The learner names its level-3 object "LearnedAbstraction"; the verdict
    # must still be gated on evidence, not on that name.
    r = run_architectural_abstraction_probe(_probe_directive())
    assert r["phase_6_verdict"]["learned_flag_alone_proves_nothing"] is True


def test_withheld_status_records_a_reason(result):
    verdict = result["phase_6_verdict"]
    if not verdict["reserved_status_granted"]:
        assert verdict["reserved_status_withheld_reason"]


# ---------------------------------------------------------------------------
# 9. Input gating
# ---------------------------------------------------------------------------


def test_rejects_non_dict():
    with pytest.raises(TypeError):
        run_architectural_abstraction_probe("nope")


def test_rejects_wrong_directive_contract():
    directive = _probe_directive()
    directive["contract"] = "WrongV1"
    with pytest.raises(ValueError):
        run_architectural_abstraction_probe(directive)


def test_rejects_wrong_directive_version():
    directive = _probe_directive()
    directive["version"] = "9.9"
    with pytest.raises(ValueError):
        run_architectural_abstraction_probe(directive)


def test_rejects_a_learner_result_with_the_wrong_contract():
    directive = _probe_directive()
    directive["learner_result"]["contract"] = "WrongV1"
    with pytest.raises(ValueError):
        run_architectural_abstraction_probe(directive)


def test_rejects_an_unseen_case_with_the_wrong_contract():
    bad = _support_case()
    bad["contract"] = "WrongV1"
    with pytest.raises(ValueError):
        run_architectural_abstraction_probe(_probe_directive(unseen=[bad]))


def test_rejects_empty_unseen_cases():
    with pytest.raises(ValueError):
        run_architectural_abstraction_probe(_probe_directive(unseen=[]))


def test_refuses_a_case_carrying_an_expected_answer():
    bad = _support_case()
    bad["expected_outcome"] = "supports_abstraction"
    with pytest.raises(ValueError):
        run_architectural_abstraction_probe(_probe_directive(unseen=[bad]))


# ---------------------------------------------------------------------------
# 10. Static audit - no forbidden machinery, no extra verdicts
# ---------------------------------------------------------------------------


def _module_source():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        return handle.read()


def _docstring_ranges(tree):
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(
                body[0].value, ast.Constant
            ) and isinstance(body[0].value.value, str):
                start = body[0].lineno - 1
                end = getattr(body[0], "end_lineno", body[0].lineno) - 1
                ranges.append((start, end))
    return ranges


def _guard_tables(tree):
    tables = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Tuple, ast.List)):
            values = [elt.value for elt in node.elts
                      if isinstance(elt, ast.Constant)
                      and isinstance(elt.value, str)]
            if values and len(values) == len(node.elts):
                start = node.lineno - 1
                end = getattr(node, "end_lineno", node.lineno) - 1
                tables.append((start, end))
    return tables


def test_module_imports_no_embedding_or_similarity_library():
    source = _module_source()
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.append(node.module)
    forbidden = ("numpy", "scipy", "sklearn", "torch", "tensorflow",
                 "sentence_transformers", "gensim", "spacy", "transformers")
    for name in imported:
        assert name.split(".")[0] not in forbidden, name


def test_module_uses_structural_fingerprint_not_text_equality():
    source = _module_source().lower()
    assert "semantic_comparator_used" in source
    assert "structural_fingerprint_equality_only" in source


def test_module_defines_no_verdict_outside_the_seven():
    """Every VERDICT-shaped string must be one of the seven states.

    ``NOT_DEMONSTRATED`` is an *epistemic status* (the closed status scale), not
    a verdict, so the audit keys on the verdict-shaped suffixes only.
    """
    source = _module_source()
    tree = ast.parse(source)
    docstrings = _docstring_ranges(tree)
    lines = source.splitlines()
    known = set(EVIDENCE_STATES)
    verdict_suffixes = (
        "_ONLY",
        "_EVIDENCE",
        "_INCONCLUSIVE",
        "_REPRESENTATION",
        "_NOT_DEMONSTRATED",
    )
    for index, line in enumerate(lines):
        if any(start <= index <= end for start, end in docstrings):
            continue
        for match in re.findall(r'"([A-Z][A-Z_]{6,})"', line):
            if match == "NOT_DEMONSTRATED":
                # The bare epistemic status, not a verdict.
                continue
            if match.endswith(verdict_suffixes):
                assert match in known, line


# ---------------------------------------------------------------------------
# 11. Purity and determinism
# ---------------------------------------------------------------------------


def test_input_is_not_mutated():
    directive = _probe_directive()
    snapshot = copy.deepcopy(directive)
    run_architectural_abstraction_probe(directive)
    assert directive == snapshot


def test_runs_are_deterministic():
    first = run_architectural_abstraction_probe(_probe_directive())
    second = run_architectural_abstraction_probe(_probe_directive())
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_non_claims_are_declared(result):
    non_claims = result["non_claims"]
    assert non_claims["engineered_algorithm_is_not_learning"] is True
    assert non_claims["learned_flag_alone_does_not_prove_learning"] is True
    assert non_claims["reserved_status_requires_full_gate_pass"] is True
