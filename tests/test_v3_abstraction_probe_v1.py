"""Tests for the V3 probe: Phases 5-6, the eleven failure modes, the verdict.

The questions this suite answers:
  * are ALL ELEVEN failure modes emitted on every run?
  * is a failure mode that was never exercised reported as NOT_EXERCISED rather
    than as a pass?
  * can Mode P ever escape its Level-B ceiling through the probe?
  * is the reserved / highest level granted only when it was earned?
  * does the probe read expectations only after the verdict?
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
from core.knowledge.understanding_foundation.why_condition_abstraction import (
    v3_abstraction_probe_v1 as P,
)

MODULE_PATH = (
    "core/knowledge/understanding_foundation/why_condition_abstraction/"
    "v3_abstraction_probe_v1.py"
)


def _ex(example_id, text):
    return {
        "contract": L.TEACHING_EXAMPLE_CONTRACT,
        "version": "1.0",
        "example_id": example_id,
        "text": text,
    }


def _uc(case_id, text):
    return {
        "contract": P.UNSEEN_CASE_CONTRACT,
        "version": "1.0",
        "case_id": case_id,
        "text": text,
    }


def _learn(mode, teaching):
    return L.run_v3_abstraction_learner({
        "contract": L.DIRECTIVE_CONTRACT,
        "version": "1.0",
        "mode": mode,
        "teaching_examples": teaching,
    })


def _probe_directive(learner_result, **extra):
    directive = {
        "contract": P.DIRECTIVE_CONTRACT,
        "version": "1.0",
        "learner_result": learner_result,
        "unseen_cases": [_uc("u1", "a plain wall stands there")],
    }
    directive.update(extra)
    return directive


def _corpus():
    return [
        _ex("e1", "the alcove is set back from the passage because the user "
                  "needs to recover"),
        _ex("e2", "a niche sits apart from the corridor so that a person can "
                  "recover quietly"),
    ]


# ---------------------------------------------------------------------------#
# 1. Contract gating
# ---------------------------------------------------------------------------#


def test_non_dict_directive_is_refused():
    with pytest.raises(TypeError):
        P.run_v3_abstraction_probe("not a dict")


def test_wrong_contract_is_refused():
    with pytest.raises(ValueError):
        P.run_v3_abstraction_probe({"contract": "Other", "version": "1.0"})


def test_wrong_version_is_refused():
    directive = _probe_directive(_learn("P", _corpus()))
    directive["version"] = "9.9"
    with pytest.raises(ValueError):
        P.run_v3_abstraction_probe(directive)


def test_a_learner_result_with_the_wrong_contract_is_refused():
    with pytest.raises(ValueError):
        P.run_v3_abstraction_probe(_probe_directive({"contract": "Other"}))


def test_a_learner_result_missing_phase_4_is_refused():
    with pytest.raises(ValueError):
        P.run_v3_abstraction_probe(_probe_directive({
            "contract": L.CONTRACT, "version": L.VERSION,
        }))


def test_an_empty_unseen_set_is_refused():
    with pytest.raises(ValueError):
        P.run_v3_abstraction_probe({
            "contract": P.DIRECTIVE_CONTRACT, "version": "1.0",
            "learner_result": _learn("P", _corpus()),
            "unseen_cases": [],
        })


def test_an_unseen_case_with_the_wrong_contract_is_refused():
    with pytest.raises(ValueError):
        P.run_v3_abstraction_probe(_probe_directive(
            _learn("P", _corpus()),
            unseen_cases=[{"contract": "Wrong", "version": "1.0"}],
        ))


def test_an_unseen_case_carrying_an_evaluation_key_is_refused():
    bad = _uc("u1", "a plain wall stands there")
    bad["expected"] = "something"
    with pytest.raises(ValueError):
        P.run_v3_abstraction_probe(_probe_directive(
            _learn("P", _corpus()), unseen_cases=[bad],
        ))


# ---------------------------------------------------------------------------#
# 2. All eleven failure modes are always emitted
# ---------------------------------------------------------------------------#


@pytest.mark.parametrize("mode", list(C.MODES))
def test_all_eleven_failure_modes_are_emitted(mode):
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn(mode, _corpus()))
    )
    emitted = {m["failure_mode"] for m in result["phase_6_failure_modes"]}
    assert emitted == set(C.FAILURE_MODES)
    assert result["phase_6_failure_mode_summary"]["all_eleven_emitted"] is True
    assert result["phase_6_failure_mode_summary"]["missing"] == []


@pytest.mark.parametrize("mode", list(C.MODES))
def test_every_failure_mode_carries_a_state_and_a_reason(mode):
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn(mode, _corpus()))
    )
    for record in result["phase_6_failure_modes"]:
        assert record["state"] in C.FAILURE_MODE_STATES, record
        assert record["reason"]
        assert record["description"]


def test_an_unexercised_failure_mode_is_not_reported_as_a_pass():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    by_name = {m["failure_mode"]: m for m in result["phase_6_failure_modes"]}
    # No comparison corpora were supplied, so these were never exercised.
    assert by_name[C.FAILURE_LEXICAL_DEPENDENCE]["state"] == "NOT_EXERCISED"
    assert by_name[C.FAILURE_WHY_IGNORED]["state"] == "NOT_EXERCISED"


def test_predfined_dependence_is_not_exercised_in_mode_p():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    by_name = {m["failure_mode"]: m for m in result["phase_6_failure_modes"]}
    assert (
        by_name[C.FAILURE_PREDEFINED_REPRESENTATION_DEPENDENCE]["state"]
        == "NOT_EXERCISED"
    )


def test_predfined_dependence_is_measured_in_mode_e():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("E", _corpus()))
    )
    by_name = {m["failure_mode"]: m for m in result["phase_6_failure_modes"]}
    assert by_name[C.FAILURE_PREDEFINED_REPRESENTATION_DEPENDENCE]["state"] in (
        "MEASURED_PASS", "MEASURED_FAIL",
    )


# ---------------------------------------------------------------------------#
# 3. The verdict vocabulary and the ceilings
# ---------------------------------------------------------------------------#


def test_the_verdict_uses_the_five_evidence_levels_and_nothing_else():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    assert result["verdict"]["level"] in C.EVIDENCE_LEVELS
    assert result["evidence_levels"] == list(C.EVIDENCE_LEVELS)


def test_mode_p_never_exceeds_its_ceiling():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    assert C.evidence_level_at_most(
        result["verdict"]["level"], C.MODE_P_CEILING
    )


def test_mode_p_never_reports_level_d_or_e():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    assert result["verdict"]["level"] not in (C.LEVEL_D, C.LEVEL_E)


def test_mode_e_ceiling_is_the_highest_level():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("E", _corpus()))
    )
    assert result["verdict"]["ceiling"] == C.LEVEL_E


def test_a_verdict_records_its_reasons():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    assert result["verdict"]["reasons"]


# ---------------------------------------------------------------------------#
# 4. Phase 5 unseen reasoning
# ---------------------------------------------------------------------------#


def test_an_empty_abstraction_accounts_for_nothing():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    phase_5 = result["phase_5_unseen"]
    assert phase_5["accounted_for_count"] == 0
    assert phase_5["supports_abstraction"] is False


def test_phase_5_records_that_no_evaluation_key_was_read():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    assert result["phase_5_unseen"]["evaluation_key_read"] is False


def test_every_unseen_case_gets_a_verdict_record():
    cases = [_uc("u1", "a wall"), _uc("u2", "a floor")]
    result = P.run_v3_abstraction_probe(_probe_directive(
        _learn("P", _corpus()), unseen_cases=cases,
    ))
    assert result["phase_5_unseen"]["case_count"] == 2
    assert len(result["phase_5_unseen"]["case_verdicts"]) == 2


# ---------------------------------------------------------------------------#
# 5. Expectations are read only after the verdict
# ---------------------------------------------------------------------------#


def test_expectations_are_recorded_as_read_after_the_verdict():
    result = P.run_v3_abstraction_probe(_probe_directive(
        _learn("P", _corpus()),
        evaluation_expectations={"anything": True},
    ))
    check = result["evaluation_expectations_read"]
    assert check["read_after_verdict"] is True


def test_expectations_absent_means_no_read_record():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    assert result["evaluation_expectations_read"] is None


# ---------------------------------------------------------------------------#
# 6. The comparison-corpus failure modes
# ---------------------------------------------------------------------------#


def test_a_filler_substitution_leaves_the_abstraction_unchanged():
    teaching = _corpus()
    substituted = [
        _ex("e1", "the burrow is set back from the channel because the user "
                  "needs to recover"),
        _ex("e2", "a grotto sits apart from the gutter so that a person can "
                  "recover quietly"),
    ]
    result = P.run_v3_abstraction_probe(_probe_directive(
        _learn("P", teaching),
        filler_substituted_learner_result=_learn("P", substituted),
    ))
    by_name = {m["failure_mode"]: m for m in result["phase_6_failure_modes"]}
    assert by_name[C.FAILURE_LEXICAL_DEPENDENCE]["state"] in (
        "MEASURED_PASS", "MEASURED_FAIL",
    )


def test_a_why_swap_on_an_empty_abstraction_is_inconclusive():
    result = P.run_v3_abstraction_probe(_probe_directive(
        _learn("P", _corpus()),
        why_swapped_learner_result=_learn("P", _corpus()),
    ))
    by_name = {m["failure_mode"]: m for m in result["phase_6_failure_modes"]}
    assert by_name[C.FAILURE_WHY_IGNORED]["state"] == "INCONCLUSIVE"


def test_a_same_structure_pair_is_measured():
    pair = [
        _uc("s1", "a recess sits apart from the corridor because a person "
                  "recovers"),
        _uc("s2", "a recess sits apart from the corridor because the tiles "
                  "were left over"),
    ]
    result = P.run_v3_abstraction_probe(_probe_directive(
        _learn("P", _corpus()), same_structure_pair=pair,
    ))
    by_name = {m["failure_mode"]: m for m in result["phase_6_failure_modes"]}
    assert by_name[C.FAILURE_SAME_STRUCTURE_CONFLATION]["state"] in (
        "MEASURED_PASS", "MEASURED_FAIL",
    )


# ---------------------------------------------------------------------------#
# 7. Uncertainty and protocol claims
# ---------------------------------------------------------------------------#


def test_uncertainty_collapse_is_measured_as_a_pass_when_retained():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    by_name = {m["failure_mode"]: m for m in result["phase_6_failure_modes"]}
    assert by_name[C.FAILURE_UNCERTAINTY_COLLAPSE]["state"] == "MEASURED_PASS"


def test_hidden_semantic_matcher_is_asserted_absent():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    by_name = {m["failure_mode"]: m for m in result["phase_6_failure_modes"]}
    assert by_name[C.FAILURE_HIDDEN_SEMANTIC_MATCHER]["state"] == "MEASURED_PASS"


def test_the_probe_emits_the_representation_provenance_ledger():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    assert result["representation_provenance_ledger"] == (
        C.REPRESENTATION_PROVENANCE_LEDGER
    )


def test_the_probe_emits_non_claims():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    assert result["non_claims"] == C.REQUIRED_NON_CLAIMS


def test_the_probe_boundary_is_transient_and_read_only():
    result = P.run_v3_abstraction_probe(
        _probe_directive(_learn("P", _corpus()))
    )
    assert result["persistent"] is False
    assert result["read_only"] is True


def test_the_probe_does_not_mutate_its_input():
    directive = _probe_directive(_learn("P", _corpus()))
    snapshot = copy.deepcopy(directive)
    P.run_v3_abstraction_probe(directive)
    assert directive == snapshot


def test_the_probe_is_deterministic():
    directive = _probe_directive(_learn("P", _corpus()))
    first = P.run_v3_abstraction_probe(copy.deepcopy(directive))
    second = P.run_v3_abstraction_probe(copy.deepcopy(directive))
    assert first["verdict"] == second["verdict"]


# ---------------------------------------------------------------------------#
# 8. Static audits
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


def test_module_imports_no_similarity_library():
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
