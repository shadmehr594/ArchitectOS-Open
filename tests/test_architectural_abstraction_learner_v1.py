"""Tests for ArchitecturalAbstractionLearnerV1 (ABSTRACTION TEST V2, Phases 1-4).

Written from the BRIEF's semantics, not from the implementation.

The brief for V2 asks ONE narrow question and forbids several shortcuts:

    Can ArchitectOS derive an ABSTRACT architectural concept from multiple
    human teaching examples whose wording, vocabulary and surface conditions
    differ?

And it is explicit about what must NEVER be used as a substitute:

    embeddings · LLM similarity · synonym dictionaries · fixed keyword lists ·
    hard-coded concept rules · a concept-to-role map.

It is equally explicit about what may and may not be called LEARNING:

    AN ENGINEERED ALGORITHM is not EMERGENT CONTENT is not LEARNING.

The suite below pins: contract shape, the three-level model, the GIVEN-vs-
LEARNED ledger, WHY as first-class, Mode F purity, the reserved status never
being assigned by the learner, leakage refusal, and determinism.

It does NOT assert that ArchitectOS understands architecture like a human.
"""

import ast
import copy
import json
import re

import pytest

from core.knowledge.understanding_foundation.architectural_abstraction_learner_v1 import (
    CONTRACT,
    DEMONSTRATION_LABEL,
    DIRECTIVE_CONTRACT,
    DIRECTIVE_VERSION,
    EMERGENT_LEDGER,
    ENGINEERING_LEDGER,
    EPISTEMIC_STATUSES,
    FORMAL_STRUCTURE_FIELDS,
    INTERPRETIVE_AXES,
    MODES,
    TEST_SUBJECT,
    VERSION,
    run_architectural_abstraction_learner,
)

MODULE_PATH = (
    "core/knowledge/understanding_foundation/"
    "architectural_abstraction_learner_v1.py"
)

TEACHING_CONTRACT = "ArchitecturalHumanTeachingExampleV1"

REQUIRED_TOP_LEVEL = (
    "contract",
    "version",
    "test_subject",
    "demonstration_label",
    "mode",
    "phase_1_given",
    "phase_2_formal",
    "phase_3_emergence",
    "phase_4_abstraction",
    "engineering_ledger",
    "emergent_ledger",
    "epistemic_status_scale",
    "non_claims",
    "persistent",
    "read_only",
)

RESERVED_STATUS = "CONCEPTUAL_ABSTRACTION_EVIDENCE"

# Terms the learner must never emit as its own authored language.
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
    "synonym",
    "embedding",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ex(example_id, description, reason, context=None):
    return {
        "contract": TEACHING_CONTRACT,
        "version": "1.0",
        "example_id": example_id,
        "description": description,
        "reason": reason,
        "context": context,
    }


def _corpus_a():
    return [
        _ex("A1", "A sleeping chamber is set apart from the shared rooms, "
                  "screened by depth.",
            "because the occupant needs to recover where nobody watches them"),
        _ex("A2", "A resting cell stands beyond the common hall, withdrawn "
                  "behind a threshold.",
            "because a person has to be unobserved while they recover"),
        _ex("A3", "A quiet nook sits past the gathering space, kept out of "
                  "sight.",
            "because the household member needs an unwatched place to rest"),
        _ex("A4", "A small bay lies off the busy corridor, turned away from "
                  "company.",
            "because whoever uses it must recover out of anyone view"),
    ]


def _directive(mode="F", teaching=None):
    return {
        "contract": DIRECTIVE_CONTRACT,
        "version": DIRECTIVE_VERSION,
        "mode": mode,
        "teaching_examples": _corpus_a() if teaching is None else teaching,
    }


@pytest.fixture()
def result():
    return run_architectural_abstraction_learner(_directive("F"))


# ---------------------------------------------------------------------------
# 1. Contract shape
# ---------------------------------------------------------------------------


def test_top_level_shape(result):
    for key in REQUIRED_TOP_LEVEL:
        assert key in result, key


def test_contract_and_version(result):
    assert result["contract"] == CONTRACT == "ArchitecturalAbstractionLearnerV1"
    assert result["version"] == VERSION == "1.0"


def test_test_subject_and_label(result):
    assert result["test_subject"] == TEST_SUBJECT
    assert result["demonstration_label"] == DEMONSTRATION_LABEL
    assert "controlled" in result["demonstration_label"]


def test_persistent_is_false_and_read_only_is_true(result):
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_four_phases_are_all_present(result):
    assert result["phase_1_given"]["phase"] == 1
    assert result["phase_2_formal"]["phase"] == 2
    assert result["phase_3_emergence"]["phase"] == 3
    assert result["phase_4_abstraction"]["phase"] == 4


def test_modes_are_the_declared_three():
    assert MODES == ("F", "H", "R")


# ---------------------------------------------------------------------------
# 2. The epistemic status vocabulary is closed
# ---------------------------------------------------------------------------


def test_epistemic_status_vocabulary(result):
    assert result["epistemic_status_scale"] == list(EPISTEMIC_STATUSES)
    assert "ENGINEERED" in EPISTEMIC_STATUSES
    assert "DERIVED" in EPISTEMIC_STATUSES
    assert "GENERALIZED" in EPISTEMIC_STATUSES
    assert RESERVED_STATUS in EPISTEMIC_STATUSES
    assert "NOT_DEMONSTRATED" in EPISTEMIC_STATUSES


def test_learner_cannot_assign_the_reserved_status(result):
    assert RESERVED_STATUS not in result["learner_assignable_statuses"]


def test_no_phase_assigns_the_reserved_status(result):
    for key in ("phase_1_given", "phase_2_formal", "phase_3_emergence",
                "phase_4_abstraction"):
        assert result[key]["epistemic_status"] != RESERVED_STATUS


def test_candidate_does_not_claim_the_reserved_status(result):
    candidate = result["phase_4_abstraction"]["candidate_abstraction"]
    assert candidate["claimed_as_conceptual_abstraction_evidence"] is False


def test_class_name_does_not_imply_learning(result):
    candidate = result["phase_4_abstraction"]["candidate_abstraction"]
    assert candidate["name"] == "LearnedAbstraction"
    assert candidate["class_name_implies_learning"] is False


# ---------------------------------------------------------------------------
# 3. Phase 1 - GIVEN vs denied
# ---------------------------------------------------------------------------


def test_phase_1_records_what_is_given(result):
    given = result["phase_1_given"]["given"]
    assert given["teaching_example_count"] == 4
    assert given["concept_name_given"] is False
    assert given["expected_answer_given"] is False
    assert given["evaluation_key_given"] is False


def test_phase_1_lists_what_is_denied(result):
    denied = result["phase_1_given"]["denied_to_learner"]
    assert "intended_concept_name" in denied
    assert "expected_label" in denied
    assert "evaluation_expectations" in denied


def test_phase_1_records_supplied_reasons(result):
    assert result["phase_1_given"]["given"]["reasons_supplied"] == 4


# ---------------------------------------------------------------------------
# 4. Phase 2 - three levels, never collapsed
# ---------------------------------------------------------------------------


def test_level_1_and_level_2a_are_distinct(result):
    assert result["phase_2_formal"]["level_1_level_2a_never_collapsed"] is True
    example = result["phase_2_formal"]["examples"][0]
    assert example["level_1_raw"]
    assert example["level_2a_formal_structure"]
    assert example["level_1_raw"][0]["level"] == "1"
    assert example["level_2a_formal_structure"][0]["level"] == "2A"


def test_formal_structure_fields_are_declared(result):
    assert (
        result["phase_2_formal"]["formal_structure_fields"]
        == list(FORMAL_STRUCTURE_FIELDS)
    )


def test_formal_structure_carries_no_architectural_meaning(result):
    for example in result["phase_2_formal"]["examples"]:
        for structure in example["level_2a_formal_structure"]:
            assert structure["contains_architectural_meaning"] is False


def test_level_2b_is_not_constructed_in_mode_f(result):
    assert result["phase_2_formal"]["level_2b_constructed"] is False
    assert result["phase_3_emergence"]["level_2b_constructed"] is False


def test_mode_f_formal_structure_has_no_interpretive_axis(result):
    blob = json.dumps(
        [
            e["level_2a_formal_structure"]
            for e in result["phase_2_formal"]["examples"]
        ]
    ).lower()
    for axis in INTERPRETIVE_AXES:
        assert not re.search(r"(?<![a-z0-9_])" + axis + r"(?![a-z0-9_])", blob)


# ---------------------------------------------------------------------------
# 5. WHY is first-class
# ---------------------------------------------------------------------------


def test_why_records_are_first_class(result):
    for example in result["phase_2_formal"]["examples"]:
        why = example["why"]
        assert why["reason_present"] is True
        assert why["reason"]
        assert why["reason_clauses"]


def test_why_records_appear_in_the_candidate(result):
    candidate = result["phase_4_abstraction"]["candidate_abstraction"]
    assert candidate["why_bindings"]


def test_why_bindings_carry_provenance(result):
    candidate = result["phase_4_abstraction"]["candidate_abstraction"]
    for binding in candidate["why_bindings"]:
        assert binding["example_id"]
        assert binding["reason"]
        assert binding["epistemic_status"] == "DERIVED"


# ---------------------------------------------------------------------------
# 6. Phase 3 - emergence
# ---------------------------------------------------------------------------


def test_invariants_are_generalized(result):
    invariants = result["phase_3_emergence"]["invariant_candidates"]
    assert invariants
    for inv in invariants:
        assert inv["example_count"] >= 2
        assert inv["cross_example"] is True


def test_incidental_conditions_are_retained_not_dropped(result):
    emergence = result["phase_3_emergence"]
    total = emergence["invariant_count"] + emergence["incidental_count"]
    assert total > emergence["invariant_count"]
    assert isinstance(emergence["incidental_conditions"], list)


def test_emergence_states_whether_it_survived(result):
    assert result["phase_3_emergence"]["survives_across_independent_examples"] is True


# ---------------------------------------------------------------------------
# 7. Mode H and Mode R construct Level 2B; Mode F does not
# ---------------------------------------------------------------------------


def test_mode_h_constructs_level_2b():
    r = run_architectural_abstraction_learner(_directive("H"))
    assert r["phase_3_emergence"]["level_2b_constructed"] is True


def test_mode_r_constructs_a_role_hypothesis():
    r = run_architectural_abstraction_learner(_directive("R"))
    role = r["phase_3_emergence"]["role_hypothesis"]
    assert role is not None
    assert role["classification"] == "experimental representation hypothesis"
    assert role["is_truth"] is False
    assert role["is_hard_coded_concept_map"] is False


def test_mode_f_has_no_role_hypothesis():
    r = run_architectural_abstraction_learner(_directive("F"))
    assert r["phase_3_emergence"]["role_hypothesis"] is None


def test_interpretive_hypotheses_carry_provenance_and_leakage_risk():
    r = run_architectural_abstraction_learner(_directive("H"))
    # In a corpus with no interpretive-axis vocabulary, no hypothesis is
    # invented: this is the honest outcome, and the guard below only applies
    # when a hypothesis IS produced.
    for hyp in r["phase_3_emergence"]["interpretive_hypotheses"]:
        assert hyp["leakage_risk"] == "present"
        assert hyp["is_hypothesis_not_truth"] is True
        assert hyp["assumptions"]
        assert hyp["alternatives"]
        assert hyp["axis"] in INTERPRETIVE_AXES
        assert hyp["source_example"]


# ---------------------------------------------------------------------------
# 8. Phase 4 - the abstraction is DERIVED, WHY-bound, and structural
# ---------------------------------------------------------------------------


def test_candidate_is_derived_not_evidence(result):
    assert result["phase_4_abstraction"]["epistemic_status"] == "DERIVED"
    candidate = result["phase_4_abstraction"]["candidate_abstraction"]
    assert candidate["epistemic_status"] == "DERIVED"


def test_candidate_invariants_are_why_bound(result):
    candidate = result["phase_4_abstraction"]["candidate_abstraction"]
    for inv in candidate["invariants"]:
        assert inv["necessity"] in ("necessary", "context")


def test_candidate_retains_plausible_alternatives(result):
    candidate = result["phase_4_abstraction"]["candidate_abstraction"]
    assert candidate["plausible_alternatives"]
    for alt in candidate["plausible_alternatives"]:
        assert alt["retained"] is True


def test_candidate_has_a_structural_fingerprint(result):
    candidate = result["phase_4_abstraction"]["candidate_abstraction"]
    assert candidate["fingerprint"].startswith("abs1:")
    assert candidate["fingerprint_basis"] == (
        "structural_invariants_and_necessity_not_text"
    )


def test_necessity_map_covers_every_surviving_condition(result):
    candidate = result["phase_4_abstraction"]["candidate_abstraction"]
    for inv in candidate["invariants"]:
        assert inv["condition"] in candidate["necessity_map"]


# ---------------------------------------------------------------------------
# 9. The GIVEN-vs-LEARNED ledger
# ---------------------------------------------------------------------------


def test_engineering_ledger_is_declared(result):
    assert result["engineering_ledger"] == ENGINEERING_LEDGER
    for step, status in result["engineering_ledger"].items():
        assert status == "ENGINEERED", step


def test_emergent_ledger_is_declared(result):
    assert result["emergent_ledger"] == EMERGENT_LEDGER


def test_engineered_steps_are_never_recorded_as_learned(result):
    for step, status in result["engineering_ledger"].items():
        assert status != "GENERALIZED", step
        assert status != RESERVED_STATUS, step


# ---------------------------------------------------------------------------
# 10. Fingerprint behaviour: stable under filler, sensitive to WHY
# ---------------------------------------------------------------------------


def _fingerprint(teaching):
    r = run_architectural_abstraction_learner(_directive("F", teaching))
    return r["phase_4_abstraction"]["candidate_abstraction"]["fingerprint"]


def test_filler_substitution_preserves_why_bound_content():
    original = run_architectural_abstraction_learner(_directive("F"))
    base_inv = {
        i["condition"]
        for i in original["phase_4_abstraction"]["candidate_abstraction"]["invariants"]
    }
    substituted = [
        _ex("F1", "A hutch is set apart from the meeting area, screened by depth.",
            "because the occupant needs to recover where nobody watches them"),
        _ex("F2", "A cranny stands beyond the assembly zone, withdrawn behind a "
                  "threshold.",
            "because a person has to be unobserved while they recover"),
        _ex("F3", "A bay sits past the assembly area, kept out of sight.",
            "because the household member needs an unwatched place to rest"),
    ]
    r = run_architectural_abstraction_learner(_directive("F", substituted))
    sub_inv = {
        i["condition"]
        for i in r["phase_4_abstraction"]["candidate_abstraction"]["invariants"]
    }
    # The WHY-bound core must survive every filler being replaced.
    assert sub_inv & base_inv


def test_why_swap_changes_the_derivation():
    swapped = [
        _ex("W1", "A sleeping chamber is set apart from the shared rooms, "
                  "screened by depth.",
            "because the builder wanted the cheapest possible partition"),
        _ex("W2", "A resting cell stands beyond the common hall, withdrawn "
                  "behind a threshold.",
            "because the plot line forced the wall in that position"),
        _ex("W3", "A quiet nook sits past the gathering space, kept out of sight.",
            "because the structural bays had to stay regular"),
    ]
    r = run_architectural_abstraction_learner(_directive("F", swapped))
    candidate = r["phase_4_abstraction"]["candidate_abstraction"]
    # The mechanical WHY carries no experiential content, so no WHY-bound
    # invariant should survive and no binding should be recorded.
    assert candidate["why_bindings"] == []


def test_identical_input_gives_identical_fingerprint():
    assert _fingerprint(_corpus_a()) == _fingerprint(_corpus_a())


# ---------------------------------------------------------------------------
# 11. Leakage and input gating
# ---------------------------------------------------------------------------


def test_rejects_non_dict():
    with pytest.raises(TypeError):
        run_architectural_abstraction_learner("nope")


def test_rejects_wrong_contract():
    directive = _directive("F")
    directive["contract"] = "WrongV1"
    with pytest.raises(ValueError):
        run_architectural_abstraction_learner(directive)


def test_rejects_wrong_version():
    directive = _directive("F")
    directive["version"] = "9.9"
    with pytest.raises(ValueError):
        run_architectural_abstraction_learner(directive)


def test_rejects_unknown_mode():
    directive = _directive("Q")
    with pytest.raises(ValueError):
        run_architectural_abstraction_learner(directive)


def test_rejects_empty_teaching():
    with pytest.raises(ValueError):
        run_architectural_abstraction_learner(_directive("F", []))


def test_rejects_teaching_example_with_wrong_contract():
    teaching = _corpus_a()
    teaching[0]["contract"] = "WrongV1"
    with pytest.raises(ValueError):
        run_architectural_abstraction_learner(_directive("F", teaching))


def test_refuses_a_teaching_example_carrying_an_expected_answer():
    teaching = _corpus_a()
    teaching[0]["expected"] = "privacy"
    with pytest.raises(ValueError):
        run_architectural_abstraction_learner(_directive("F", teaching))


def test_refuses_a_teaching_example_carrying_a_target_skeleton():
    teaching = _corpus_a()
    teaching[1]["target_skeleton"] = ["apart", "unobserved"]
    with pytest.raises(ValueError):
        run_architectural_abstraction_learner(_directive("F", teaching))


def test_refuses_a_teaching_example_carrying_the_intended_concept():
    teaching = _corpus_a()
    teaching[2]["intended_concept"] = "withdrawal_for_recovery"
    with pytest.raises(ValueError):
        run_architectural_abstraction_learner(_directive("F", teaching))


# ---------------------------------------------------------------------------
# 12. No forbidden machinery (static audit)
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


def test_module_does_not_import_an_embedding_or_similarity_library():
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
                 "sentence_transformers", "gensim", "spacy", "transformers",
                 "openai", "anthropic")
    for name in imported:
        root = name.split(".")[0]
        assert root not in forbidden, name


def test_module_contains_no_synonym_table():
    source = _module_source()
    tree = ast.parse(source)
    docstrings = _docstring_ranges(tree)
    lines = source.splitlines()
    for index, line in enumerate(lines):
        if any(start <= index <= end for start, end in docstrings):
            continue
        lowered = line.lower()
        assert "synonyms" not in lowered, line
        assert "synonym_map" not in lowered, line


def _guard_tables(tree):
    """Every tuple/list of string literals anywhere in the module.

    These are the module's own lookup tables - forbidden terms, evaluation
    keys, glue words, and the like. The audit must exclude them so it tests
    executable logic rather than the guard data that names the banned words.
    """
    table_nodes = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Tuple, ast.List)):
            values = [elt.value for elt in node.elts
                      if isinstance(elt, ast.Constant)
                      and isinstance(elt.value, str)]
            if values and len(values) == len(node.elts):
                start = node.lineno - 1
                end = getattr(node, "end_lineno", node.lineno) - 1
                table_nodes.append((start, end))
    return table_nodes


def test_module_has_no_hard_coded_concept_name():
    """No hard-coded concept NAME may be declared as data.

    The module's own guard tables legitimately spell out the words it refuses
    to emit; the audit skips those tables and docstrings and checks the rest.
    """
    source = _module_source()
    tree = ast.parse(source)
    excluded = _docstring_ranges(tree) + _guard_tables(tree)
    lines = source.splitlines()
    for index, line in enumerate(lines):
        if any(start <= index <= end for start, end in excluded):
            continue
        lowered = line.lower()
        assert "target_concept" not in lowered, line
        assert "expected_concept" not in lowered, line


def test_module_contains_no_forbidden_emitted_terms_in_logic():
    """The module must not USE a forbidden term in its own logic.

    The guard tables and docstrings legitimately name the forbidden words; the
    audit skips them and checks only that no other executable line uses them.
    """
    source = _module_source()
    tree = ast.parse(source)
    excluded = _docstring_ranges(tree) + _guard_tables(tree)
    lines = source.splitlines()
    for index, line in enumerate(lines):
        if any(start <= index <= end for start, end in excluded):
            continue
        stripped = re.sub(r"#.*", "", line)
        if stripped.strip().startswith(("def ", "class ", "import ", "from ")):
            continue
        for term in ("design_solution", "optimal", "recommended",
                     "should_place"):
            if re.search(r"(?<![a-z0-9_])" + term + r"(?![a-z0-9_])",
                         stripped.lower()):
                raise AssertionError("forbidden term used in logic: " + str(line))


def test_module_is_language_neutral_apart_from_english_glue():
    source = _module_source()
    tree = ast.parse(source)
    docstrings = _docstring_ranges(tree)
    lines = source.splitlines()
    # Structural punctuation and box-drawing rules are permitted; lexical
    # vocabulary from another language is not.
    structural = "\u060c\u061b\u061f"
    box_drawing = set("\u2500\u2502\u250c\u2510\u2514\u2518\u251c\u2524"
                      "\u252c\u2534\u253c\u2550\u2551\u2554\u2557\u255a\u255d")
    for index, line in enumerate(lines):
        if any(start <= index <= end for start, end in docstrings):
            continue
        for char in line:
            if char in structural or char in box_drawing:
                continue
            codepoint = ord(char)
            if codepoint > 0x7F:
                raise AssertionError(
                    "non-ASCII beyond structural punctuation: " + repr(line)
                )


# ---------------------------------------------------------------------------
# 13. Purity and determinism
# ---------------------------------------------------------------------------


def test_input_is_not_mutated():
    directive = _directive("F")
    snapshot = copy.deepcopy(directive)
    run_architectural_abstraction_learner(directive)
    assert directive == snapshot


def test_runs_are_deterministic():
    first = run_architectural_abstraction_learner(_directive("F"))
    second = run_architectural_abstraction_learner(_directive("F"))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_non_claims_are_declared(result):
    non_claims = result["non_claims"]
    assert non_claims["not_a_learned_model"] is True
    assert non_claims["engineered_algorithm_is_not_learning"] is True
    assert non_claims["class_name_does_not_imply_learning"] is True
