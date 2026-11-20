"""Tests for the V3 abstraction learner and the Mode P / Mode E separation.

The questions this suite answers:
  * is Mode E really denied every architectural relation word?
  * does Mode P stay under its Level-B ceiling?
  * does the learner refuse to overclaim when the corpus supports nothing?
  * is the fingerprint labelled a stability measurement and never evidence?
  * is the learner boundary free of the frozen V2 package?
"""

import ast
import copy
import json
import re

import pytest

from core.knowledge.understanding_foundation.why_condition_abstraction import (
    v3_contracts as C,
)
from core.knowledge.understanding_foundation.why_condition_abstraction import (
    v3_abstraction_learner_v1 as L,
)

MODULE_PATH = (
    "core/knowledge/understanding_foundation/why_condition_abstraction/"
    "v3_abstraction_learner_v1.py"
)


def _ex(example_id, text):
    return {
        "contract": L.TEACHING_EXAMPLE_CONTRACT,
        "version": "1.0",
        "example_id": example_id,
        "text": text,
    }


def _directive(mode, teaching):
    return {
        "contract": L.DIRECTIVE_CONTRACT,
        "version": "1.0",
        "mode": mode,
        "teaching_examples": teaching,
    }


def _corpus():
    return [
        _ex("e1", "the alcove is set back from the passage because the user "
                  "needs to recover"),
        _ex("e2", "a niche sits apart from the corridor so that a person can "
                  "recover quietly"),
        _ex("e3", "a bay stands back from the walkway for the user to recover "
                  "in private"),
    ]


def _mode_p_favourable():
    return [
        _ex("a", "the hall opens onto the court because access is needed"),
        _ex("b", "the lobby opens onto the yard because access is needed"),
        _ex("c", "the room opens onto the garden because access is needed"),
    ]


# ---------------------------------------------------------------------------#
# 1. Contract gating
# ---------------------------------------------------------------------------#


def test_non_dict_directive_is_refused():
    with pytest.raises(TypeError):
        L.run_v3_abstraction_learner(["not", "a", "dict"])


def test_wrong_contract_is_refused():
    with pytest.raises(ValueError):
        L.run_v3_abstraction_learner(
            {"contract": "Other", "version": "1.0", "mode": "P",
             "teaching_examples": _corpus()}
        )


def test_wrong_version_is_refused():
    directive = _directive("P", _corpus())
    directive["version"] = "9.9"
    with pytest.raises(ValueError):
        L.run_v3_abstraction_learner(directive)


def test_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        L.run_v3_abstraction_learner(
            {"contract": L.DIRECTIVE_CONTRACT, "version": "1.0",
             "mode": "X", "teaching_examples": _corpus()}
        )


def test_forbidden_contract_is_refused():
    with pytest.raises(ValueError):
        L.run_v3_abstraction_learner(
            {"contract": "ArchitecturalIFCEntityV1", "version": "1.0",
             "mode": "P", "teaching_examples": _corpus()}
        )


def test_empty_teaching_set_is_refused():
    with pytest.raises(ValueError):
        L.run_v3_abstraction_learner(_directive("P", []))


def test_a_teaching_example_with_a_wrong_contract_is_refused():
    with pytest.raises(ValueError):
        L.run_v3_abstraction_learner(
            _directive("P", [{"contract": "Wrong", "version": "1.0",
                              "example_id": "x", "text": "a wall"}])
        )


# ---------------------------------------------------------------------------#
# 2. Leakage refusal
# ---------------------------------------------------------------------------#


def test_a_teaching_example_carrying_an_expected_answer_is_refused():
    bad = _ex("x", "a plain wall stands there")
    bad["expected"] = "something"
    with pytest.raises(ValueError):
        L.run_v3_abstraction_learner(_directive("P", [bad]))


def test_a_teaching_example_carrying_an_intended_relation_is_refused():
    bad = _ex("x", "a plain wall stands there")
    bad["intended_relation"] = "access"
    with pytest.raises(ValueError):
        L.run_v3_abstraction_learner(_directive("P", [bad]))


# ---------------------------------------------------------------------------#
# 3. MODE E receives NO relation vocabulary
# ---------------------------------------------------------------------------#


def test_mode_e_refuses_a_corpus_containing_a_relation_word():
    with pytest.raises(ValueError):
        L.run_v3_abstraction_learner(
            _directive("E", [_ex("x", "the room gives access to the stair")])
        )


def test_mode_e_refuses_a_directive_supplying_a_relation_vocabulary():
    directive = _directive("E", [_ex("x", "a plain wall stands there")])
    directive["relation_vocabulary"] = ["access"]
    with pytest.raises(ValueError):
        L.run_v3_abstraction_learner(directive)


def test_mode_e_refuses_a_directive_supplying_a_scope_vocabulary():
    directive = _directive("E", [_ex("x", "a plain wall stands there")])
    directive["scope_vocabulary"] = ["boundary_crossing"]
    with pytest.raises(ValueError):
        L.run_v3_abstraction_learner(directive)


def test_mode_e_given_vocabulary_is_empty_in_phase_1():
    result = L.run_v3_abstraction_learner(_directive("E", _corpus()))
    given = result["phase_1_given"]["given"]
    assert given["relation_vocabulary_given"] == []
    assert given["scope_vocabulary_given"] == []
    assert result["phase_1_given"]["mode_e_no_relation_vocabulary"] is True


def test_mode_p_given_vocabulary_is_recorded_in_phase_1():
    result = L.run_v3_abstraction_learner(_directive("P", _corpus()))
    given = result["phase_1_given"]["given"]
    assert given["relation_vocabulary_given"] == list(
        C.MODE_P_RELATION_VOCABULARY
    )


def test_mode_e_output_carries_no_forbidden_relation_word():
    result = L.run_v3_abstraction_learner(_directive("E", _corpus()))
    blob = json.dumps({
        "phase_2": result["phase_2_conditions"],
        "phase_3": result["phase_3_coherence"],
        "phase_4": result["phase_4_abstraction"],
    }, sort_keys=True).lower()
    for term in C.MODE_E_FORBIDDEN_RELATION_TERMS:
        assert not re.search(
            r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])", blob
        ), term


# ---------------------------------------------------------------------------#
# 4. Mode E stores relation_slot as null until the corpus fills it
# ---------------------------------------------------------------------------#


def test_mode_e_relation_slot_starts_null_when_nothing_can_be_derived():
    result = L.run_v3_abstraction_learner(
        _directive("E", [_ex("x", "a plain wall")])
    )
    for entry in result["phase_2_conditions"]["per_example"]:
        for condition in entry["conditions"]:
            assert condition["relation"]["relation_slot"] is None
            assert condition["relation"]["no_coercion_declared"] is True


def test_mode_e_declares_the_derived_origin_of_a_filled_slot():
    result = L.run_v3_abstraction_learner(_directive("E", _corpus()))
    for entry in result["phase_2_conditions"]["per_example"]:
        for condition in entry["conditions"]:
            relation = condition["relation"]
            if relation["relation_slot"] is not None:
                assert relation["relation_slot_origin"] == C.ORIGIN_DERIVED
                assert relation["relation_slot_origin"] != C.ORIGIN_ENGINEERED


# ---------------------------------------------------------------------------#
# 5. Mode P uses the predefined vocabulary, and says so
# ---------------------------------------------------------------------------#


def test_mode_p_records_the_predefined_vocabulary_it_used():
    result = L.run_v3_abstraction_learner(
        _directive("P", _mode_p_favourable())
    )
    abstraction = result["phase_4_abstraction"]["candidate_abstraction"]
    assert abstraction["predefined_relation_vocabulary_used"] == list(
        C.MODE_P_RELATION_VOCABULARY
    )


def test_mode_p_slot_origin_is_engineered_not_derived():
    result = L.run_v3_abstraction_learner(
        _directive("P", _mode_p_favourable())
    )
    for entry in result["phase_2_conditions"]["per_example"]:
        for condition in entry["conditions"]:
            if condition["relation"]["relation_slot"] is not None:
                assert (
                    condition["relation"]["relation_slot_origin"]
                    == C.ORIGIN_ENGINEERED
                )


def test_mode_p_can_reach_its_ceiling_when_the_why_repeats_the_kind():
    result = L.run_v3_abstraction_learner(
        _directive("P", _mode_p_favourable())
    )
    abstraction = result["phase_4_abstraction"]["candidate_abstraction"]
    assert abstraction["reported_evidence_level"] == C.LEVEL_B
    assert abstraction["mode_ceiling"] == C.MODE_P_CEILING


def test_mode_p_never_reports_a_novel_relational_pattern():
    result = L.run_v3_abstraction_learner(
        _directive("P", _mode_p_favourable())
    )
    abstraction = result["phase_4_abstraction"]["candidate_abstraction"]
    assert abstraction["novel_relational_pattern"] is None


# ---------------------------------------------------------------------------#
# 6. The learner refuses to overclaim
# ---------------------------------------------------------------------------#


def test_an_empty_abstraction_reports_level_a_not_a_guess():
    result = L.run_v3_abstraction_learner(_directive("P", _corpus()))
    abstraction = result["phase_4_abstraction"]["candidate_abstraction"]
    assert abstraction["invariants"] == []
    assert abstraction["reported_evidence_level"] == C.LEVEL_A


def test_a_surface_verb_only_pattern_is_diagnosed_as_lexical():
    corpus = [
        _ex("a", "the seat overlooks the court because the viewer needs rest"),
        _ex("b", "the bench overlooks the garden because the sitter needs calm"),
        _ex("c", "the stair overlooks the hall because the walker needs pause"),
    ]
    result = L.run_v3_abstraction_learner(_directive("E", corpus))
    abstraction = result["phase_4_abstraction"]["candidate_abstraction"]
    # A shared verb recurring in every example with a differing WHY is not a
    # why-grounded invariant. The learner must not report above Level B.
    assert abstraction["reported_evidence_level"] in (C.LEVEL_A, C.LEVEL_B)


def test_a_scope_marker_alone_is_never_promoted_to_an_invariant():
    result = L.run_v3_abstraction_learner(_directive("E", _corpus()))
    invariants = result["phase_3_coherence"]["invariant_candidates"]
    assert all(i["slot_kind"] != "scope" for i in invariants)


def test_claimed_as_learning_is_false_on_every_abstraction():
    for mode in C.MODES:
        result = L.run_v3_abstraction_learner(_directive(mode, _corpus()))
        abstraction = result["phase_4_abstraction"]["candidate_abstraction"]
        assert abstraction["claimed_as_learning"] is False
        assert abstraction["claimed_as_conceptual_abstraction_evidence"] is False


# ---------------------------------------------------------------------------#
# 7. Fingerprint is stability, not evidence
# ---------------------------------------------------------------------------#


def test_fingerprint_is_labelled_representation_stability():
    result = L.run_v3_abstraction_learner(_directive("P", _corpus()))
    abstraction = result["phase_4_abstraction"]["candidate_abstraction"]
    assert abstraction["fingerprint_semantics"] == "representation_stability"
    assert abstraction["fingerprint_is_learning_evidence"] is False


def test_fingerprint_is_deterministic():
    first = L.run_v3_abstraction_learner(_directive("P", _corpus()))
    second = L.run_v3_abstraction_learner(_directive("P", _corpus()))
    assert (
        first["phase_4_abstraction"]["candidate_abstraction"]["fingerprint"]
        == second["phase_4_abstraction"]["candidate_abstraction"]["fingerprint"]
    )


# ---------------------------------------------------------------------------#
# 8. The learner never assigns the reserved status
# ---------------------------------------------------------------------------#


def test_the_learner_never_assigns_the_reserved_status():
    for mode in C.MODES:
        result = L.run_v3_abstraction_learner(_directive(mode, _corpus()))
        for key in ("phase_1_given", "phase_2_conditions", "phase_3_coherence",
                    "phase_4_abstraction"):
            assert (
                result[key].get("epistemic_status")
                != C.STATUS_CONCEPTUAL_ABSTRACTION_EVIDENCE
            )
        assert (
            result["evidence_level_reached"]
            != C.STATUS_CONCEPTUAL_ABSTRACTION_EVIDENCE
        )


def test_learner_assignable_statuses_exclude_the_reserved_one():
    result = L.run_v3_abstraction_learner(_directive("P", _corpus()))
    assert (
        C.STATUS_CONCEPTUAL_ABSTRACTION_EVIDENCE
        not in result["learner_assignable_statuses"]
    )


# ---------------------------------------------------------------------------#
# 9. Ledgers and provenance
# ---------------------------------------------------------------------------#


def test_every_run_emits_both_ledgers():
    result = L.run_v3_abstraction_learner(_directive("P", _corpus()))
    assert result["engineering_ledger"]
    assert result["emergent_ledger"]
    assert all(
        v == C.ORIGIN_ENGINEERED for v in result["engineering_ledger"].values()
    )


def test_every_run_emits_the_representation_provenance_ledger():
    result = L.run_v3_abstraction_learner(_directive("E", _corpus()))
    ledger = result["representation_provenance_ledger"]
    assert ledger == C.REPRESENTATION_PROVENANCE_LEDGER
    # Every predefined relation kind must be marked as MODE-P-ONLY.
    assert ledger["predefined_relation_kind"]["may_be_mode_e"] is False
    assert ledger["predefined_scope_kind"]["may_be_mode_e"] is False


def test_non_claims_are_emitted_on_every_run():
    result = L.run_v3_abstraction_learner(_directive("P", _corpus()))
    assert result["non_claims"] == C.REQUIRED_NON_CLAIMS
    assert result["non_claims"][
        "mode_p_cannot_report_novel_relational_pattern"
    ] is True


def test_the_boundary_is_transient_and_read_only():
    result = L.run_v3_abstraction_learner(_directive("P", _corpus()))
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_the_input_is_not_mutated():
    directive = _directive("P", _corpus())
    snapshot = copy.deepcopy(directive)
    L.run_v3_abstraction_learner(directive)
    assert directive == snapshot


# ---------------------------------------------------------------------------#
# 10. Static audits
# ---------------------------------------------------------------------------#


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
                ranges.append((body[0].lineno - 1,
                               getattr(body[0], "end_lineno",
                                       body[0].lineno) - 1))
    return ranges


def _guard_tables(tree):
    tables = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Tuple, ast.List)):
            values = [elt.value for elt in node.elts
                      if isinstance(elt, ast.Constant)
                      and isinstance(elt.value, str)]
            if values and len(values) == len(node.elts):
                tables.append((node.lineno - 1,
                               getattr(node, "end_lineno", node.lineno) - 1))
    return tables


def test_module_does_not_import_the_frozen_v2_package():
    tree = ast.parse(_module_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "architectural_abstraction" not in node.module, node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "architectural_abstraction" not in alias.name


def test_module_imports_no_similarity_or_embedding_library():
    tree = ast.parse(_module_source())
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.append(node.module)
    for name in imported:
        assert name.split(".")[0] not in (
            "numpy", "scipy", "sklearn", "torch", "tensorflow",
            "sentence_transformers", "gensim", "spacy", "transformers",
        ), name


def test_module_does_not_use_a_forbidden_emitted_term_in_logic():
    source = _module_source()
    tree = ast.parse(source)
    excluded = _docstring_ranges(tree) + _guard_tables(tree)
    for index, line in enumerate(source.splitlines()):
        if any(start <= index <= end for start, end in excluded):
            continue
        stripped = re.sub(r"#.*", "", line)
        if stripped.strip().startswith(("def ", "class ", "import ", "from ")):
            continue
        for term in ("design_solution", "optimal", "recommended"):
            assert not re.search(
                r"(?<![a-z0-9_])" + term + r"(?![a-z0-9_])",
                stripped.lower(),
            ), line


def test_module_is_ascii_apart_from_typographic_rules():
    source = _module_source()
    tree = ast.parse(source)
    docstrings = _docstring_ranges(tree)
    box = set("\u2500\u2502\u250c\u2510\u2514\u2518\u251c\u2524\u252c\u2534"
              "\u253c\u2550\u2551\u2554\u2557\u255a\u255d")
    for index, line in enumerate(source.splitlines()):
        if any(start <= index <= end for start, end in docstrings):
            continue
        for char in line:
            if char in box:
                continue
            assert ord(char) <= 0x7F, repr(line)
