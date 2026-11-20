"""Tests for V3ConditionV1 - the atomic condition with provenance.

The questions this suite answers:
  * does every element really carry its origin?
  * can a Mode-E slot be filled with an architectural relation word by accident?
  * is the WHY stored verbatim and never silently rewritten?
  * is the boundary strictly gated, transient and read-only?
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
    v3_condition_model_v1 as M,
)

MODULE_PATH = (
    "core/knowledge/understanding_foundation/why_condition_abstraction/"
    "v3_condition_model_v1.py"
)


# ---------------------------------------------------------------------------#
# 1. Construction and shape
# ---------------------------------------------------------------------------#


def test_condition_contract_and_version():
    condition = M.make_condition("c1", "the alcove is set back")
    assert condition["contract"] == "V3ConditionV1"
    assert condition["version"] == "1.0"
    assert condition["level"] == "condition"


def test_condition_has_every_required_field():
    condition = M.make_condition("c1", "the alcove is set back")
    for field in M.REQUIRED_FIELDS:
        assert field in condition, field


def test_scaffold_slots_start_empty_with_no_coercion_declared():
    condition = M.make_condition("c1", "the alcove is set back")
    relation = condition["relation"]
    assert relation["relation_slot"] is None
    assert relation["scope_slot"] is None
    assert relation["relation_slot_origin"] is None
    assert relation["scope_slot_origin"] is None
    assert relation["no_coercion_declared"] is True
    assert relation["scaffold_is_not_a_relation"] is True


def test_scaffold_declares_its_own_origin_as_engineered():
    condition = M.make_condition("c1", "the alcove is set back")
    assert condition["relation"]["scaffold_origin"] == C.ORIGIN_ENGINEERED


# ---------------------------------------------------------------------------#
# 2. Polarity and modality are DERIVED with evidence
# ---------------------------------------------------------------------------#


def test_polarity_is_derived_from_an_explicit_negative_marker():
    condition = M.make_condition("c1", "the hall must not be overlooked")
    assert condition["polarity"]["value"] == "negative"
    assert condition["polarity"]["kind_origin"] == C.ORIGIN_DERIVED
    assert "not" in condition["polarity"]["markers_present"]


def test_polarity_is_positive_when_no_negative_marker_is_present():
    condition = M.make_condition("c1", "the hall opens to the court")
    assert condition["polarity"]["value"] == "positive"
    assert condition["polarity"]["markers_present"] == []


def test_modality_is_derived_with_the_marker_that_produced_it():
    condition = M.make_condition("c1", "the wall must remain solid")
    assert condition["modality"]["value"] == "obligation"
    assert condition["modality"]["marker"] == "must"
    assert condition["modality"]["kind_origin"] == C.ORIGIN_DERIVED


def test_modality_defaults_to_assertion_when_no_marker_is_present():
    condition = M.make_condition("c1", "the alcove is set back")
    assert condition["modality"]["value"] == "assertion"
    assert condition["modality"]["marker"] is None


def test_prohibition_beats_obligation_because_it_is_tested_first():
    condition = M.make_condition("c1", "the stair must not be blocked")
    assert condition["modality"]["value"] == "prohibition"


# ---------------------------------------------------------------------------#
# 3. Slot filling and the origin discipline
# ---------------------------------------------------------------------------#


def test_fill_relation_slot_records_the_origin_of_the_kind():
    scaffold = M.make_scaffold()
    filled = M.fill_relation_slot(scaffold, "access", "boundary_crossing",
                                  C.ORIGIN_ENGINEERED)
    assert filled["relation_slot"] == "access"
    assert filled["scope_slot"] == "boundary_crossing"
    assert filled["relation_slot_origin"] == C.ORIGIN_ENGINEERED
    assert filled["scope_slot_origin"] == C.ORIGIN_ENGINEERED
    assert filled["no_coercion_declared"] is False


def test_fill_relation_slot_rejects_an_unknown_origin():
    scaffold = M.make_scaffold()
    with pytest.raises(ValueError):
        M.fill_relation_slot(scaffold, "access", None, "INVENTED")


def test_a_filled_slot_without_an_origin_is_refused():
    scaffold = M.make_scaffold()
    scaffold["relation_slot"] = "access"
    scaffold["relation_slot_origin"] = None
    with pytest.raises(ValueError):
        M.validate_scaffold(scaffold)


def test_an_empty_slot_declaring_an_origin_is_refused():
    scaffold = M.make_scaffold()
    scaffold["relation_slot"] = None
    scaffold["relation_slot_origin"] = C.ORIGIN_EMERGENT
    with pytest.raises(ValueError):
        M.validate_scaffold(scaffold)


def test_a_slot_origin_outside_the_closed_set_is_refused():
    scaffold = M.make_scaffold()
    scaffold["relation_slot"] = "access"
    scaffold["relation_slot_origin"] = "PROBABLY"
    with pytest.raises(ValueError):
        M.validate_scaffold(scaffold)


# ---------------------------------------------------------------------------#
# 4. The WHY is stored verbatim
# ---------------------------------------------------------------------------#


def test_why_verbatim_is_stored_exactly_as_supplied():
    reason = "the user needs to recover"
    condition = M.make_condition("c1", "the alcove is set back",
                                 why_verbatim=reason)
    assert condition["why"]["why_verbatim"] == reason


def test_why_keeps_the_first_class_fields():
    condition = M.make_condition("c1", "the alcove is set back",
                                 why_verbatim="because recovery matters")
    for field in ("why_verbatim", "why_clause", "grounding",
                  "causal_direction"):
        assert field in condition["why"], field


def test_a_condition_without_a_why_is_marked_unbound():
    condition = M.make_condition("c1", "the alcove is set back")
    assert condition["why"]["grounding"] == "unbound"
    assert condition["why"]["causal_direction"] == "unknown"


# ---------------------------------------------------------------------------#
# 5. Uncertainty and alternatives are retained, never collapsed
# ---------------------------------------------------------------------------#


def test_uncertainty_starts_unresolved_when_no_slot_is_derived():
    condition = M.make_condition("c1", "the alcove is set back")
    assert condition["uncertainty"]["level"] == "unresolved"
    assert condition["uncertainty"]["collapsed"] is False


def test_an_alternative_reading_is_retained():
    condition = M.make_condition(
        "c1", "the alcove is set back",
        alternatives=[{"plausible_alternative_reading": "another reason"}],
    )
    assert len(condition["alternatives"]) == 1
    assert condition["uncertainty"]["retained_alternatives"]


# ---------------------------------------------------------------------------#
# 6. Intended effect is an explicit inference, never the human's words
# ---------------------------------------------------------------------------#


def test_intended_effect_is_flagged_as_an_inference():
    condition = M.make_condition("c1", "the alcove is set back",
                                 intended_effect="quiet recovery")
    assert condition["intended_effect"]["is_inference"] is True
    assert condition["intended_effect"]["origin"] == C.ORIGIN_DERIVED


def test_intended_effect_is_absent_when_nothing_is_inferred():
    condition = M.make_condition("c1", "the alcove is set back")
    assert condition["intended_effect"] is None


# ---------------------------------------------------------------------------#
# 7. Strict gating
# ---------------------------------------------------------------------------#


def test_a_non_dict_is_refused():
    with pytest.raises(TypeError):
        M.validate_condition(["not", "a", "dict"])


def test_a_forbidden_contract_is_refused():
    with pytest.raises(ValueError):
        M.validate_condition({"contract": "ArchitecturalBIMEntityV1",
                              "version": "1.0"})


def test_a_wrong_contract_is_refused():
    with pytest.raises(ValueError):
        M.validate_condition({"contract": "SomethingElse", "version": "1.0"})


def test_a_wrong_version_is_refused():
    condition = M.make_condition("c1", "the alcove is set back")
    condition["version"] = "9.9"
    with pytest.raises(ValueError):
        M.validate_condition(condition)


def test_a_missing_required_field_is_refused():
    condition = M.make_condition("c1", "the alcove is set back")
    del condition["polarity"]
    with pytest.raises(ValueError):
        M.validate_condition(condition)


def test_a_why_missing_a_first_class_field_is_refused():
    condition = M.make_condition("c1", "the alcove is set back")
    del condition["why"]["causal_direction"]
    with pytest.raises(ValueError):
        M.validate_condition(condition)


def test_a_valid_condition_validates_and_returns_a_copy():
    condition = M.make_condition("c1", "the alcove is set back")
    out = M.validate_condition(condition)
    assert out == condition
    assert out is not condition


# ---------------------------------------------------------------------------#
# 8. Transient and read-only
# ---------------------------------------------------------------------------#


def test_the_input_is_not_mutated():
    condition = M.make_condition("c1", "the alcove is set back")
    snapshot = copy.deepcopy(condition)
    M.validate_condition(condition)
    assert condition == snapshot


# ---------------------------------------------------------------------------#
# 9. Clause splitting never separates a WHY from its condition
# ---------------------------------------------------------------------------#


def test_clauses_splits_on_semicolons_and_connectives():
    parts = M.clauses("the hall opens; the stair rises and the rail turns")
    assert len(parts) >= 2


def test_clauses_does_not_split_on_the_word_because():
    parts = M.clauses("the alcove is set back because the user recovers there")
    assert len(parts) == 1
    assert "because" in parts[0]


def test_negation_markers_include_structural_negations_only():
    for marker in M.NEGATION_MARKERS:
        assert re.fullmatch(r"[a-z0-9 ]+", marker), marker


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
    tree = ast.parse(_module_source())
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.append(node.module)
    forbidden = ("numpy", "scipy", "sklearn", "torch", "tensorflow",
                 "sentence_transformers", "gensim", "spacy", "transformers",
                 "openai", "anthropic")
    for name in imported:
        assert name.split(".")[0] not in forbidden, name


def test_module_contains_no_synonym_table_in_logic():
    source = _module_source()
    tree = ast.parse(source)
    excluded = _docstring_ranges(tree) + _guard_tables(tree)
    for index, line in enumerate(source.splitlines()):
        if any(start <= index <= end for start, end in excluded):
            continue
        lowered = line.lower()
        assert "synonym_map" not in lowered, line
        assert "synonyms" not in lowered, line


def test_module_does_not_import_the_frozen_v2_package():
    tree = ast.parse(_module_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "architectural_abstraction" not in node.module, node.module
            assert "abstraction_learner_v1" not in node.module, node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "architectural_abstraction" not in alias.name


def test_module_is_ascii_apart_from_typographic_rules():
    source = _module_source()
    tree = ast.parse(source)
    docstrings = _docstring_ranges(tree)
    box = set("\u2500\u2502\u250c\u2510\u2514\u2518\u251c\u2524\u252c\u2534"
              "\u253c\u2550\u2551\u2554\u2557\u255a\u255d")
    structural = "\u060c\u061b\u061f"
    for index, line in enumerate(source.splitlines()):
        if any(start <= index <= end for start, end in docstrings):
            continue
        for char in line:
            if char in box or char in structural:
                continue
            assert ord(char) <= 0x7F, repr(line)
